## 题目本质

设计 **system to display aggregation of events where multiple robots are continuously generating events in real-time** —— 工厂 / 仓库里数百个 robot 每秒产生 events（位置 / 任务进度 / error）。Dashboard 实时显示**聚合视图**。

类似 IoT telemetry 系统。

## 需求

- 1000+ robots
- 每 robot 10-100 events/sec
- Dashboard < 5 sec lag
- Filter by zone / type / status
- Historical replay

## 整体架构

```ascii
   Robots (1000)
       │ MQTT / gRPC stream events
       ▼
  ┌──────────────┐
  │ Ingest GW    │  edge servers per facility
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Kafka        │  per-zone partition
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Stream Processor │  Flink: 1s tumbling agg
  │ (aggregate)      │  per zone / per robot type
  └──┬───────────┬───┘
     │           │
     ▼           ▼
  ┌──────┐  ┌──────────────┐
  │ Redis│  │ TSDB         │  historical
  │ live │  │ (InfluxDB)   │
  │ agg  │  └──────────────┘
  └──┬───┘
     │
     ▼
  Dashboard (WebSocket subscribe)
```

## 核心组件

### 1. Ingest

Robots 用 MQTT (低 bandwidth IoT 标准) push event。Edge GW 接收，batch + forward to Kafka。

### 2. Event schema

```json
{
  "robot_id": "R-001",
  "zone": "warehouse-A",
  "ts": 1234567890,
  "type": "position" | "task" | "error",
  "payload": {...}
}
```

### 3. Aggregation

Flink 1-second tumbling window:
- Per zone: active_robot_count, error_count, avg_position
- Per robot type: ...
- 加权: avg / max / count / histogram

Output to Redis (live) + InfluxDB (historical)。

### 4. Dashboard

WebSocket subscribe Redis pub/sub channel "agg.zone.warehouse-A"。每秒 push update。

Visualizations:
- Heatmap of robot positions per zone
- Error rate timeseries
- Per-robot detail panel (click drill-down)

### 5. Drill down

Click a zone → detailed view → query per-robot recent events from InfluxDB (last 5 min full event log)。

### 6. Replay

User selects time range "yesterday 2-3 PM"。Server replays InfluxDB events at 10x speed back to UI。

### 7. Alert

Stream processor sets rule:
- error_count > 10/min in zone → alert
- robot_idle_time > 30s → maintenance check
- position out_of_bounds → safety alert

Alert push to PagerDuty / Slack。

### 8. 数据压缩

Robot position 每 100ms 报送 raw 浪费。Delta-encoded position：只发与上次差异。Server 还原 full state。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Transport | MQTT | HTTP：开销大 |
| Aggregation | Flink stream | Batch：lag 大 |
| Live store | Redis pub/sub | DB poll：慢 |
| Historical | TSDB | RDBMS：write 慢 |
| Compression | Delta encoding | Raw：bandwidth 浪费 |

## 容量估算

- 1000 robots × 50 events/sec = 50k events/sec
- Aggregation per 1s × 10 zones = 10 outputs/sec → trivial
- Storage: 50k × 100B = 5 MB/sec raw → InfluxDB compressed ~1 MB/sec → 86 GB/day

## 易错点

> [!pitfall]
> ❌ HTTP POST per event → 网络 overhead 爆；
> ❌ 全 raw event 推 dashboard → 浏览器死；
> ❌ Aggregation 在 dashboard 端做 → 数据传量大；
> ❌ 不区分 alert vs metric → alert latency 高；
> ❌ Replay 实时计算 → 慢。

> [!key]
> 三大要点：(1) **MQTT + Kafka + Flink** 经典 IoT stack；(2) **Tumbling agg + Redis live + TSDB historical**；(3) **Delta encoding + sampling** 节省 bandwidth。

> [!followup]
> "1000 → 10000 robots？" → kafka partition + flink parallelism scale 即可；"Robots 之间互通信？" → P2P + edge consensus；"AR 显示 robot 实时位置（superimpose on camera feed）？" → unity SDK + WebSocket。
