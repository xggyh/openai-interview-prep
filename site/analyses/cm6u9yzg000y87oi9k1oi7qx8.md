## 题目本质

设计 **Uber** 级 ride-hailing 平台：乘客 → 匹配司机 → 实时定位 → 计价 + 支付。1B+ users，多 region。

## 需求

- 乘客 request ride（pickup + drop-off）
- 系统匹配最近 driver
- 实时跟踪 location + ETA
- 完成后计费

## 整体架构

```ascii
   Rider App           Driver App
       │                  │
       │ location          │ location ping (5s)
       │ ride request      │ status (online/onroute/busy)
       ▼                  ▼
  ┌─────────────────────────────┐
  │   Location Service          │  S2 cell / geohash index
  │   (driver geo index)        │
  └──────────┬──────────────────┘
             │ nearby query
             ▼
  ┌─────────────────────────────┐
  │   Matching Service          │  优化 ride-driver pair
  └──────────┬──────────────────┘
             │
             ▼
  ┌─────────────────────────────┐
  │   Ride Service              │  ride lifecycle state
  └──────────┬──────────────────┘
             │
             ▼
  ┌─────────────────────────────┐
  │   Pricing + Payment         │
  └─────────────────────────────┘
```

## 核心组件

### 1. Location Service：地理索引

司机每 5 秒 push 位置。1M 在线司机 → 200k QPS。

数据结构：**S2 cells / H3 hexagon**（Uber 实际用 H3）：
- 把地球分成 hex cells (各 resolution)
- 司机 located at cell ID
- "附近 driver" 查询 = 取中心 cell + k-ring 邻居 → union 出 candidates

```python
# Redis GEO 或自建 H3 + Redis Set per cell
redis.geoadd('drivers', longitude, latitude, driver_id)
nearby = redis.geosearch('drivers', longitude, latitude, radius=2, unit='km')
```

### 2. Matching 算法

**朴素**：取最近的 K driver，选 ETA 最小者。问题：同时多 rider 抢同一 driver。

**Batched matching**：每 5 秒 batch all pending rides + all available drivers，跑**Hungarian / minimum-cost bipartite matching** 全局最优。

```
cost(rider, driver) = ETA(driver_pos → rider_pos) + driver_rating_penalty
```

batched 让全局更优（减少空驶 + 更短 wait）。

### 3. Ride state machine

```
requested → matched → en_route_pickup → in_progress → completed
             ↓ no driver
           cancelled
```

每 transition 写 DB + emit event。State stored in **strongly consistent DB**（Spanner / CockroachDB）。

### 4. Realtime tracking

WebSocket / SSE 把 driver 位置 push 给 rider。每 5 秒一次（不需要更高频）。

```
driver pings location → server → push to (rider in this ride)
```

### 5. Pricing

- Base fare + per-km + per-min
- **Surge pricing**：实时 demand / supply ratio per zone → 乘倍数
- 出发前 give estimate（用 Maps API ETA + distance）

### 6. Payment

完成后调 payment gateway。前 5 秒可 dispute（cancel before charge）。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Geo index | H3 + Redis | DB B-tree on (lat, lng)：慢 |
| Matching | Batched bipartite | Greedy per request：局部最优 |
| State | Strong consistency DB | Eventual：state confusion |
| Tracking | WebSocket 5s | Polling 1s：浪费电池 |
| Pricing | Real-time surge | Static：失 elasticity |

## 容量估算

- 1M concurrent rider + 500k driver
- Location ping QPS: 500k / 5s = 100k QPS
- Match QPS: peak 10k rides / sec
- DB writes: ride state changes, ~30k QPS peak

## 易错点

> [!pitfall]
> ❌ Greedy matching → 全局次优；
> ❌ Strong consistency 不重要 (state confusion 导致用户体验差)；
> ❌ Location 用 (lat, lng) DB query —— 慢；
> ❌ 每秒 ping —— 电池 + 流量爆；
> ❌ 不做 surge pricing —— supply / demand 失衡。

> [!key]
> 三大要点：(1) **H3 / S2 geo index** 处理大规模 nearby query；(2) **Batched bipartite matching** 全局最优；(3) **Strong consistency state machine** 防 race。

> [!followup]
> "Uber Pool (carpool)？" → multi-stop TSP，detour ≤ threshold；"自动驾驶 driver？" → driver pool 加 robotaxi subset，dispatch 算法区分；"国际 + 多 currency？" → per-region pricing engine + currency convert；"如何 prevent fraud (假乘客 / 假司机)？" → ML risk score + manual review。
