## 题目本质

设计 **Yelp** —— 位置感知服务（LBS）：用户提交 lat/lng → 查询附近商家 → 返回 POI 列表 + ratings/reviews。全球规模、高 QPS。

OpenAI Senior-Staff 级，6 人报告。考点：**地理空间索引 (geohash / QuadTree / R-tree) + 多维查询 + 评论存储**。

## 需求拆解

**功能性：**
- 商家入驻（位置 + 类目 + 营业信息）
- 用户查 nearby (radius 1-5 km) → 返回商家列表 + 评分排序
- 关键词搜索（"pizza near me"）
- 用户写评论 + 上传图片
- 评分 1-5 星

**非功能性：**
- 1 亿月活，峰值 50k QPS
- 查询 P99 < 200ms
- 全球覆盖（multi-region）
- 评论持久 + 防刷

## 整体架构

```ascii
   Client (mobile)
        │ lat/lng + query
        ▼
   ┌──────────────┐
   │  Edge / CDN  │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │  Search API  │
   └──┬───────┬───┘
      │       │
      ▼       ▼
 ┌────────┐  ┌──────────────────┐
 │ Geo    │  │ Full-Text Search │  Elasticsearch
 │ Index  │  │ (name + cat)     │
 │(Quad/  │  └──────────────────┘
 │ Geo-   │
 │  hash) │
 └────────┘
      │
      ▼
 ┌──────────────┐
 │ Business DB  │  Postgres / Cassandra
 │ (metadata)   │
 └──────┬───────┘
        │
        ▼
 ┌──────────────┐
 │ Reviews DB   │  Cassandra (by business_id)
 └──────────────┘

   write path (reviews / business updates)
        ▼
   Kafka → indexers → Geo + ES
```

## 核心组件

### 1. 地理空间索引（最关键）

三种主流方案：

**A. Geohash**
- 把 lat/lng 编码成字符串（如 `9q8yyx`），共享前缀越多越近
- 存 `geohash → list[business_id]`，按前缀查（前 5 字符 ≈ 5 km × 5 km 格子）
- 查 nearby：用 8 个相邻 cell（自身 + 周围 8 格）union 出候选 → 再按精确距离过滤
- 优点：实现简单，Redis ZSET 存 prefix；缺点：边界效应（cell 边上的商家漏查需 8 cell union）

**B. QuadTree**
- 递归四分整张地图；密集区域细分，稀疏区域大格子
- 查找时定位到含查询点的最小格子 + 邻居格子
- 优点：自适应密度；缺点：实现复杂

**C. R-tree**
- 用矩形 bounding box 组织点；支持任意 bounding box 查询
- 优点：通用，支持 polygon；缺点：写更新成本高（rebalance）

**推荐方案 A**（Geohash）—— 简单 + Redis 原生 GEOADD/GEOSEARCH 支持。

### 2. Redis GEO Commands

```python
# 入驻商家
redis.geoadd('businesses:sf', longitude, latitude, business_id)

# Nearby 查询：用户在 (-122.4, 37.7) 找 2km 内的商家
results = redis.geosearch('businesses:sf',
    longitude=-122.4, latitude=37.7,
    radius=2, unit='km',
    sort='ASC',                # 按距离升序
    count=50,
    withcoord=True, withdist=True)
```

Redis GEO 内部用 geohash 实现。极简。

**Sharding**：按 city 或 H3 hex 大格分 shard，跨 shard 时合并候选。

### 3. Business 数据模型

```sql
CREATE TABLE businesses (
  id            UUID PRIMARY KEY,
  name          TEXT,
  category_ids  TEXT[],
  lat           DOUBLE PRECISION,
  lng           DOUBLE PRECISION,
  address       TEXT,
  hours         JSON,
  phone         TEXT,
  avg_rating    NUMERIC(2,1),     -- materialized
  review_count  INT,              -- materialized
  status        TEXT,
  created_at    TIMESTAMPTZ
);
CREATE INDEX idx_cat ON businesses USING GIN (category_ids);
```

### 4. Reviews

```sql
-- Cassandra: by business_id partition
CREATE TABLE reviews (
  business_id  UUID,
  review_id    UUID,
  user_id      UUID,
  rating       INT,
  body         TEXT,
  images       LIST<TEXT>,
  ts           TIMESTAMP,
  PRIMARY KEY ((business_id), ts, review_id)
) WITH CLUSTERING ORDER BY (ts DESC);
```

写评论时**异步更新** business 的 `avg_rating` 和 `review_count`：
- Kafka topic: `review.created`
- Worker 消费 → 重新计算 (running avg)：`new_avg = (old_avg * old_count + rating) / (old_count + 1)`
- 写回 businesses 表

### 5. 全文搜索

`name + category + description` 索引到 Elasticsearch：
- Query: `match: { query: "pizza" }` + filter geo bounding box
- ES 原生支持 `geo_distance` filter

混合查询：
```json
{
  "query": {
    "bool": {
      "must": { "match": { "name": "pizza" } },
      "filter": { "geo_distance": { "distance": "2km", "location": {"lat":..., "lon":...} } }
    }
  },
  "sort": [{"_geo_distance": {...}}, {"avg_rating": "desc"}]
}
```

### 6. 评分排序融合

最终列表的 score 综合：
- 距离（越近越好）
- 评分（越高越好）
- 评论数（越多越可信）
- Sponsored（付费）

```
score = w1 * inverse_distance + w2 * avg_rating + w3 * log(review_count) + w4 * sponsored_boost
```

ML 模型可以学习权重。

### 7. 防刷评论

- 一个用户对一个商家只能写一条 review
- 检测异常：同 IP 大量 review、刚注册用户、内容文本相似度高
- ML 分类器 + 人工审核 + 用户举报

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Geo index | Redis GEO (geohash) | QuadTree：复杂；R-tree：写成本高 |
| Reviews 存储 | Cassandra | Postgres：写吞吐撑不住 |
| 评分聚合 | Materialized + 异步更新 | 实时 SELECT AVG：查询慢 |
| 全文搜索 | Elasticsearch | DB LIKE：慢 |
| Multi-region | per-region cluster + 异步同步 | Global single：延迟高 |

## 关键技术细节

- **H3 hex 比 geohash 更均匀**：Uber 开源的 H3 把地球分成六边形格子，相邻 cell 距离一致（geohash 有矩形边界问题）。生产可选
- **CDN 缓存 hot business**：商家详情 + photos 走 CDN
- **Photo storage**：S3 + 多分辨率（thumb / medium / large）
- **Stale rating**：avg_rating 异步更新可能 ms 级 stale，业务可接受

> [!key]
> 三大要点：(1) **Redis GEO / geohash** 作地理索引；(2) **Cassandra by business_id** 写评论；(3) **avg_rating materialized + 异步更新** 避免 SELECT AVG 扫表。

> [!pitfall]
> ❌ Nearby 查询用 `SELECT * WHERE dist < 2km` —— 全表 + 计算 distance，慢死；
> ❌ 评分用 `SELECT AVG()` 实时算 —— 表大时几秒；
> ❌ 评论存 Postgres 没 partition —— 热门商家行数爆；
> ❌ Geohash 不考虑边界 cell —— 漏查相邻；
> ❌ Photo 直接走 backend —— 流量爆。

> [!followup]
> "高峰餐厅排长队怎么排？" → 实时 queue 状态写 Redis，pub/sub 推前端；"how to handle business 移动（gas station 在地图上位置错了）？" → 用户举报 + 重新审核工作流；"如何全球扩展？" → per-continent region 独立 cluster，主从复制 metadata。
