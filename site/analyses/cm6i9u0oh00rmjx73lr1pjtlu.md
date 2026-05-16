## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Routing** | 找两点间最优路线 | 走迷宫找出口 |
| **Graph** | 由 node + edge 组成的数据结构。地图：node = 路口，edge = 路段 | 蜘蛛网 |
| **Dijkstra** | 经典最短路径算法，从起点扩散 | 漫水法找门 |
| **A***  | Dijkstra + heuristic，扩散有方向感更快 | 用指南针的漫水法 |
| **Contraction Hierarchies (CH)** | 预处理 graph 加 shortcut 边，查询超快 | 主城与城外修高速 |
| **OSM (OpenStreetMap)** | 开源全球地图数据 | 维基百科的地图版 |
| **ETA** | Estimated Time of Arrival | "预计 1 小时到" |
| **Geohash / S2 / H3** | 把地球切成 grid 的索引体系 | 经纬度的"邮编" |
| **Tile** | 地图渲染的小方块 (256×256 像素)，按 zoom 层切 | 拼图的一片 |
| **Vector tile** | 地图 tile 用矢量描述（点线面），客户端渲染 | 矢量图 vs 位图 |
| **Reverse geocoding** | 把 GPS 转地址 | (37.4, -122.0) → "Mountain View, CA" |
| **POI** | Point of Interest，餐厅 / 加油站 / 地标 | 地图上的兴趣点 |

---

## 1. 题目本质 — 这是什么问题

**Navigation / Mapping System** = Google Maps / Apple Maps / Waze 这类应用：
1. 显示地图（视觉）
2. 搜索地点（POI / 地址）
3. **算两点最短路线**（routing）
4. **预测 ETA**（实时 traffic）
5. **导航实时更新**（绕道 / 重算）

**为什么这道题难**：

1. **地图巨大**：全球 1B+ road segment（OSM 数据库 100+ GB raw）
2. **Routing 对计算密集**：朴素 Dijkstra 在 1B node graph 上跑半小时不出结果
3. **实时 traffic** 大量数据流：千万用户每秒报位置
4. **ETA 准** ≠ length / speed limit；要考虑历史 pattern + 实时 traffic + 天气
5. **全球部署 + 低延迟**：APAC 用户不能等加州 server 响应 200ms
6. **离线** mobile：网络断仍要能导航

考点：**graph shortest path at scale + real-time traffic ingest + ETA ML + map tile delivery**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：用户主要场景是开车导航？还是步行 / 公共交通？  
**典型答**：先做开车，扩展支持步行 / 公交。

**你问**：实时 traffic 怎么来？  
**典型答**：(a) Anonymous GPS from app users (consent-based)；(b) 政府 / 路网 sensor；(c) 历史 pattern fallback。

**你问**：要不要 reroute on traffic change？  
**典型答**：要。每 30 秒检查，明显更快路线 → 建议切换。

**你问**：离线模式？  
**典型答**：下载某 region 数据后能离线导航。

### 2.2 非功能性

**你问**：用户量 / 并发？  
**典型答**：1M+ concurrent navigation。

**你问**：单 routing 查询延迟？  
**典型答**：P95 < 500ms (开始导航前用户能等)；reroute < 200ms (导航中)。

**你问**：地图渲染延迟？  
**典型答**：tile load < 100ms (CDN cache hit 是常态)。

**你问**：ETA 准确度？  
**典型答**：误差 < 10%（30 min trip 准 ±3 min）。

### 2.3 需求清单

```
功能：
- Routing (driving/walking/transit)
- POI search
- ETA prediction with traffic
- Reroute on traffic change
- Map tile rendering
- Offline mode

非功能：
- 1M concurrent users
- Routing P95 < 500ms
- Tile load < 100ms (CDN)
- ETA error < 10%
```

> [!key]
> 这道题最难的部分是 **routing scale**。1B node graph 上跑 Dijkstra 直接死。**Contraction Hierarchies** 这个算法是 Google Maps / OSRM 真用的。要熟。

---

## 3. 容量估算

### 3.1 地图数据

```
全球道路 ~100M road segment
每 segment metadata 100 byte → 10 GB
+ POI 1B × 200 byte = 200 GB
+ Tile (multi-zoom): pre-rendered 几 TB
```

→ **几 TB raw**, 加索引 + multi-resolution → 几十 TB。

### 3.2 Routing QPS

```
1M concurrent × 路线请求 / 5 分钟 (开始 + 偶尔 reroute)
= 200k routing QPS
```

每 routing 朴素 Dijkstra 1 秒 → 需要 200k cores。**用 CH 降到 1ms** → 几百 cores 够。

### 3.3 Traffic 上报

```
1M users × ping every 5s = 200k GPS pings/sec
× 30 byte each = 6 MB/sec
```

Kafka 完全撑得住。

### 3.4 Tile QPS

```
1M users × 平均 10 tile / page × 1 page / min = 167k tile QPS
CDN 99% hit → origin 1.7k QPS
```

### 3.5 估算清单

```
Routing: 200k QPS, 必须用 CH (1ms/query)
Traffic: 200k pings/sec → Kafka
Tile: 167k QPS CDN, 1.7k origin
Storage: ~50 TB total (map + tiles + POI)
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：朴素方案

```ascii
   User → Service
   Service: Dijkstra(graph, start, end)
```

**问题**：1B node graph，Dijkstra O((V+E) log V) → 几分钟。User 等不了。

### 4.2 第 1 步：预处理 graph (CH)

**Contraction Hierarchies** = 预处理把 graph 转换成有 shortcut edge 的形式。**Query 时间从分钟降到 ms**。

```
原 graph: 1B nodes, 任意两点 Dijkstra 慢
↓ 预处理（offline, 几小时）
CH graph: 1B nodes + 100M shortcuts
↓ Query
A* 双向搜索 + 只走 "向上" 边 → 1ms
```

预处理思路：按 "importance" 顺序逐一 contract 节点 —— 把它从 graph 移除，加 shortcut 到它的 neighbors，保证最短路径性质。

**为什么这样能加速**：query 不必扫每个 node，只在"contracted hierarchy"中跳跃。highway 这种 important 节点更靠近 root，几跳就能跨越大距离。

### 4.3 第 2 步：实时 traffic 集成

```ascii
   Phone GPS → Kafka topic: gps.pings
                 │
                 ▼
            ┌──────────────────┐
            │ Stream Processor │  per-edge: aggregate speed
            └──────┬───────────┘
                   │
                   ▼
            ┌──────────────────┐
            │ Edge speed       │  current_speed[edge_id] = avg of last 5min
            │ Cache (Redis)    │
            └──────────────────┘
                   │
                   ▼
            Routing service reads from cache
            uses current_speed instead of speed_limit
```

每 road segment 当前估计速度从 GPS pings 聚合。Stream processor 5 分钟 window。

### 4.4 第 3 步：ETA prediction

```
Naive ETA = sum(length[edge] / current_speed[edge])
```

不准。因为：
- Stop signs / traffic lights 不在 speed 里
- 历史 pattern (周一 8AM vs 周日 10AM)
- 天气 / 特殊事件
- 司机驾驶习惯

**ML ETA Model**:

```python
features = [
    naive_eta,              # 朴素 sum 的 baseline
    current_traffic_score,  # 当前 traffic
    time_of_day,
    day_of_week,
    weather,
    historical_pattern[edge][hour][weekday],
    special_events_nearby,
]
predicted_eta = model.predict(features)
```

Gradient Boosting / DNN，每 5 分钟 retrain。Google Maps 实测 ETA 误差 < 3%。

### 4.5 第 4 步：Tile + CDN

```ascii
Map tile (per zoom level z, x, y):
  z=0: 1 tile covers whole world
  z=10: ~1M tiles
  z=18 (max): ~10B tiles
  
Storage: ~10 TB total (pre-rendered raster)
Or: vector tiles (~1 TB, client renders)
```

**Vector tiles 优势**：
- 客户端渲染 → 更小（geometry + style）
- Zoom 平滑（vector 可任意缩放）
- 主题切换不重新 download (dark mode / satellite)

CDN cache by (z, x, y, style)。**Immutable** → TTL 永久。

### 4.6 第 5 步：完整架构

```ascii
   Mobile / Web client
       │
       ▼
   ┌──────────────┐
   │ Edge / CDN   │  ← geo-routed
   └──────┬───────┘
          │
          ▼
   ┌──────────────────┐         ┌────────────────┐
   │ Routing Service  │ ──────▶ │ Map Graph      │
   │ (CH + A*)        │         │ (preprocessed) │
   └──────┬───────────┘         └────────────────┘
          │
          │ traffic
          ▼
   ┌──────────────────┐
   │ Traffic Service  │ ◀── Real-time GPS feeds (Kafka)
   │ (per-edge speed) │
   └──────────────────┘
          │
          ▼
   ┌──────────────────┐
   │ ETA Service      │  ML model
   └──────────────────┘
          
   Separate:
   ┌──────────────────┐         ┌──────────────────┐
   │ Tile Server      │ ──────▶ │ CDN              │
   │ (vector / raster)│         │ (immutable)      │
   └──────────────────┘         └──────────────────┘
   ┌──────────────────┐
   │ POI Service      │  Elasticsearch + geo index
   └──────────────────┘
```

---

## 5. 每个组件深挖

### 5.1 Map Graph 数据结构

```python
class Node:
    """Intersection / endpoint"""
    id: int
    lat: float
    lon: float

class Edge:
    """Road segment between two nodes"""
    id: int
    from_node: int
    to_node: int
    length_m: float
    max_speed_kmh: int          # speed limit
    type: str                    # 'highway' / 'arterial' / 'local'
    turn_restrictions: list     # 不允许转弯 (e.g. no left)
    one_way: bool
    
class CurrentTraffic:
    """Real-time overlay"""
    edge_id: int
    avg_speed_5min: float        # 实际平均速度
    last_updated: timestamp
```

**存储**：Spatial DB (PostGIS) 或专门 graph DB。OSM 原始数据 + 内部 enrichment。

### 5.2 Routing 算法

**Dijkstra (朴素)**:

```python
def dijkstra(graph, source, target):
    dist = {source: 0}
    heap = [(0, source)]
    while heap:
        d, u = heappop(heap)
        if u == target: return d
        for edge in graph[u]:
            new_dist = d + edge.cost
            if new_dist < dist.get(edge.to, inf):
                dist[edge.to] = new_dist
                heappush(heap, (new_dist, edge.to))
```

复杂度 O((V+E) log V)。1B node → 几分钟。**太慢**。

**A*** (Dijkstra + heuristic):

```python
def heuristic(node, target):
    """Great-circle distance（最快可能）"""
    return haversine(node, target) / MAX_SPEED

# Priority = dist + heuristic
heappush(heap, (dist[u] + heuristic(u, target), u))
```

A* prefer 朝目标方向扩展，剪枝大。但仍 O(big graph)。

**Contraction Hierarchies (CH)**:

预处理 → query O(log² N)，1000x 比 Dijkstra 快。

```python
# Preprocessing (几小时 once)
order = compute_node_order(graph)  # 按 importance
for node in order:
    add_shortcuts(graph, node)
    contract(graph, node)

# Query (1ms)
def ch_query(start, end):
    # Bidirectional A* in CH graph
    # Only traverse "upward" edges (lower-importance → higher-importance)
    return bidirectional_a_star(ch_graph, start, end)
```

工业 OSRM / Google Maps 真用。

### 5.3 实时 traffic 集成

```python
# 收集 GPS pings
def on_gps_ping(user_id, lat, lon, ts, speed):
    # Map-match: GPS → 最近的 edge
    edge_id = map_match(lat, lon)
    # 写 Kafka
    kafka.produce('gps.pings', {
        'edge_id': edge_id,
        'speed': speed,
        'ts': ts,
        'user_anon': hash(user_id),  # 匿名化
    })

# Stream processor
gps_pings
  .key_by(edge_id)
  .window(SlidingWindow(5min, 1min))
  .aggregate(avg_speed)
  .sink(redis_edge_speed)

# Routing 读 Redis
def edge_cost(edge_id):
    current = redis.get(f'speed:{edge_id}') or edge.max_speed_kmh
    return edge.length_m / current
```

**Anonymization**：用户隐私重要，GPS data 必须匿名化 (没有 user_id 关联，只看 edge 级聚合)。

### 5.4 ETA Prediction

```python
class ETAModel:
    def __init__(self):
        self.gbm = lightgbm.Booster.load('eta_model.txt')
    
    def predict(self, route_edges, current_time):
        eta = 0
        for edge in route_edges:
            features = self._build_features(edge, current_time)
            edge_time = self.gbm.predict(features)
            eta += edge_time
        return eta
    
    def _build_features(self, edge, t):
        return {
            'edge_length': edge.length,
            'edge_type': edge.type,
            'speed_limit': edge.max_speed,
            'current_speed': get_current_speed(edge),
            'hour': t.hour,
            'weekday': t.weekday(),
            'historical_avg': self.history[edge.id][t.hour][t.weekday()],
            'weather': get_weather(edge.location),
            'event_nearby': check_events(edge.location, t),
        }
```

Retrain 周期：每 5-15 分钟用最新数据训练（fast feature drift in traffic）。

### 5.5 Re-routing 流程

```python
# Mobile app every 30s
def on_location_update(current_loc, current_route):
    # 1. 是否偏离 route
    if distance(current_loc, current_route.nearest_point) > 100m:
        new_route = routing.compute(current_loc, dest)
        notify("Re-routing")
    
    # 2. 是否前方 traffic 变差
    remaining = current_route.remaining_edges()
    current_eta = eta_model.predict(remaining)
    if current_eta > original_eta * 1.2:  # 20% 慢
        alt_route = routing.compute(current_loc, dest)
        if alt_route.eta < current_eta * 0.9:  # alt 快 10%+
            suggest("Alternate route saves 5 min")
```

**注意**：不能太频繁建议重路 —— 用户烦。Threshold 至少 5 分钟差异才提示。

### 5.6 Tile 系统

```
Tile naming convention (Slippy Map):
  z = zoom level (0-18)
  x = column
  y = row
  
  URL: /tiles/{z}/{x}/{y}.png 或 .pbf (vector)
```

每 tile 预渲染。每次 OSM 数据 update → 增量 re-render 受影响 tile。

**Vector tile format (MapBox / OSM)**：

```
.pbf (Protocol Buffer encoding):
  layers: [
    {name: "roads", features: [...]},
    {name: "buildings", features: [...]},
    {name: "labels", features: [...]},
  ]
```

Client (Mobile / Web) 用 OpenGL / Canvas 渲染。

### 5.7 POI Search

```
Index: Elasticsearch
  fields: name, category, lat, lon, address, popularity
  Geo-index: geo_point

Query example:
  POST /search
  {
    "text": "starbucks",
    "near": {"lat": 37.4, "lon": -122.0, "radius_km": 5},
    "sort": ["distance", "popularity"]
  }
```

ES native `geo_distance` filter + scoring。

### 5.8 Offline mode

```
User downloads region (e.g. "San Francisco Bay Area"):
  - Map tiles (vector, ~50 MB)
  - Routing graph (subset, ~100 MB)
  - POI database (~20 MB)
  
Total: ~200 MB per region
```

Mobile app 本地 Dijkstra (smaller graph 足够)。No traffic update offline.

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - Driving / walking / transit?
  - Real-time traffic?
  - Offline?
  - Scale

0:05 - 0:10  Capacity Estimation
  - 200k routing QPS
  - 200k GPS pings/sec
  - 167k tile QPS

0:10 - 0:15  High-Level Architecture
  - Routing (CH)
  - Traffic (GPS → Kafka)
  - ETA (ML)
  - Tiles (CDN)

0:15 - 0:30  Deep Dive
  ★ CH preprocessing + query
  ★ Real-time traffic aggregation
  ★ ETA ML features
  ★ Vector tile + CDN

0:30 - 0:38  Follow-ups
  - Re-routing logic
  - Anonymization
  - Multi-modal (transit)

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK Maps system。先 clarify：driving first，offline support，real-time traffic 有。
> 
> 估算：1M concurrent × 路线请求 / 5min ≈ 200k QPS。Naive Dijkstra 1B node 几分钟 → 不可能。所以 **核心是 routing 预处理算法**。
> 
> 整体架构：(1) Routing service 用 Contraction Hierarchies 预处理过的 graph，query 1ms；(2) Traffic service 收 GPS pings 聚合 per-edge speed；(3) ETA ML 模型；(4) Tile + CDN serving 地图渲染；(5) POI ES index。
> 
> Deep dive routing：CH 是关键 idea。预处理（几小时一次）按 importance 排 node，contract 时加 shortcut edge。Query 用 bidirectional A* 在 CH graph 只走 'upward' 边。Highway 这种 important 节点更高 priority，几跳就跨越大距离。比 Dijkstra 快 1000x。
> 
> Traffic：phone GPS 每 5 秒报 location，Kafka topic 收，Flink keyBy edge_id 用 5min sliding window 算 avg speed → Redis 存。Routing service 用 Redis 当 cost factor。User 必须 opt-in，数据匿名化 (没有 user_id)。
> 
> ETA：朴素 sum(len/speed) 不准。ML 模型 features 含 current_speed + hour-of-day pattern + weather + 历史 baseline。每 5 min retrain。Google 实测 < 3% error。
> 
> Tile：vector .pbf format (~比 raster 小 5x)，CDN cache immutable。Client 客户端渲染 (theme 切换不必重 download)。
> 
> Re-route：每 30 秒检测偏离 + 前方 traffic 变差。Alt route 快 10%+ 才建议（避免过度提示）。
> 
> 想 deep dive CH preprocessing 还是 ETA ML?"

---

## 8. Follow-up 演练

### Q1: CH preprocessing 怎么做？

**答**：
- 按 "importance score" 排 node（heuristic: degree, betweenness, edge difference）
- 从 lowest-importance 开始逐一 contract
- Contract node v：移除 v，对每对邻居 (u, w)，如果 v 是 u→w 最短路径上 → 加 shortcut edge (u, w, dist) 替代
- 维护 contraction order (low → high)
- Query 时 bidirectional：from start 只走"to higher rank" edges, from end 只走"from higher rank" edges

复杂度：preprocessing O(N log² N)，query O(log² N)。

### Q2: 如果 user GPS 不连续 (隧道 / NAT)？

**答**：Map-matching algorithm。即使 GPS 跳跃，HMM-based map matching 推断"用户在 edge X 上"。如果某段没 GPS 数据，fallback 到历史平均 / speed limit。

### Q3: 怎么处理跨国家边界？

**答**：每 country / region 独立 graph + ETA model（驾驶习惯 / 法规 / 限速制不同）。跨境路线在 border 节点拼接 (joint graph)。

### Q4: 实时事故 / 道路施工怎么处理？

**答**：
- 政府 / 第三方 feeds (Waze 也是用户报告)
- 用户报告 (in-app "我看到事故")
- Anomaly detection on edge speed drop
- Edge cost: 临时 * 大系数 (driver 绕开)

### Q5: 离线 routing 怎么实现？

**答**：用户下载 region (tiles + sub-graph + POI ~200 MB)。Mobile 端 Dijkstra/A* (smaller graph 够)。No traffic。Re-online 后传输离线产生的 GPS 数据。

### Q6: ETA 加 weather 模型怎么训练？

**答**：历史数据：weather conditions + actual travel time。模型学到 "rain → speed -20%, snow → -50%"。Real-time weather API feed in query。

### Q7: 怎么 prevent 用户 GPS data 反推个人？

**答**：
- 不带 user_id 进 Kafka，hash 替代
- Pings 只 keep 7 day raw，then aggregate to edge level
- DP (differential privacy) 加 noise
- Aggregation 至少 K 个用户才算 (k-anonymity)

---

## 9. 常见易错点

> [!pitfall]
> ❌ **朴素 Dijkstra on 1B graph** —— 几分钟，不可用；  
> ❌ **不用预处理 (CH/CRP)** —— query 慢 1000x；  
> ❌ **ETA 用 speed limit** —— 不准，必须实际 speed；  
> ❌ **GPS 不匿名化** —— 隐私 / 法规风险；  
> ❌ **Tile 不 CDN** —— origin QPS 爆；  
> ❌ **频繁 reroute alert** —— 用户烦，5min+ diff 才提；  
> ❌ **静态 ETA model** —— traffic pattern 季节 / 工作日变化，要 retrain；  
> ❌ **离线 graph 太大** —— 几 GB 用户不愿下载；分 region 切。

---

## 10. 加分项

- **Customizable Routes** (CRP): 比 CH 更新（Microsoft / BMW），支持动态 edge cost change 不重 preprocess
- **3D / AR navigation**: 楼层 navigation + 摄像头实景指引
- **Multi-modal**: driving + transit + walking 混合 trip
- **Carpool / Ride share routing**: multi-stop TSP heuristics
- **EV-aware routing**: 电动车考虑充电桩位置 + 电量
- **Truck routing**: 桥高 / 重量 限制
- **Privacy-first**: differential privacy on aggregations
- **Crowd-sourced POI**: 用户提交新 POI + 审核

---

## 11. 总结：你应该记住的 3 件事

1. **Contraction Hierarchies 是大规模 routing 的标配**。1B node graph 不可能朴素 Dijkstra，CH 让 query 从分钟级降到毫秒级。能解释 contract + shortcut 的原理是面试加分。

2. **实时 traffic 是 ETA 准确的灵魂**。crowdsourced GPS + 5min sliding window aggregation + ML 模型，是 Google / Waze 实战。

3. **CDN + vector tile** 让地图加载丝滑。Pre-render + edge cache + immutable URL 是 web map 的标配。Mobile 也是同套思路（download tile to disk）。

> [!followup]
> **学习推荐**：(a) 跑 OSRM (Open Source Routing Machine) 本地体验 CH；(b) 读 Geisberger et al. "Contraction Hierarchies" paper；(c) 看 MapBox vector tile spec；(d) 学 PostGIS 做地理 query；(e) 思考"为什么 Waze 比 Google Maps 给的 ETA 经常不一样" (data source / aggregation 不同)。
