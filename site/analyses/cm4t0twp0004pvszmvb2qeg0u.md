## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Top-K** | 找前 K 个最热 item | 排行榜 Top-10 |
| **Stream** | 持续来的数据流（vs batch 一次性） | 不断流的水 vs 一桶水 |
| **Min-Heap** | 维护"最小值在堆顶"的数据结构，O(log K) 操作 | 排排坐，最小的在前 |
| **Count-Min Sketch (CMS)** | 用概率数据结构估计 counter，内存极省 | 漏勺 — 大颗粒精准、小可能漏 |
| **HyperLogLog** | 估"distinct count"的 sketch | 估"人群里有几种 dress" |
| **Heavy hitter** | 出现次数远超均值的元素 | 一群人里最高的几个 |
| **Sliding window** | 时间窗口"滑动"，老数据过期 | 一辆缓行的车 5 分钟视野 |
| **Tumbling window** | 时间窗口"接力"，互不重叠 | 钟表分针一格一格走 |
| **Misra-Gries** | 算法，O(K) 内存找候选 heavy hitter | 选举筹码法 |
| **Space-Saving** | 类似 Misra-Gries 的 O(K) 算法，更精确 | 改进版筹码法 |
| **Flink / Kafka Streams** | 业界主流流处理框架 | 流水线运营商 |
| **Sketch merging** | 多个 shard 的 sketch 合并得 global | 多分公司销售榜合一份 |

---

## 1. 题目本质

**Top-K System** = 从持续 event 流中**实时找 top K items by count**。Generic framework，可应用：
- Trending hashtags (Twitter)
- Top search queries (Google Suggest)
- Top products (Amazon best sellers)
- Top players (esports leaderboard - but那个是 ZSET 题)
- DDoS detection (IP top requesters)
- Spam: top spammers / phishing URLs

**为什么这是 STAFF 题（虽然只 1 ppl 报告）**：

考的是**stream processing + 概率数据结构 + sharding**：

1. **海量流量** (亿级 events/sec) → 不能 naive 计数
2. **多时间窗口** (1 min / 1 hour / 1 day) 同时维护
3. **Heavy hitter 算法** — Count-Min Sketch / Space-Saving
4. **跨 shard 合并** — 分布式 Top-K 的难点
5. **精确度 vs 内存** trade-off

考 STAFF 关键：**知道 sketch 算法 + sliding window + multi-time-window**。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `Record(item, count=1)` | 记录一次 event |
| `GetTopK(window, K) -> [(item, count)]` | 查询 top-K |
| `GetCount(item, window) -> count` | 单 item 计数估计 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Event throughput** | 1M events/sec sustained |
| **Query latency** | p99 < 100 ms |
| **Memory** | O(K log N) per shard，不能 O(N) |
| **Accuracy** | top-K precision ≥ 95% |
| **Windows** | 1 min, 5 min, 1 hour, 1 day |
| **Update latency** | < 5 s (event → top-K updated) |

---

## 3. 容量估算

- **Events**: 1M /s × 86400 = 86B events/day
- **Distinct items**: 10M (e.g., distinct search queries / hashtags)
- **Naive count**: 10M items × 100 B = 1 GB total per window — actually doable for in-memory
- **Multi-window**: 4 windows × 1 GB = 4 GB — fine

But:
- 1M events/sec write → 单机扛不住
- 多 shard → 每 shard local top-K 然后 merge → 算法挑战

---

## 4. 关键设计：算法选择

### 4.1 Exact counting (naive)

```python
counts = defaultdict(int)
def record(item): counts[item] += 1
def top_k(): return heapq.nlargest(K, counts.items(), key=lambda x: x[1])
```

**问题**: distinct items 1B+ 时内存爆，且 top_k 是 O(N log K)。

### 4.2 Min-Heap of size K + HashMap counter

```
HashMap: item → count (full counter)
MinHeap: top-K 候选 (size K, 堆顶最小)

on record(item):
    counts[item] += 1
    if item in heap:
        heap.update(item, counts[item])
    elif counts[item] > heap.peek().count:
        heap.replace_top(item, counts[item])
```

**问题**：仍 O(N) 内存 (HashMap). 1B distinct items 时不行。

### 4.3 Count-Min Sketch (probabilistic)

固定大小的 2D 数组 `counts[d][w]`, d row × w columns，加 d 个 hash 函数。

```python
def record(item):
    for i in range(d):
        h = hash_i(item) % w
        counts[i][h] += 1

def estimate_count(item):
    return min(counts[i][hash_i(item) % w] for i in range(d))
```

**Memory**: 4 rows × 100k cols × 4 B = **1.6 MB** for any number of items.

**Error**: counts > true count by some additive ε, with prob 1-δ。`w = e/ε, d = ln(1/δ)`.

**Limit**: CMS 不直接给 top-K — only 估 single item count. 配合 heap：

```
CMS for counting + Min-Heap for tracking top-K candidates
```

### 4.4 Space-Saving Algorithm (O(K) memory, deterministic)

```
counters = {item: count} of size K (fixed)

on record(item):
    if item in counters:
        counters[item] += 1
    elif len(counters) < K:
        counters[item] = 1
    else:
        # Evict the minimum
        min_item = argmin(counters)
        del counters[min_item]
        counters[item] = counters[min_item] + 1  # inherit count!
```

**Guarantees**:
- Any item with true count > N/K is **guaranteed** in counters
- Counter overestimates by at most N/K

**内存**：K items × 100 B = 100 KB for K=1000.

**This is the cleanest "fixed memory top-K"**。

### 4.5 推荐组合

- **Per-shard**: Space-Saving (K' > K, e.g., K' = 10×K)
- **Sketch for exact-ish count**: Count-Min in parallel for "did user X care about exact count?"
- **Global merge**: union per-shard counters, recompute top-K

---

## 5. 高层架构

```
   Event source (Kafka, 1M events/s)
         ↓ partition by hash(item) % N
   ┌────────────────────────────────┐
   │  Shard 0..N (Flink/Spark)      │
   │  - Space-Saving per window     │
   │  - Tumbling windows (1m/5m/1h) │
   │  - Emit candidates per window  │
   └────────────────────────────────┘
         ↓
   ┌────────────────────────────────┐
   │  Aggregator (single shard /     │
   │   per region)                   │
   │  - Merge shards' candidates     │
   │  - Compute global top-K         │
   └────────────────────────────────┘
         ↓
   ┌────────────────────────────────┐
   │  Redis ZSET / DynamoDB           │
   │  - Query API serves top-K        │
   └────────────────────────────────┘
```

### Step 1: Partitioning by item

Events 按 `hash(item) % N` 分到 N 个 shard. 同 item 永远进同 shard → 单 shard 看到 item 的所有 count.

### Step 2: Per-shard top-K computation

Each shard runs Space-Saving alg with `K' = 10 * K`：保留 candidate top-10K (因为 global top-K 不一定是每个 shard 的 top-K)。

### Step 3: Aggregation

Aggregator 收 N shards 的 candidates → merge counts (sum across shards) → sort → global top-K。

### Step 4: Multi-window

每个 window (1m / 5m / 1h / 1d) 独立维护 Space-Saving counter。

**Implementation**:
- Tumbling windows: 每 1 min 启动新 counter，老 counter 结算后丢弃
- Sliding 1 hour: 60 个 1-min sub-window，sum 60 个的 counter → 1h top-K
- 1 day: 24 个 1-hour，sum

### Step 5: Real-time query

API 查 top-K 时直接读 Redis (aggregator 周期性 publish)。

---

## 6. 组件深挖

### Deep Dive 1: Count-Min Sketch 数学

**Error bound**:
- For count of item x: `true_count ≤ estimate ≤ true_count + ε × N` with prob 1-δ
- 通常 ε = 0.01% (估算误差 < 0.01% of stream)
- δ = 0.01% (failure rate)
- Memory = 4 rows × 1M cells × 4 B = 16 MB

**Heavy hitter**: item with `true_count > φN` (φ = e.g., 1%). CMS guarantees these are detected.

### Deep Dive 2: Sliding Window 实现

**Naive (deque of events, size = window)**:
- O(window size) memory
- O(1) add, O(1) eviction
- 但 window size 1 hour × 1M events/sec = 3.6B events → 内存爆

**Tumbling sub-windows + merge**:
- 60 个 1-min sub-windows, 每个有自己 Space-Saving counter
- Query 1-hour top-K: merge 60 个 counters

**Exponential decay (alternative)**:
- Each event 加权 `e^(-λ × age)`
- 不需要 evict, 旧数据自然衰减
- 但累积浮点误差

### Deep Dive 3: Shard Merging

**Challenge**: Space-Saving per shard 给 K' candidates，merge 时 item 可能在多 shard 都是 top-K' 也可能某个 shard 不在 top-K'.

**Solution**:
- Per shard 维护 K' = 10×K candidates
- Aggregator collect all shards' K' lists
- For each unique item, sum counts across shards
- Sort & take top-K

**Edge case**: item 在 shard A 排第 11, 在 shard B 排第 1，global merge 后可能进 top-K. K' = 10×K guard against this (shard A 的 K' = 100, 排第 11 进了，不会丢)。

### Deep Dive 4: Skew (Hot Item)

**Single item 占 50% 流量** (e.g., #BlackFriday) → 该 shard 流量 50× others → backpressure。

**Solution**:
- **Salt the hash**: hot items 自动 random-salt 分到 multiple shards
- Aggregator 合并 salt suffix
- Trade-off: 额外 metadata, but 流量均衡

**或** dedicated "celebrity" path: top items 不走 shard，直接进 single global atomic counter（Redis INCR）。

### Deep Dive 5: Approximate vs Exact

**业务要 Exact**?
- 通常不需要—"哪 100 个是热门"对 K=100 来说 ±5 个误差用户无感
- 如果真要 exact: 用 spanner / distributed atomic counter，代价高 10×

**Approximate works because**:
- Top-K precision (in top-K 中真正 top-K 比例) > 95% 用户感知不出
- Exact count off by 0.1% in 1M events 也不可见

### Deep Dive 6: Memory Budget at Scale

10M distinct items × 100 B = 1 GB exact in memory — actually feasible!

When **Sketch matters**:
- 1B+ distinct items (IP addresses, user IDs, URLs)
- Need 100+ windows (long history at multiple granularities)
- Memory budget tight (mobile / edge)

For most web-scale Top-K: exact in-memory works at single shard 10M items × 100 B = 1 GB.

### Deep Dive 7: Query Path Caching

Top-K query 100k QPS → cache aggregated result in Redis with TTL 10s。Recompute from raw counters every 10s。

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：what's the item? how many distinct? how many windows? |
| 5-10min | 容量：1M events/s, 10M distinct items, K=100 |
| 10-15min | 算法选择：min-heap vs CMS vs Space-Saving，trade-off |
| 15-25min | 高层架构：partition by item → shard → aggregator → cache |
| 25-40min | Deep dives: sliding window / shard merge / skew / exact vs approx |
| 40-45min | multi-region / hot path |

---

## 7. 样板讲解稿

> Top-K 框架 generic 适用 trending hashtags / top queries / spam IPs 等。核心是 **stream processing + sketch + sliding window**。
>
> **算法选择**：
> - Naive HashMap + min-heap: O(distinct items) memory, 1M+ distinct 不行
> - **Space-Saving algorithm**: O(K) memory deterministic，是 fixed memory 经典方案
> - Count-Min Sketch: 估单 item count，O(log 1/δ × 1/ε) memory，配合 heap 找 top-K
>
> **架构**：
> 1. Kafka partition by hash(item) 分 N shard
> 2. Each shard 用 Flink/Spark Streaming 跑 Space-Saving (K'=10K)
> 3. Aggregator merge shards' candidates → global top-K
> 4. Redis cache top-K result, 10s TTL
>
> **Multi-window**:
> - Tumbling sub-windows (1min granularity)
> - Sliding window = sum of N sub-windows
>
> **Skew**:
> - Hot items salt-hash to distribute load
> - Or dedicated celebrity path
>
> Numbers: 1M events/s, 10M distinct items, K=100, p99 < 100ms.

---

## 8. Follow-up Q&A

### Q1: "Space-Saving 跟 Count-Min Sketch 哪个适合？"

**A**：
- **Space-Saving**: O(K) memory, deterministic — best for "fixed K top elements"
- **CMS**: O(log 1/δ / ε) memory, probabilistic — best for "what's the count of ANY item"
- **Combination**: SS for top-K candidates + CMS for accurate count estimate

### Q2: "Heavy hitter 在 shard A 排第 100，shard B 排第 1，merge 后会丢吗？"

**A**：会，如果 shard 只 keep top-K=10. 解法是每 shard 保留 K' = 10×K 候选，足够覆盖 cross-shard 排名变化。

### Q3: "1 hour window 怎么 sliding？"

**A**：60 个 1-min tumbling sub-windows，aggregator 维护 sliding sum: 每分钟 evict 最老 sub-window + add new。Counter merge 是关键 (Space-Saving 可 merge：counts 相加 + 取 top-K)。

### Q4: "如果某个事件突然爆量 (10×)，怎么处理？"

**A**：
1. **Backpressure**: Kafka 缓冲 spike
2. **Detect via heap top**: 单 item 占 partition 流量 50%+ → fire alert
3. **Salt hot item**: 自动 split to multiple shards
4. **Pre-aggregate at producer**: client 本地 batch 10s reduce 流量

### Q5: "实时怎么定义？ 5s 还是 5min？"

**A**：tunable. 通常：
- 5s for breaking news / DDoS
- 1 min for trending hashtags
- 1 hour for "top of the day"

Trade-off: smaller granularity = more memory + compute, more accurate "right now"。

### Q6: "Multi-region 全球 top-K 怎么算？"

**A**：
- Per region 维护本地 top-K (Space-Saving)
- 每 1 min 各 region 把 K' candidates push 到 global aggregator
- Global aggregator merge → global top-K
- Trade-off: 1 min lag for global (vs in-region real-time)

### Q7: "Item 是用户 IP 找 DDoS attacker？"

**A**：
- Distinct IPs 可达 100M → 必须 sketch
- Use CMS for IP counts + SS for top
- Threshold trigger: IP > 100 req/s → flag for rate limit
- Sliding 1-min window for short bursts

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **HashMap counter for all items** → 10M+ items 时内存爆
2. **不知道 Space-Saving / CMS** → answer 是 heuristic
3. **Per shard K = K** → merge 时丢 cross-shard heavy hitters
4. **不区分 sliding vs tumbling** → 概念混淆
5. **没考虑 skew** → 单 shard 过载
6. **Real-time = 0 latency** → 不现实，应说 5s/1min

### ✅ 加分项

1. **Space-Saving algorithm** 算出来 K=1000 时 100 KB memory
2. **CMS error bound** math (ε, δ)
3. **K' = 10×K** for cross-shard correctness
4. **Salt hot item** 防 shard 过载
5. **Tumbling sub-windows + merge** 实现 sliding window
6. **Multi-granularity windows** (1m/5m/1h/1d)
7. **Flink / Kafka Streams** 提一嘴 implementation
8. **HLL for distinct count** if asked

> [!key] STAFF vs SENIOR：能写出 Space-Saving 伪代码 + 解释 O(K) 内存 deterministic 是 STAFF；只说"min-heap" 是 SENIOR。

---

## 10. Cheat Sheet

```
算法选择:
  Exact (small distinct < 10M): HashMap + min-heap
  Fixed K memory: Space-Saving (deterministic, O(K))
  Approx count any item: Count-Min Sketch
  Hybrid: SS + CMS in parallel

Sharding:
  partition by hash(item)
  per-shard K' = 10*K candidates
  Aggregator merge → global top-K

Multi-window:
  1-min tumbling sub-windows
  Sliding 1h = sum of 60 sub-windows
  Per window: independent Space-Saving counter

Skew handling:
  Salt hot items (multi-shard)
  Or celebrity path (Redis INCR direct)

Memory:
  Space-Saving K=1000 → 100 KB
  CMS 1M cells × 4 rows → 16 MB
  Exact 10M items × 100B → 1 GB (feasible!)

数字:
  1M events/s, 10M distinct, K=100
  4 windows (1m/5m/1h/1d)
  p99 < 100ms query
  Update lag: 5s
  precision@K > 95%
```
