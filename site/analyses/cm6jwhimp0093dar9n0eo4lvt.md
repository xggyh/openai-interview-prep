## 题目本质

设计 **Server Health Monitoring System**：监控数千 / 数万服务器的健康状况（CPU/mem/disk/network/process）+ alert + dashboard + historical trend.

Google 报告 7 次。考点：**time-series ingestion + storage + alerting + visualization**。

## 需求拆解

- 50k servers，每 10 秒报 metrics
- Metric 种类：~50 per server
- Alert latency < 1 minute
- 历史保留：1 个月精细 + 1 年聚合
- 99.99% available

## 整体架构

```ascii
    Servers (50k)
       │  agent on each: push or pull
       ▼
  ┌──────────────┐
  │ Collector    │  Prometheus pull / OTel push
  │ (regional)   │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Kafka            │  topic: metrics.raw
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Stream Processor │  Flink: aggregate to 10s/1m/1h/1d
  └──┬───────────┬───┘
     │           │
     ▼           ▼
  ┌──────┐  ┌─────────────┐
  │ TSDB │  │ Alert       │
  │ (Prom│  │ Engine      │
  │  /   │  │ (rules eval)│
  │ Vict.│  └──────┬──────┘
  │ Met.)│         │
  └──┬───┘         ▼
     │       ┌─────────────┐
     │       │ PagerDuty / │
     │       │ Slack alert │
     │       └─────────────┘
     ▼
  Grafana dashboard
```

## 核心组件

### 1. Collection 模式：Pull vs Push

**Prometheus pull**：collector 定期 scrape `/metrics` endpoint
- 优点：发现 stale / dead server 容易（scrape failed）
- 缺点：firewall / NAT 后的 server 麻烦

**Push** (OpenTelemetry / StatsD)：agent 主动 push
- 优点：穿透 firewall
- 缺点：dead server 不知道是 dead 还是 silent

实战：**hybrid** —— 内部 server pull，edge / mobile push。

### 2. TSDB

需求：write-heavy, time-ordered query。专用 time-series DB：
- **Prometheus**：单机 limit，需 federation
- **VictoriaMetrics**：高写入 throughput
- **Thanos**：长期存储 + Prometheus 协调
- **InfluxDB**：商业 + 复杂查询
- **TimescaleDB**：Postgres extension，SQL friendly

每 metric 是 series = (metric_name + labels)，时间序列。

### 3. Multi-resolution

```
10 秒精度 → 保留 1 天 (downsample 后丢)
1 分钟精度 → 7 天
5 分钟精度 → 1 月
1 小时精度 → 1 年
```

Flink job 每分钟从 raw 计算 aggregations 写入对应 retention level。Query 时按时间范围选 resolution。

### 4. Alert engine

Rule format（PromQL 风格）:

```
alert: HighCPU
expr: avg_over_time(cpu_usage{job="prod"}[5m]) > 0.9
for: 5m
labels:
  severity: page
annotations:
  summary: "CPU > 90% for 5 min on {{ $labels.instance }}"
```

每 30 秒 evaluate rules → 触发 alert send to PagerDuty / Slack。

**Anti-flapping**：`for: 5m` 要求条件持续 5 分钟才 alert，避免抖动。

### 5. Visualization

Grafana：dashboard 由 panels 组成，每 panel = PromQL query + viz config。
- Live update via WebSocket
- Drill-down：点击 server → 详细 panel

### 6. Anomaly detection (ML)

Static threshold (CPU > 90%) 太粗。加 ML model:
- Per-metric 历史 baseline (mean ± stddev by hour-of-day)
- 当前 vs baseline > 3σ → anomaly
- ML detect "异常 patterns" without explicit threshold

### 7. SLO + Error Budget

定义 SLO：99.9% successful requests in 30-day rolling。
- Error budget = 0.1% = 43.8 minutes / month
- Burn rate alert：当前燃烧速度预测 24h 内耗尽 budget → 立即 alert

### 8. Multi-region

每 region 独立 collector + TSDB。Global query 通过 Thanos / federation。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Collection | Hybrid pull/push | 单一 pull：NAT 不友好 |
| TSDB | VictoriaMetrics / Prometheus | Generic DB：write 慢 |
| Alert | Rule + ML anomaly | Threshold only：粗糙 |
| Storage | Multi-resolution | Single：成本爆 |
| Multi-region | Per-region + federation | Single global：跨洋慢 |

## 容量估算

- 50k servers × 50 metrics × 1/10s = 250k metrics/sec
- 250k × 30s evaluation interval = 7.5M evaluations / 30s for alerts
- Storage：250k × 16 bytes × 86400 = 350 GB/day raw → downsample 后 50 GB/day

## 易错点

> [!pitfall]
> ❌ 静态 threshold —— 不同 workload 不同 baseline；
> ❌ 不 dedupe alert —— 1 个 incident 收 100 条 page；
> ❌ Alert 不 escalate —— 1 个 page 没人接 → 漏；
> ❌ Cardinality 爆炸（每 request 都 unique label）—— TSDB 死；
> ❌ 不做 alert silence during deploy —— deploy 期间 noisy alert。

> [!key]
> 三大要点：(1) **Multi-resolution TSDB + downsample** 控成本；(2) **Rule + anomaly hybrid alerting** 避免 false positive；(3) **SLO + error budget** 把 alert 与 business value 对齐。

> [!followup]
> "如何 reduce alert fatigue？" → grouping, silencing, smart on-call rotation；"Distributed tracing 集成？" → metric / trace / log 三位一体 (OpenTelemetry)；"Auto-remediation？" → alert 触发 playbook script 自动 restart / scale；"Cost optimization？" → drop low-cardinality labels + sample 数据流。
