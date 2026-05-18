## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Robot / IoT device** | 工厂/仓库里实时上报状态的机器 | 工人不断打卡 + 报进度 |
| **Telemetry** | 设备上报的数据流 (位置/电池/状态) | 工人随时汇报 |
| **Time-series data** | 按时间戳排序的数据 | 心电图 |
| **TSDB (InfluxDB / TimescaleDB / ClickHouse)** | 专为时序优化的 DB | 心电图专用记录纸 |
| **Stream processing (Flink / Kafka Streams)** | 实时处理无限数据流 | 流水线工人 |
| **Tumbling window** | 不重叠的时间窗 (e.g., 1 min) | 钟表分针一格 |
| **Sliding window** | 重叠的时间窗 (e.g., last 5 min, slide every 1 min) | 缓行车的视野 |
| **Downsampling** | 老数据降精度 (秒级 → 分钟级) | 老报表只保留每日总数 |
| **Retention policy** | 数据保留多久 | "三年内的报表不丢" |
| **Aggregation** | 求和 / 平均 / 计数 | 月销售总额 |
| **Dashboard** | 实时可视化界面 | 工厂中控室大屏 |
| **Alerting** | 异常时报警 | 工厂报警铃 |
| **MQTT** | 轻量级 IoT 协议 | IoT 设备的"短信" |
| **Edge computing** | 数据在设备端先聚合再上传 | 工厂本地先合并报告 |

---

## 1. 题目本质

**Event Aggregation for Robots** = 工厂 / 仓库中数百到数万个 robot 每秒产生 events，**实时聚合 + 显示 dashboard + 报警**。

**典型产品**：
- **AWS IoT Core / Azure IoT Hub** —— cloud IoT platform
- **Grafana + InfluxDB / Prometheus** —— monitoring 标杆
- **Splunk / Datadog** —— enterprise observability
- **Amazon FBA warehouse robots** —— Kiva robots 监控
- **Tesla autopilot fleet** —— 车辆遥测
- **Industry 4.0** —— smart factory

**为什么这是 STAFF 题**：

考的是 **IoT pipeline architecture**:

1. **High-volume ingestion** (1k robots × 10 events/sec = 10k events/sec)
2. **Time-series storage** 选型
3. **Stream aggregation** for real-time dashboard
4. **Downsampling + retention** for long-term storage
5. **Multi-tenancy** (多客户 / 多 site)

考 STAFF 关键：**完整 IoT/observability stack**，不只是 "events 存 DB"。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `IngestEvent(robot_id, timestamp, metrics)` | 设备上报 |
| `GetCurrentState(robot_id) -> state` | 当前状态 |
| `GetTimeSeries(robot_id, metric, range) -> data[]` | 历史曲线 |
| `GetAggregated(facility, range, granularity) -> data` | 聚合视图 |
| `SetAlert(metric, threshold)` | 设置报警 |
| `Subscribe(facility) for dashboard` | 实时 dashboard 订阅 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Ingestion rate** | 100k events/sec (10k robots × 10 Hz) |
| **End-to-end latency** | < 5 s (event → dashboard) |
| **Dashboard update** | 1 Hz refresh |
| **Storage** | 1 year hot + 5 years cold |
| **Retention** | raw 7 days, 1-min agg 1 year, 1-hour agg 5 years |
| **Multi-tenancy** | 1000 facilities, isolated |
| **Alerting** | < 30 s from anomaly to notification |

---

## 3. 容量估算

- 10k robots × 10 events/sec × 100 B = **100 MB/sec raw** = **8.6 TB/day**
- 7 days hot raw: 60 TB
- 1-min agg: 10k robots × 1440 min/day × 100 B = 14 GB/day × 365 = **5 TB/year**
- 1-hour agg over 5 years: 0.2 TB total

Total cold storage: ~10 TB / facility / 5 years. With 1000 facilities: 10 PB total.

---

## 4. 高层架构

```
┌───────────────────────────────────────┐
│  Robots (10k devices × 10 Hz)          │
└───────────────────────────────────────┘
              │ MQTT / HTTP / WebSocket
              ↓
┌───────────────────────────────────────┐
│  IoT Gateway / Ingestion Layer        │
│   - Authenticate + rate limit          │
│   - Validate + enrich (facility_id, etc)│
└───────────────────────────────────────┘
              │
              ↓
┌───────────────────────────────────────┐
│  Kafka (partition by facility_id)      │
└───────────────────────────────────────┘
              │
              ├──── Stream Processor (Flink) ──→ Aggregation Store (Redis/Druid)
              │                                ├── Per-robot current state
              │                                └── Per-facility 1-min aggregates
              │
              ├──── Raw Sink ──→ Time-series DB (InfluxDB / ClickHouse)
              │
              └──── Alert Engine ──→ Notification (Slack/Email/PagerDuty)

              ↓
┌───────────────────────────────────────┐
│  Dashboard Service                     │
│   - WebSocket subscriptions            │
│   - Real-time chart updates            │
└───────────────────────────────────────┘
```

### Step 1: Ingestion

Devices push events via MQTT (lightweight, QoS 1):
- Robot connects to MQTT broker
- Publish to topic `facility/{site_id}/robot/{robot_id}/events`
- Broker (Mosquitto / EMQX / AWS IoT Core) routes to backend

**Why MQTT over HTTP**:
- Persistent connection (省 TCP handshake)
- Low overhead (binary protocol)
- QoS levels (0=fire-forget, 1=at-least-once, 2=exactly-once)

### Step 2: Stream processing (Flink)

Flink job consumes Kafka:

```python
events
  .keyBy(robot_id)
  .timeWindow(Time.minutes(1))
  .aggregate(MinMaxAvg)  # 1-min agg per robot

events
  .keyBy(facility_id)
  .timeWindow(Time.seconds(10))
  .aggregate(EventCount, AverageHealth)  # facility-level

events
  .filter(temperature > 80)
  .keyBy(robot_id)
  .reduce(triggerAlert)  # alert rule
```

### Step 3: Storage layers

- **Hot (last 7 days raw)**: InfluxDB / ClickHouse
- **Warm (1-year 1-min agg)**: InfluxDB downsampled
- **Cold (5-year 1-hour agg)**: S3 Parquet
- **Current state (latest event per robot)**: Redis Hash

### Step 4: Dashboard

```
Browser opens dashboard
  → WebSocket to Dashboard Service
  → subscribe(facility_id)
  → Stream of aggregated events from Redis pub/sub
  → Browser renders chart (D3 / Recharts)
```

**Update rate**: 1 Hz (every second). For historical view (last 24h chart): query InfluxDB on dashboard open, then live updates via WebSocket.

### Step 5: Alerting

Alert rules in YAML:
```yaml
- name: high_temperature
  metric: robot.temperature
  condition: avg over 5min > 80
  action: notify @ops via PagerDuty
```

Flink applies rules → when fires → Kafka topic `alerts` → Notification service.

---

## 5. 组件深挖

### Deep Dive 1: MQTT at Scale

100k events/sec from 10k robots:
- Single MQTT broker: ~100k connections, 100k QPS
- Cluster: EMQX / VerneMQ (Erlang BEAM 原生 high connection)
- **Sharded topic**: `facility/{site}/robot/{id}` natural sharding

**Authentication**: cert-based (each robot has client cert) or token-based with rotation.

### Deep Dive 2: Time-Series DB Choice

| DB | 优势 | 劣势 |
|---|---|---|
| **InfluxDB** | Easy, popular, native TSDB | Single-node oss, paid for cluster |
| **TimescaleDB** | Postgres-based, SQL friendly | Less optimized than pure TSDB |
| **ClickHouse** | Insane analytics speed, columnar | Not pure TSDB, harder ops |
| **Prometheus** | Pull-based, k8s native | Local storage, scaling hard |
| **VictoriaMetrics** | Prom-compatible, durable | Newer |
| **Druid** | Real-time + historical hybrid | Complex ops |

**STAFF 答**：
- 小规模 (< 1M points/s): InfluxDB
- 大规模 + analytics: ClickHouse
- k8s monitoring: Prometheus + VictoriaMetrics

### Deep Dive 3: Downsampling Pipeline

Hot 7 days raw → after 7 days, downsample to 1-min, drop raw。

**Flink continuous query**:
```
window_1m = events.window(1 min).aggregate()
write window_1m to storage_warm

after 7 days: 
  raw deleted (InfluxDB retention policy)
  warm 1-min retained 1 year
  
after 1 year:
  warm 1-min → downsample to 1-hour → cold storage
```

**Compression**: Parquet for cold (~10× compression on time-series).

### Deep Dive 4: Real-time Dashboard via WebSocket

Browser connects WebSocket, subscribes to `facility_id` channel.

**Server side**:
- Maintain map: WebSocket connection → facility filter
- Redis pub/sub: stream processor publishes 1-Hz aggregated update to `facility.{id}` channel
- Dashboard Service subscribe → fan-out to all connected WebSockets

**Scaling**: 1 facility might have 100 dashboard users. 1000 facilities × 100 = 100k WebSocket → 1 Dashboard Service node holds.

### Deep Dive 5: Alert Engine

Rule types:
1. **Threshold**: metric > X for Y duration
2. **Rate of change**: derivative > X
3. **Composite**: A AND B AND NOT C
4. **Anomaly**: ML-based (z-score, isolation forest)

**Evaluate**:
- Flink job per rule, on relevant key (robot_id / facility_id)
- On firing: deduplicate (don't spam for same alert), notify

**Dedup**:
- Alert state machine: ACTIVE / RESOLVED
- Re-firing within 5 min of ACTIVE → suppress
- After RESOLVED, can re-fire

### Deep Dive 6: Multi-tenancy

1000 facilities (different customers), data must isolate:

- Kafka topic partition by `tenant_id`
- TSDB schema: `metric, tenant_id, robot_id, timestamp, value`
- Query API: enforce tenant from auth token
- Resource quota per tenant (ingestion rate, storage)

### Deep Dive 7: Edge Aggregation

If robots have low bandwidth (e.g., mobile / IoT):

- Robot **local pre-aggregates** every 10s (instead of 10Hz raw)
- Upload 1 row per 10s = 100× reduction
- Trade-off: dashboard granularity reduced to 10s vs 100ms

**Edge compute** (AWS Greengrass, Azure IoT Edge): run code on-device for filtering/aggregation。

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：how many robots, event rate, dashboard granularity, retention |
| 5-10min | 容量：100k events/sec, 8.6 TB/day raw, 7d hot + 5y cold |
| 10-15min | API + protocol (MQTT vs HTTP) |
| 15-25min | 高层架构：MQTT → Kafka → Flink → TSDB + dashboard via WS |
| 25-40min | Deep dives: TSDB choice / downsampling / dashboard WS / alerting / edge |
| 40-45min | multi-tenancy / cost optimization |

---

## 7. 样板讲解稿

> 这是经典 **IoT telemetry pipeline**，4 个 stage：ingest → process → store → display.
>
> **架构**：
> 1. Robots → **MQTT** broker (省连接 + 低开销) → ingestion layer (auth + enrich)
> 2. **Kafka** (partition by facility_id) decouples ingest 跟 processing
> 3. **Flink** stream processor:
>    - 1-min aggregates per robot
>    - 10-s facility-level aggregates
>    - Alert rule evaluation
> 4. Storage layered:
>    - Redis: per-robot current state
>    - InfluxDB / ClickHouse: 7 days raw
>    - Downsample to 1-min retain 1 year
>    - 1-hour Parquet to S3 for 5 years
> 5. **Dashboard**: WebSocket subscribe + Redis pub/sub fan-out
> 6. **Alerting**: Flink rule evaluator → PagerDuty
>
> **Multi-tenancy**: per-facility partitioning + tenant-aware queries.
>
> **Edge optimization**: pre-aggregate on robot if bandwidth tight.
>
> Numbers: 10k robots × 10Hz = 100k events/sec, 8.6 TB/day raw, end-to-end < 5s。

---

## 8. Follow-up Q&A

### Q1: "为什么 MQTT 不 HTTP?"

**A**：
- MQTT 持久连接，避免每次 TCP/TLS handshake (~100ms savings/req)
- Binary protocol (2-byte header) vs HTTP (hundreds of B header)
- QoS levels for delivery guarantee
- 100k connections per broker (HTTP 重 in this density)

### Q2: "InfluxDB vs ClickHouse 选哪个？"

**A**：
- **InfluxDB**: simple ops, easy to start, line protocol natural fit
- **ClickHouse**: 10× faster analytics, but more complex ops + needs more expertise

Small to medium scale: InfluxDB. Large analytics (billion-row scans): ClickHouse.

### Q3: "Dashboard 1 Hz 刷新，怎么实现？"

**A**：
- WebSocket to Dashboard Service
- Dashboard Service subscribes Redis pub/sub channel `facility.{id}`
- Flink writes 1-Hz aggregated metric to Redis (`SET facility:{id}:cpu_avg value` + `PUBLISH facility.{id} value`)
- Dashboard Service push to WebSocket

### Q4: "下载 24h 历史曲线，1M data points 怎么不卡？"

**A**：
- Server-side downsample for query (24h × 100Hz = 8.6M points → reduce to 1440 × 60 = 86k points at 1-min granularity)
- Client renders only visible viewport (virtual scrolling for table)
- Lazy load older points on zoom

### Q5: "Alert 怎么避免 spam (一秒发 100 个 'CPU > 80%' alert)？"

**A**：
- Alert state machine (ACTIVE / RESOLVED)
- Notify only on state transition (FIRING / RESOLVED)
- Throttle: max 1 notification per 5 min for same alert
- Grouping: aggregate similar alerts (10 robots overheating → 1 notification "10 robots in zone X overheated")

### Q6: "如果 robot 网络断了，event 丢吗？"

**A**：
- Local buffer on robot (last 10 min)
- Reconnect → flush buffer
- MQTT QoS 1 (at-least-once)
- Server dedup by `event_id` if seen
- Mark "stale data" on dashboard if robot offline > N minutes

### Q7: "1000 facilities，1 facility 突然 burst 100x events？"

**A**：
- Per-tenant rate limit at ingestion layer
- Kafka backpressure: producer slows down if topic lag > X
- Auto-scale Flink: parallelism scale with input rate
- Cost alert: notify customer if burst exceeds plan tier

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **Use Postgres / generic DB** for time-series → 1B points 查不动
2. **忽略 downsampling** → 5 年 raw 几十 PB
3. **HTTP for ingestion** → connection overhead at scale
4. **没考虑 multi-tenancy** → data leak across customers
5. **Dashboard 拉所有 raw** → 浏览器 OOM
6. **Alert no dedup** → notification storm
7. **Single broker MQTT** → bottleneck

### ✅ 加分项

1. **MQTT + EMQX/VerneMQ** at scale
2. **Flink for stream processing**
3. **Layered storage** (Redis / TSDB / S3)
4. **Continuous downsampling** with retention policies
5. **Redis pub/sub for dashboard fan-out**
6. **Edge aggregation** for bandwidth-constrained robots
7. **Alert state machine** with grouping
8. **Tenant isolation + quota** for multi-tenant

> [!key] STAFF vs SENIOR：能说出 **MQTT + Flink + InfluxDB + downsampling + WS dashboard** 完整 stack 是 STAFF；只说 "events → DB → dashboard" 是 SENIOR。

---

## 10. Cheat Sheet

```
Pipeline 4 stages:
  Ingest: MQTT → IoT Gateway → Kafka
  Process: Flink (per-robot 1-min agg, facility 10s agg, alert rules)
  Store:
    Redis: current state per robot
    InfluxDB/ClickHouse: 7d raw
    Downsample 1-min → 1y
    1-hour Parquet S3 → 5y
  Display: Dashboard Service WebSocket + Redis pub/sub

Storage retention:
  Raw 100Hz: 7 days
  1-min agg: 1 year
  1-hour agg: 5 years
  Cost ~$1/GB/year for cold, ~$30/GB for SSD

Tech choices:
  Ingestion: MQTT (EMQX/VerneMQ broker)
  Queue: Kafka
  Processing: Flink (better than Kafka Streams for windowing)
  TSDB: InfluxDB (simple) / ClickHouse (analytics)
  State: Redis Hash
  Dashboard: WebSocket + Redis pub/sub

Alerting:
  Rule engine in Flink
  State machine: ACTIVE/RESOLVED
  Dedup + grouping
  Output: PagerDuty / Slack / email

数字:
  10k robots × 10 Hz = 100k events/sec
  100 B/event = 100 MB/sec = 8.6 TB/day
  End-to-end latency < 5 s
  Dashboard 1 Hz refresh
  1000 facilities multi-tenant
```
