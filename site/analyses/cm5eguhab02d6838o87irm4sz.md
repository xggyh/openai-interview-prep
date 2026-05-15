## 题目本质

**LC 460 LFU Cache**：实现 Least Frequently Used 缓存。`get(key)` / `put(key, value)` 都 **O(1)**。容量满时驱逐**使用次数最少**的；若并列驱逐**最久未用**的。

LFU 比 LRU 难一档，是 Google / Meta 的"hard" 经典。

## 数据结构设计（双 hashmap + 双链表）

```
key_to_node  : dict[key -> Node]            ; Node 存 key/val/freq, 在某个 freq 的双链表里
freq_to_list : dict[freq -> DoublyLinkedList] ; 每个 freq 一个 list（按访问顺序，最旧在 head）
min_freq     : int                          ; 当前最小频率（驱逐用）
```

**get 流程**：找 node → 从其 freq 链表移除 → freq+1 → 加到 freq+1 链表的尾部 → 如果该 freq 是 min_freq 且 list 为空，min_freq++

**put 流程**：
- key 已存在：更新 val，等同于 get
- key 不存在：满了就驱逐 `freq_to_list[min_freq].head`；插入新 node 到 freq=1 链表，min_freq = 1

## Python 实现

```python
from collections import OrderedDict, defaultdict

class LFUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.size = 0
        self.min_freq = 0
        # key -> (val, freq)
        self.kv: dict = {}
        # freq -> OrderedDict[key -> None]，最早 insertion 在前
        self.freq_buckets: dict[int, OrderedDict] = defaultdict(OrderedDict)

    def _touch(self, key: int) -> None:
        """将 key 从当前 freq bucket 移到 freq+1 bucket，更新 min_freq."""
        val, f = self.kv[key]
        # remove from current freq bucket
        del self.freq_buckets[f][key]
        if not self.freq_buckets[f]:
            del self.freq_buckets[f]
            if self.min_freq == f:
                self.min_freq += 1
        # add to next freq bucket（OrderedDict 末尾）
        self.kv[key] = (val, f + 1)
        self.freq_buckets[f + 1][key] = None

    def get(self, key: int) -> int:
        if key not in self.kv:
            return -1
        self._touch(key)
        return self.kv[key][0]

    def put(self, key: int, value: int) -> None:
        if self.cap == 0:
            return
        if key in self.kv:
            self.kv[key] = (value, self.kv[key][1])
            self._touch(key)
            return
        if self.size == self.cap:
            # evict LFU + LRU 内部
            lfu_bucket = self.freq_buckets[self.min_freq]
            evict_key, _ = lfu_bucket.popitem(last=False)  # 最早的
            del self.kv[evict_key]
            if not lfu_bucket:
                del self.freq_buckets[self.min_freq]
            self.size -= 1
        # 新元素 freq = 1
        self.kv[key] = (value, 1)
        self.freq_buckets[1][key] = None
        self.min_freq = 1
        self.size += 1
```

**为什么 OrderedDict？** Python 的 `OrderedDict` 维护插入顺序，且 `popitem(last=False)` 是 O(1)。这等价于双向链表 + dict 的工程实现。

## 复杂度

- `get`: **O(1)** 摊销
- `put`: **O(1)** 摊销
- 空间: O(capacity)

## 关键技术点

### 1. min_freq 的更新时机

- 增 (`_touch` 把 key 从 f 移到 f+1)：如果 f == min_freq 且 f 的 bucket 空了 → min_freq++
- 新插入：min_freq = 1（新元素 freq 永远是 1）
- 删除：只可能从 min_freq bucket 删（驱逐），bucket 空了不需更新（下次 put 会重设）

### 2. 为什么 LRU 内部用 OrderedDict 而不是 list

`list.pop(0)` 是 O(N)。OrderedDict / 双向链表能 O(1) 从头部删。

### 3. capacity == 0

特判：`put` 时直接 return；`get` 永远 miss。

## 易错点

> [!pitfall]
> ❌ 更新 freq 时忘了从旧 bucket 删 —— 旧 freq 里残留；
> ❌ 删除 bucket 后不删 dict key —— 死链；
> ❌ min_freq 更新错误：`_touch` 中只在"当前 freq == min_freq 且 bucket 空了"才 ++，不要 unconditional ++；
> ❌ 用 list 模拟 OrderedDict —— pop(0) O(N)，整体退化为 O(N)；
> ❌ capacity == 0 没特判 —— 第一次 put 就 KeyError。

> [!key]
> LFU = LRU + freq 计数。Python 用 `dict[freq] -> OrderedDict` 比手写双向链表清晰且性能等价。同样的"双层 hash"技巧也用在 LRU 的高级实现（双 dict 模拟有序队列）。

> [!followup]
> "如何分布式 LFU？" → 复杂，通常用 Redis ZSCORE + 双重排序（freq, recency）；"如何让 capacity 动态调整？" → resize 接口，缩小时驱逐到目标；"如何记 hit/miss 统计？" → counters；"为什么 LRU 比 LFU 更常用？" → LFU 对"突发热点 vs 长期冷数据"不友好（一旦某 key 被狂访问，freq 上去后即使后期不再用也很难被驱逐）。
