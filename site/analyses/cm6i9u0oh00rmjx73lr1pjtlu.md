## 题目本质

设计 **Navigation / Mapping System** (Google Maps / Apple Maps)：用户输入起终点 → 返回最优路线 + ETA + 实时导航更新。

Google 报告 7 次。考点：**graph shortest path at scale + real-time traffic + map tile rendering + ETA prediction**。

## 需求拆解

- 全球地图，10B+ road segments
- 1M+ concurrent users navigating
- 路线 P95 < 500ms
- ETA 准确度 < 10% error
- Offline / online 混合

## 整体架构

```ascii
   Mobile App
       │
       │ start/end + current location
       ▼
  ┌──────────────┐
  │   Edge       │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐         ┌────────────────┐
  │ Routing Service  │ ──────▶ │ Map Graph      │
  │ (Dijkstra/A*+CH) │         │ (preprocessed) │
  └──────┬───────────┘         └────────────────┘
         │
         │ traffic / ETA
         ▼
  ┌──────────────────┐
  │ Traffic Service  │ ◀── real-time GPS feeds
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ Tile Server      │  → map tiles to client
  │ (vector / raster)│
  └──────────────────┘
```

## 核心组件

### 1. Map Graph 数据结构

道路是有向图：node = intersection，edge = road segment with (length, speed_limit, turn_restrictions, current_traffic)。

**预处理**：分层（Highway / Arterial / Local）+ **Contraction Hierarchies (CH)** 让 query 时间 sub-millisecond。

### 2. Routing 算法

- **Dijkstra**：O((V+E) log V)。10B 边的全球图直接跑会爆。
- **A***：加 heuristic (great-circle distance to destination)，剪枝大。
- **Contraction Hierarchies**：预处理 O(N log² N)，查询 O(log² N)。Google / OSRM 实战用法。
- **Hierarchical Dijkstra**：先在 highway level 搜，下沉到 local level。

实战：CH + landmark heuristic + bidirectional search。

### 3. Real-time traffic

来源：
- Anonymized GPS from app users (consent-based)
- Government / road sensor APIs
- Historical patterns

每条 road segment 每分钟更新 estimated speed。Routing 时 cost = length / speed。

```
edge_cost(e, t) = length(e) / current_speed(e, t)
```

### 4. ETA prediction

不是简单 sum edge cost。ML model 加上：
- Time of day / day of week patterns
- Weather
- Special events (concerts / sports)
- Historical 同时段数据

Model 每 5 分钟 retrain（短期 ETA 准确）。

### 5. Re-routing

App 每 30 秒发当前位置。如果：
- 偏离 plan route → re-route
- 前方 traffic 变差，ETA +20% → 建议 alt route

Re-route 是 incremental Dijkstra from current location。

### 6. Tile rendering

地图分 256×256 像素 tile，z (zoom) × x × y 三维索引。Client 按 viewport 请求 tiles。
- 矢量 tile：客户端渲染（轻量 + zoom 平滑）
- 栅格 tile：服务端预渲染（兼容老设备）

CDN cache by (z, x, y, style)，hit rate 极高。

### 7. POI / Search

道路本身 + POI（餐厅 / 加油站 / ATM）。POI 用 geohash / S2 cell 索引，"附近 X 类型" 查询用 LC-style nearest-K。

### 8. Offline mode

下载 region tile + 路网 graph + POI 数据。本地 Dijkstra 跑离线导航。

## 关键技术

### Contraction Hierarchies 简介

预处理：按 importance 顺序 "contract" 每个 node —— 移除 node 时为它的邻居添加 shortcut edges 保持 shortest path 性质。

Query：双向 A* 只用 contracted graph 中 "向上" 边 → query O(log² N) 比纯 Dijkstra 快 1000x。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Routing | CH + A* | 纯 Dijkstra：query 慢 |
| Traffic | Crowdsource GPS | 静态：实时性差 |
| ETA | ML model | rule-based：精度低 |
| Tiles | Vector + CDN | Raster only：流量高 |
| Re-route | Server-side | Client-side：算力不够 |

## 容量估算

- 1M concurrent users × 路线请求 / 5 分钟 = 200k QPS routing
- CH query ~1ms × 200k = 200 cores 够（分布式 routing service）
- Tile QPS：1M users × 10 tiles/page × 1 request/min = 167k QPS → CDN 99% hit，origin 1.7k

## 易错点

> [!pitfall]
> ❌ 直接 Dijkstra 全球图 —— TLE；
> ❌ 用 Euclidean distance 算 cost —— 没考虑 road network；
> ❌ Real-time traffic 每秒收 GPS —— 太频繁，1 分钟 aggregate 就够；
> ❌ ETA 不考虑 historical pattern —— 周一 8AM 比周日 10AM 慢 3x，model 必须 capture；
> ❌ Tile 不 CDN —— 流量爆。

> [!key]
> 三大要点：(1) **CH preprocessing + bidirectional A*** 把全球 graph routing 干到 ms 级；(2) **Crowdsource GPS + ML ETA** 实时准确；(3) **Vector tile + CDN** 服务地图。

> [!followup]
> "Multi-mode (driving + transit + walking)？" → 多层 graph，cost function 不同；"Carpool / Ride share 路线？" → multi-stop TSP 启发式；"3D / AR 导航？" → 加海拔 + 楼层数据；"Bike / Pedestrian 不同 graph？" → 用 OSM tags 过滤可通行。
