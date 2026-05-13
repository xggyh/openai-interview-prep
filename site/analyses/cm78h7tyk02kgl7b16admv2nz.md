## 题目本质

设计**Metrics Aggregator**：服务通过 client library 上报 count 类指标（user signups、system errors、ad clicks 等），在 dashboard 上以**直方图/时间序列**展示。支持任意时间窗口聚合查询。

经典 SD 题，OpenAI 报告 2 次。考点：**写聚合（time-bucketing） + 多分辨率存储 + 查询路由**。

## 需求拆解

**功能性：**
- Client `Counter('user.signup').inc(1)` —— SDK 暂存 + 周期 flush
- Server 接收 metric events，按时间桶聚合
- Dashboard 查询：`SELECT SUM(value) FROM metrics WHERE name='user.signup' AND ts BETWEEN ... GROUP BY interval(1h)`
- Tag / dimension 支持：`Counter('http.request', method='GET', status=200)`

**非功能性：**
- 1M events / sec
- 查询 P99 < 1s（1-hour 窗口）/ < 5s（30-day 窗口）
- 数据保留：1 月精细，1 年聚合

## 整体架构

```ascii
   App + SDK
       │ 批量上报 (UDP / HTTP / Kafka)
       ▼
  ┌──────────────┐
  │ Ingest API   │  → 写 Kafka
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Kafka            │  topic: metrics.raw
  │ (按 metric_name  │
  │  partition)      │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Stream Processor │  → 5s / 1min / 1h 桶聚合
  │  (Flink/Spark/   │
  │   custom)        │
  └──┬──────┬───┬────┘
     │      │   │
     ▼      ▼   ▼
  ┌─────┐ ┌─────┐ ┌─────┐
  │ 5s  │ │ 1m  │ │ 1h  │  分辨率分层存储
  │ TSDB│ │ TSDB│ │ TSDB│
  └──┬──┘ └──┬──┘ └──┬──┘
     │       │       │
     └───────┼───────┘
             ▼
       ┌──────────────┐
       │ Query Service│  按 query 范围选最合适粒度
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ Dashboard /  │
       │ Grafana      │
       └──────────────┘
```

## 核心组件设计

### 1. Client SDK

```python
class Counter:
    """Thread-safe counter that batches and flushes periodically."""

    _registry = {}
    _lock = threading.Lock()

    def __init__(self, name, **tags):
        self.name = name
        self.tags = tags
        self._value = 0
        self._lock = threading.Lock()
        with Counter._lock:
            Counter._registry[(name, frozenset(tags.items()))] = self

    def inc(self, amount=1):
        with self._lock:
            self._value += amount

    @classmethod
    def flush_all(cls):
        """周期由 background thread 调用，每秒一次"""
        with cls._lock:
            batch = []
            for (name, tags), counter in cls._registry.items():
                with counter._lock:
                    val = counter._value
                    counter._value = 0
                if val > 0:
                    batch.append({'name': name, 'tags': dict(tags), 'value': val, 'ts': time.time()})
            send_to_ingest(batch)
```

**关键**：
- SDK 内部缓冲，避免每 `inc` 一次网络调用
- Tag 哈希成 unique key 决定不同 series
- Flush 用 UDP 或 batch HTTP，丢一点不致命（监控类指标允许少量丢失）

### 2. Ingest API

- 接收 batch → 直接写 Kafka，不做任何聚合（保持低延迟）
- 验证 metric name + tag 合法（避免高基数 cardinality 攻击）
- 限速：每 client / 每 metric_name 上限

### 3. Stream Processor（核心聚合）

按分辨率分层聚合：

| 分辨率 | 保留期 | 用途 |
|---|---|---|
| 5 秒 | 1 天 | 实时 alert + 短时排查 |
| 1 分钟 | 7 天 | dashboard 默认 |
| 1 小时 | 90 天 | 历史趋势 |
| 1 天 | 永久 | 归档 |

每条 raw event 同时累计到自己所在的 5s、1m、1h、1d 桶：

```python
# Flink-ish pseudocode
events.key_by(lambda e: (e.name, frozenset(e.tags.items()))) \
      .window(TumblingWindow.of(5.seconds)) \
      .reduce(lambda a, b: a + b) \
      .sink(tsdb_5s)
# 复用同样的 stream，5s 桶再 rollup 成 1m，1m → 1h
```

### 4. Storage：Time-Series DB

每个 series（metric_name + tag combination）一条 timeline。

- **Open-source**：InfluxDB / TimescaleDB / VictoriaMetrics / Prometheus（适合单 cluster scale）
- **大规模 SaaS**：自研列存 + per-series-per-day shard

**Schema**：
```
series_id = hash(name, sorted(tags))
key = (series_id, time_bucket)
value = aggregated value
```

按 series_id 分 partition，按时间分 chunk。

### 5. Query Service

根据查询时间范围**自动选最合适粒度**：

```python
def pick_resolution(start, end):
    span = end - start
    if span <= 1.hour: return '5s'
    if span <= 1.day:  return '1m'
    if span <= 30.days: return '1h'
    return '1d'
```

减少查询返回点数 → 减少传输 + 渲染时间。Grafana 看 30 天 trend 不需要看每秒点。

### 6. Query 语义

```
SELECT name, SUM(value)
FROM metrics
WHERE name = 'http.request'
  AND tags.method = 'GET'
  AND ts BETWEEN start AND end
GROUP BY interval(1m), tags.status
```

实现：按 series_id 列出所有匹配 tag 的 series → 各自查 timeline → group/sum/avg。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 传输 | UDP / Kafka batch | 同步 HTTP per event：延迟高 |
| 聚合时机 | 写时聚合（pre-aggregation） | 查时聚合：查询慢 |
| 多分辨率 | 同时维护 5s/1m/1h/1d | 单分辨率：查长时段慢 |
| Tag cardinality | 限制（< 10k unique per name） | 不限：series 数爆 → DB 撑不住 |
| 一致性 | 最终一致（监控数据，允许小延迟） | 强一致：吞吐撑不住 |

## 容量估算

- 1M events/s × 100 字节 = 100 MB/s 上行
- 假设 平均 100 unique series 处理 (high cardinality 例外) → 5s 桶 = 100 写/5s/series = 20 QPS/series
- 1 月数据保留 5s 粒度 → 100 series × 17280 buckets/day × 30 day × 16 B = ~830 MB （单 metric）

整体算下来 1 月精细数据 TB 级，1 年聚合保留 < 1 TB。

## 关键技术细节

- **高基数标签警惕**：user_id 当 tag → series 数随 user 增长 → DB 爆。SDK 应禁止 high-cardinality tag
- **Late-arriving events**：用 watermark + grace period（如 10 分钟）允许迟到事件归入正确桶
- **Time skew**：client 时钟可能不准，server 重新打 ts 或用 client_ts + server_ts 都存
- **Quantile（直方图）**：count 是简单 sum；p99 需要 HDR histogram / t-digest，分桶后还能合并

> [!key]
> 三大要点：(1) **客户端 batch + UDP/Kafka** 减少网络；(2) **多分辨率预聚合**（写时算好不同粒度，查时直接读）；(3) **查询自动选粒度** 避免返回千万点。

> [!pitfall]
> ❌ Synchronous HTTP per inc —— SDK 拖垮 app；
> ❌ Tag 不限制 cardinality —— series 数爆，DB 死；
> ❌ 只存 raw event 查时聚合 —— 30 天查询扫几亿条；
> ❌ 没考虑 late-arriving —— alert 误报；
> ❌ 实时聚合 + 短保留 但 dashboard 看长时段 —— 没数据。

> [!followup]
> "alert 怎么实现？" → 实时聚合后过阈值检测，PagerDuty webhook；"如何 distributed tracing 集成？" → metrics 是 counters，traces 是 spans，统一 ingest 不同存储；"如何 multi-tenant？" → series_id 加 tenant_id 前缀 + 独立配额。
