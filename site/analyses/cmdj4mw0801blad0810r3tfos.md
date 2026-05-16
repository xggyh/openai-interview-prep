## 题目本质

设计 **Distributed system for getting the slowest query from Google search**：从 search service 的几十亿 daily queries 中找出**最慢的 top-K queries**（按 latency）作为优化目标。

考点：**streaming top-K by metric + sampling + persistence**。

## 解法

类似 [[cm4t0twp0004pvszmvb2qeg0u]] (Top-K System) 的 framework，但 metric 是 **latency**（continuous）而非 frequency。

### 1. Streaming approach

每 query 完成后 emit event `{query_id, normalized_query, latency_ms, timestamp}`。

```
Search Service → Kafka topic: query.latency
                       │
                       ▼
              ┌────────────────────┐
              │ Stream Aggregator  │
              │  per-window top-K  │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ Top-K Store        │  → Redis sorted set / DB
              └────────────────────┘
```

### 2. Top-K by latency

不是 count，是 latency。所以是：**Top-K queries by max latency in window**。

```python
# 每 window 维护 max-heap of size K, by latency
heap = []  # min-heap of (-latency, query_id, ts)
def on_query(latency, query):
    if len(heap) < K:
        heapq.heappush(heap, (-latency, query))
    elif latency > -heap[0][0]:
        heapq.heapreplace(heap, (-latency, query))
```

每 5 分钟 emit top-K → 持久化。

### 3. Query normalization

Same logical query 不同参数（`q=python+tutorial` vs `q=java+tutorial`）。Normalize:
- Lowercase + 去 stop words
- 提取 query template (anonymize specifics)
- 同 template 的 latency 才能 aggregate

### 4. Slowest by p99 / p95 vs max?

Single outlier latency 不代表"slow query"。更好：**top-K by p99 latency** over same template。

实现：每 template 维护 latency histogram（HDR Histogram / T-digest）→ p99 → top-K templates。

### 5. Sampling

10B queries/day → 不可能全部 process。10% sampling 足够（top-K 是 high-count item，sample 不丢精度）。

### 6. Multi-dimensional

- 按 region：US slow query vs JP slow query
- 按 user segment：mobile vs desktop
- 按 service version：v1 vs v2 deploy 后是否 regress

每维度独立 aggregator。

### 7. Persistence

Top-K per (window, region, version) 写 DB / TimescaleDB。Analyst dashboard 看历史 trend，研发用来 prioritize 优化目标。

### 8. Alert integration

当 top-K queries 中出现"新 query 而且 p99 急涨" → alert。这是 regression detection。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Metric | p99 / max | mean：长尾不显示 |
| Aggregation | Per template (normalized) | Per query：cardinality 爆 |
| Sample | 10% | 100%：贵 |
| Window | 5 分钟 + sliding | Tumbling：突发不平滑 |

## 易错点

> [!pitfall]
> ❌ Top-K by single max latency → outlier dominant；
> ❌ 不 normalize query → 同 template 算多次；
> ❌ 不 sample → 处理不过来；
> ❌ Slowest 不带 context（哪个 region / 哪个 version） → 找不到根因；
> ❌ 不 alert on regression → 优化方向漂移。

> [!key]
> 三大要点：(1) **Template normalization** 让 query 可聚合；(2) **HDR histogram for p99** 而非 mean；(3) **Multi-dim aggregation (region/version)** 找 regression。

> [!followup]
> "Real-time slowest queries (< 1 min latency)？" → 短 window + 高 sample rate；"按 user satisfaction 而非 latency？" → 加 user metrics (abandon rate, page load)；"如何 distinguish slow query vs slow infra？" → trace 关联 service-level latency。
