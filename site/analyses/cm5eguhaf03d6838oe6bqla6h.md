## 题目本质

**LC 1756 Design Most Recently Used Queue**：实现 MRU Queue 支持：`fetch(k)` —— 把第 k 个元素移到末尾，返回该元素值。初始 queue = [1, 2, ..., n]。

## 解法

直接用 list 是 O(N) per fetch（删除 + append）。优化方案：**Sqrt Decomposition** 或 **Order-Statistic Tree / BIT**。

LC 数据下 list 直接 O(N) 可过。面试期望提到更优解。

## Python 实现（朴素 list）

```python
class MRUQueue:
    def __init__(self, n: int):
        self.q = list(range(1, n + 1))

    def fetch(self, k: int) -> int:
        v = self.q.pop(k - 1)   # 1-indexed
        self.q.append(v)
        return v
```

**复杂度**：每次 fetch O(N)。N, K ≤ 2000，总 4M ops，AC。

## 优化：Sqrt Decomposition

把 queue 切成 √N 大小的 buckets。`fetch(k)`：
1. 找 k 在哪个 bucket（计 cumulative size）
2. 删除该 bucket 内 idx 的元素
3. append 到最后一个 bucket（如果满了就 new bucket）

每操作 O(√N)。总 O(K√N)。

```python
class MRUQueueSqrt:
    def __init__(self, n: int):
        import math
        self.bucket_size = int(math.sqrt(n)) + 1
        self.buckets: list[list[int]] = []
        cur = []
        for x in range(1, n + 1):
            if len(cur) == self.bucket_size:
                self.buckets.append(cur)
                cur = []
            cur.append(x)
        if cur: self.buckets.append(cur)

    def fetch(self, k: int) -> int:
        k -= 1   # 0-indexed
        for bucket in self.buckets:
            if k < len(bucket):
                v = bucket.pop(k)
                self.buckets[-1].append(v)
                if len(self.buckets[-1]) > self.bucket_size * 2:
                    # rebalance (optional)
                    pass
                return v
            k -= len(bucket)
        return -1
```

## 最优：BIT + sentinel

用 BIT 计 1..M 中第 k 个未删除位置（Fractional Cascading / Order-Statistic）。每 fetch O(log² N)。复杂但快。

## 关键技术点

### 1. 朴素 list.pop(k-1) 是 O(N)

list 内部连续数组，删除中间需要 shift 后面元素。N=2000 时 OK。

### 2. Sqrt 平衡

让 bucket 数 ≈ √N，每 bucket 大小 ≈ √N。删除是 O(√N)（bucket 内 shift），查找 bucket 也 O(√N)（最坏扫所有 bucket）。

### 3. Rebalance

最后一个 bucket 长期 append 会变大。定期 rebalance（拆成多 bucket）保证均衡。LC 数据规模可省。

## 易错点

> [!pitfall]
> ❌ fetch(k) 用 0-indexed 但题目 1-indexed —— off by 1；
> ❌ pop 完没 append 到尾 —— 元素丢；
> ❌ Sqrt 实现中 bucket 不维护大小变化 —— 查 k 时错位。

> [!key]
> "中间删 + 尾部加" 类操作的标准技巧：sqrt decomposition 或 BIT。LC 数据量小时朴素 list 也过，面试可先朴素再说优化。

> [!followup]
> "动态调整 queue 大小？" → linked list 更灵活；"支持 remove(value)？" → dict 维护 value -> bucket pointer；"分布式 MRU？" → consistent hash + per-shard MRU。
