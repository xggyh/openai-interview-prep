## 题目本质

设计 **Top-K System**：实时从数据流中找出 top K items（按 count / score）。Twitter trending tags、search query top suggestions、e-commerce top products。

参考类似题：[[cm7honmgk0278imqn03o95rtg]] (Trending Hashtags)。这里更通用的 framework。

## 核心算法

### 1. Exact top-K

适合数据量小（< 1M items / window）：
- HashMap counter + min-heap of size K
- Each event: counter[item]++; if among top-K push heap

### 2. Approximate top-K — Count-Min Sketch + Heavy Hitters

适合 high cardinality（10M+ items）：

```python
class HeavyHitters:
    def __init__(self, k, cms_width=10000, cms_depth=5):
        self.cms = CountMinSketch(cms_width, cms_depth)
        self.heap = []      # min-heap of (estimated_count, item)
        self.k = k
        self.in_heap = set()

    def add(self, item):
        self.cms.add(item)
        est = self.cms.estimate(item)
        if item in self.in_heap:
            # rebuild heap entry for this item
            # 复杂度优化：lazy delete
            heapq.heappush(self.heap, (est, item))
        elif len(self.heap) < self.k:
            heapq.heappush(self.heap, (est, item))
            self.in_heap.add(item)
        elif est > self.heap[0][0]:
            _, evicted = heapq.heapreplace(self.heap, (est, item))
            self.in_heap.discard(evicted)
            self.in_heap.add(item)
```

### 3. Approximate — Misra-Gries

固定 K+1 counters。新 item：if 已有 ++；else if 有 counter = 0 替换；else 所有 counter -1。

guarantee：true frequency > total/K 的 item 一定被找到。简单且 O(K) memory。

## 整体架构（分布式）

```ascii
   Event stream (Kafka)
         │
         ▼
   ┌──────────────────┐
   │ Partition (by    │  shuffle by item hash
   │ item hash)       │
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ Local top-K per  │  每 worker 维护 local CMS + heap
   │ worker (Flink)   │
   └──────┬───────────┘
          │ 每 N 秒 emit local top-K
          ▼
   ┌──────────────────┐
   │ Global aggregator│  union top-K from all workers
   │ → final top-K    │
   └──────┬───────────┘
          ▼
   ┌──────────────────┐
   │ Redis top-K cache│
   └──────────────────┘
```

### 关键：分而合并的近似性

不能保证 global exact top-K，但 union of local top-K + scoring 在实践上误差极小（top-K 都是 high-frequency item，分到各 shard 仍会是 local top）。

## Sliding window 

如果要"最近 5 分钟 top-K"而非"all-time"：每分钟一个 sub-window CMS + heap，5 个 sub-window union 计算。

老 sub-window expire 自然滑动。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Exact vs approx | Approx for high cardinality | Exact：内存爆 |
| Algo | CMS + heavy hitters | Sort all every interval：O(N log N) |
| Partition | by item hash | by random：top-K shuffle 不准 |
| Window | sliding | tumbling：bursty 不平滑 |

## 易错点

> [!pitfall]
> ❌ 朴素 HashMap counter for 10M cardinality —— OOM；
> ❌ CMS 不加 heavy hitters → 没法快速 enumerate top-K；
> ❌ 全 global single counter —— 写热点；
> ❌ Sliding window 不 expire 老数据 —— count 累计成 all-time；
> ❌ Approx error 不告知用户 —— UI 不应表达"准确"。

> [!key]
> Top-K 高基数 = **CMS + heavy hitters + sliding window**。LC 风格的 top-K 题（Top K Frequent Elements）是 in-memory exact 版；分布式 streaming 版用 approximate。

> [!followup]
> "Personalized top-K per user？" → per-user counter（如果 user 多就分布式）；"Top-K with decay (新事件权重高)？" → exponential decay 在 CMS 上；"Top-K with constraints (category)？" → 加 filter 维度 sharding。
