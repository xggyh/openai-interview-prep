## 题目本质

设计 **Foursquare** —— 位置感知（LBS）社交 app：用户提交 lat/lng → 返回附近 POI 列表。比 Yelp 更轻（不含评论 / 餐厅信息），重点是 **k-nearest POI** 高效查询 + 全球扩展。

OpenAI Staff 级 1 人报告。考点：**地理索引（QuadTree / GeoHash / H3） + 多区域分布**。

## 需求拆解

**功能性：**
- POST `/checkin {user_id, lat, lng}` → 记录用户当前位置
- GET `/nearby?lat=&lng=&radius_m=` → 返回 N 个最近 POI
- POST `/poi` → 添加新 POI（餐厅、地标）

**非功能性：**
- 1 亿活跃用户 / 10 亿 POI
- nearby 查询 P99 < 100ms
- 全球部署
- 写入 < 1M 次/秒（checkin + POI updates）

## 整体架构

```ascii
   Mobile
     │ lat/lng
     ▼
  ┌──────────┐
  │ Edge GW  │  geo-route to nearest region
  └────┬─────┘
       │
       ▼
  ┌──────────────┐
  │ Query Svc    │  → 地理索引查找 + POI metadata fan-out
  └──┬─────────┬─┘
     │         │
     ▼         ▼
  ┌─────┐  ┌─────────────┐
  │ Geo │  │ POI         │  Cassandra/Postgres
  │Index│  │ Metadata DB │
  │(in- │  └─────────────┘
  │ memo│
  │  +  │
  │Redis│
  │GEO) │
  └─────┘
       │
       ▼
  ┌──────────────┐
  │ Checkin Log  │  Kafka → analytics
  └──────────────┘
```

## 核心组件设计

### 1. 地理空间索引选择

| 方案 | 优点 | 缺点 |
|---|---|---|
| **GeoHash** | 简单、Redis 原生 | 矩形边界，相邻 cell 距离不均匀 |
| **QuadTree** | 自适应密度 | 写入 rebalance 复杂 |
| **H3 hexagon (Uber)** | 六边形邻居均匀、12 级精度 | 学习成本 |
| **S2 (Google)** | 球面映射精确、library 成熟 | 比 H3 复杂 |
| **R-tree** | 通用 bounding box | 写更新 slow |

**Foursquare 这种简单 nearest-POI 查询，推荐 GeoHash + Redis** 或 **H3**。

### 2. GeoHash 实现

```python
import redis
r = redis.Redis()

# 添加 POI
r.geoadd('pois:global', longitude, latitude, poi_id)

# 查询 nearby
results = r.geosearch(
    'pois:global',
    longitude=-122.4, latitude=37.7,
    radius=1, unit='km',
    sort='ASC', count=20,
    withcoord=True, withdist=True
)
```

底层用 GeoHash 52-bit interleaved bits 存储。`GEOSEARCH` 把目标点的 9 个邻居 cell 都搜一遍（中心 + 8 邻居）保证不遗漏。

### 3. H3 实现（更精细）

```python
import h3

# POI 入库时计算多级 H3 index
def index_poi(poi_id, lat, lng):
    cells = {res: h3.geo_to_h3(lat, lng, res) for res in [7, 8, 9]}
    for res, cell in cells.items():
        redis.sadd(f"h3:{res}:{cell}", poi_id)

# 查询：用合适 resolution
def nearby(lat, lng, radius_m):
    if radius_m < 100:    res = 9       # ~100m hex
    elif radius_m < 1000: res = 8       # ~500m
    else: res = 7                       # ~1.5km
    center = h3.geo_to_h3(lat, lng, res)
    # 取 center + 周围 k-rings（k=ceil(radius / hex_size))
    cells = h3.k_ring(center, k=1)
    poi_ids = set()
    for c in cells:
        poi_ids |= redis.smembers(f"h3:{res}:{c}")
    # 精确距离过滤
    results = []
    for pid in poi_ids:
        meta = poi_db.get(pid)
        d = haversine(lat, lng, meta.lat, meta.lng)
        if d <= radius_m:
            results.append((pid, d))
    return sorted(results, key=lambda x: x[1])[:20]
```

H3 邻居距离均匀，比 GeoHash 更可控。

### 4. POI Metadata Store

```sql
CREATE TABLE pois (
  id          UUID PRIMARY KEY,
  name        TEXT,
  category    TEXT[],
  lat         DOUBLE PRECISION,
  lng         DOUBLE PRECISION,
  address     TEXT,
  popularity  INT,           -- check-in count cached
  status      TEXT
);
```

按 `id` hash 分 shard（写均匀）。读用 cache（Redis LRU）热门 POI。

### 5. Checkin Log

```python
# Kafka topic: checkins.v1
# {user_id, poi_id, ts, lat, lng}
```

写入时更新 POI popularity（异步聚合）：每分钟一次 `INCR popularity`。

### 6. 分区策略（全球）

POI 是 global query —— 用户在 SF 查 POI，POI 数据在每个 region 都要有副本（否则跨洋查询延迟爆）。

**方案**：每个 region 独立 Redis cluster，存全球 POI 的 geo index。POI 写入走主 region，CDC 异步同步到所有 region。

读：永远走本 region，亚秒延迟。

### 7. Caching

热门 POI（前 1%）走 Redis hot cache：
- POI metadata：`HGET poi:{id}` → cached lookup
- Popular nearby query 结果：按 `(geohash, category, hour)` 缓存几分钟

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Geo index | Redis GEO (GeoHash) | H3：更精确但需要库 |
| Replication | 全 region 复制 POI | 单 region：跨洋慢 |
| POI 写 | Master region + CDC | Multi-master：冲突难处理 |
| Popularity | 异步聚合 | 实时 UPDATE：写热点 |

## 容量估算

- 10 亿 POI × 平均 200 字节 = 200 GB POI metadata
- 每 region Redis GEO 全球 POI 索引 ≈ 10 亿 × 24 B = 24 GB 内存 → 一个 Redis cluster 能装下
- 写入 1M ops/s 主要是 checkin（POI 更新慢），Kafka 完全能撑

## 关键技术细节

- **Haversine distance** 精确算两点距离（球面距离）
- **dedup POI**：用户报告"new POI"时，先按 (name + lat/lng 50m 内) 查 fuzzy match，避免重复
- **POI validation**：crowdsource 上传 + spam filter + 人工审核 high-traffic
- **Privacy**：用户 checkin 默认 friends-only，可以匿名贡献 POI

> [!key]
> 三大要点：(1) **GeoHash / H3 索引** 解 nearest-K 查询；(2) **每 region 独立 Redis GEO + 异步全球复制**；(3) **POI metadata cache + popularity 异步聚合**。

> [!pitfall]
> ❌ 查询直接 SQL `WHERE distance(...) < r` —— 全表扫，慢 100x；
> ❌ Single-region Redis 给全球用 —— 跨洋 200ms 延迟；
> ❌ POI popularity 实时 UPDATE —— 热点写；
> ❌ GeoHash 只查中心 cell —— 边界 POI 漏；要 9 cell（自身 + 8 邻居）；
> ❌ User checkin 同步阻塞 nearby query → 锁竞争。

> [!followup]
> "如何动态调整 hex resolution？" → 根据 region 密度（曼哈顿用 res=10，沙漠用 res=7）；"如何支持 'place near my future location' (路线 nearby)？" → 把路线 polyline 转为多个 segment，对每个 segment buffer + 取 union；"反作弊（用户假 checkin）？" → 加速度计 + GPS sanity check + ML 异常检测。
