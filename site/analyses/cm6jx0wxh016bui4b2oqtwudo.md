## 题目本质

设计 **Logger System**：分布式应用产生 logs → ingest → store → query / alert / archive。100k+ services, 1PB+ logs/day。

## 需求

- 1M events/sec ingest
- 10s lag from emit to queryable
- 30 days hot search, 1 year cold archive
- Full-text search + filter by service / level / timestamp

## 整体架构

```ascii
   Apps
     │ stdout / structured log
     ▼
   ┌──────────────┐
   │ Log Agent    │  fluent-bit / Vector
   │ (on each box)│
   └──────┬───────┘
          │ batched, compressed
          ▼
   ┌──────────────┐
   │ Kafka        │  topic: logs.raw
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Indexer      │  → Elasticsearch / OpenSearch
   │ (write-heavy)│
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Hot tier     │  → ES cluster (last 30 days)
   └──────┬───────┘
          │ scheduled archive
          ▼
   ┌──────────────┐
   │ Cold storage │  S3 + Parquet
   └──────────────┘

   ┌──────────────┐
   │ Query API    │  → Kibana / custom UI
   └──────────────┘
```

## 核心组件

### 1. Agent

每 host run agent：
- Tail log files / capture stdout
- Parse 结构化（JSON）+ unstructured（regex / grok）
- Batch + compress + send to Kafka

Async + buffered，不阻塞 app。

### 2. Kafka 缓冲

Decouple agent / indexer。Indexer 慢时 Kafka 缓冲，不丢日志。

按 service 分 partition，保证同 service 日志顺序。

### 3. Indexer + ES

每条 log entry → ES document，按时间 daily index。每 service 一个 index alias。

ES 提供 full-text search + filter + aggregation。

但 ES 贵且不适合 PB 级长期存储 → **hot/cold tier 分离**。

### 4. Hot/Cold tier

- Hot (last 30 days): ES → instant search，秒级返回
- Cold (30 days - 1 year): S3 Parquet → batch query via Athena / Presto，分钟级

每天定时 job 把 31 天前数据从 ES export 到 S3 + drop ES index。

### 5. Query API

```
GET /logs?service=foo&level=error&from=...&to=...&query="connection refused"
```

按时间范围决定 hot vs cold：
- < 30 days: 查 ES
- > 30 days: trigger Athena query S3

### 6. Sampling for 高频

某些 service 1M log/sec，全存浪费。**Adaptive sampling**:
- DEBUG / INFO: 1% sample
- WARN: 10%
- ERROR / FATAL: 100%

但 always emit "sampling header" let downstream知道 sample rate。

### 7. PII Scrubbing

Agent / indexer 上做 PII regex（email / phone / credit card）→ redact 或 hash。Compliance 必备。

### 8. Alert integration

Log pattern 触发 alert：
- 1 分钟内 error > 100 → page on-call
- 特定 error signature → 立即 alert

通过 ES Watcher 或独立 Stream processor。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Transport | Kafka | direct HTTP：丢日志 |
| Hot store | ES | DB：search 慢 |
| Cold store | S3 Parquet | Glacier：太慢；ES 全 hot：贵 |
| Sampling | level-based adaptive | All log：成本爆 |
| Indexing | Per-day index | Per-week：query 跨多 index 慢 |

## 容量估算

- 1M events/sec × 500B avg = 500 MB/s = ~45 TB/day raw
- 30 days hot：1.4 PB in ES → expensive；用 sampling 后 140 TB OK
- 1 year cold: 16 PB Parquet on S3 (compressed 4-5x → 3-4 PB stored)

## 易错点

> [!pitfall]
> ❌ Sync log emit → app 卡；
> ❌ ES 全部 30 天 + 1 年 → 成本爆 1000 万美金/年；
> ❌ 不 sample → noise drowns signal；
> ❌ 不做 PII scrub → compliance disaster；
> ❌ Per-event index → ES write bottleneck；要 bulk insert。

> [!key]
> 三大要点：(1) **Agent + Kafka 解耦 ingest**；(2) **Hot ES + Cold S3 分层**；(3) **Adaptive sampling** 控成本。

> [!followup]
> "Real-time aggregation (count errors by service)？" → Flink subscribe Kafka 实时算；"Cross-service trace correlation？" → 加 trace_id field 在所有 log，OpenTelemetry；"如何 detect anomalous log patterns？" → ML model + log similarity clustering (Drain algorithm)；"GDPR delete user data？" → mark for deletion + rebuild affected indices。
