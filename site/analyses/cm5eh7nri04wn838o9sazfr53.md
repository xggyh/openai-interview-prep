## 题目本质

**LC 347 Top K Frequent Elements**：给数组 `nums` 和整数 `k`，返回**出现频率前 k 高**的元素。Google 高频经典。

## 解题切入点

三种主流解法，按复杂度递减：

| 方法 | 时间 | 空间 | 适用 |
|---|---|---|---|
| Sort by freq | O(N log N) | O(N) | k 接近 N |
| **Heap (size k)** | **O(N log k)** | O(N + k) | k ≪ N |
| **Bucket sort** | **O(N)** | O(N) | 频率范围 ≤ N（即 ≤ N 种 freq） |

面试期望 **heap** 或 **bucket sort**。两个都得熟。

## Python 实现 — 推荐 Bucket Sort

```python
from collections import Counter
from typing import List

class Solution:
    def topKFrequent(self, nums: List[int], k: int) -> List[int]:
        freq = Counter(nums)            # O(N) 统计频率
        n = len(nums)
        # buckets[i] = 出现 i 次的元素列表
        buckets = [[] for _ in range(n + 1)]
        for num, f in freq.items():
            buckets[f].append(num)
        # 从频率高到低收集 k 个
        res = []
        for f in range(n, 0, -1):
            for num in buckets[f]:
                res.append(num)
                if len(res) == k:
                    return res
```

## Heap 解法

```python
import heapq
from collections import Counter

class Solution:
    def topKFrequent(self, nums, k):
        freq = Counter(nums)
        # 用 size-k min-heap：堆顶是频率最低
        heap = []
        for num, f in freq.items():
            heapq.heappush(heap, (f, num))
            if len(heap) > k:
                heapq.heappop(heap)
        return [num for f, num in heap]
```

或者更简单用 `heapq.nlargest`：

```python
return heapq.nlargest(k, freq.keys(), key=freq.get)  # O(N log k)
```

## 为什么 Bucket Sort 是 O(N)

频率最大值 ≤ N（因为只有 N 个元素）。所以 buckets 数组大小 N+1，每个元素恰好被 push 一次，扫一次找 top k。总扫描量 O(N + k)。

## 复杂度对比

```
N = nums.length
unique count u <= N
```

| 方法 | 时间 | 空间 |
|---|---|---|
| Sort | O(u log u) | O(u) |
| Heap | O(u log k) | O(u + k) |
| Bucket | **O(N)** | O(N) |

## 边界 case

```python
assert sorted(Solution().topKFrequent([1,1,1,2,2,3], 2)) == [1, 2]
assert Solution().topKFrequent([1], 1) == [1]
assert sorted(Solution().topKFrequent([1,2], 2)) == [1, 2]
```

## 易错点

> [!pitfall]
> ❌ 用 `heapq.heappush` 不限制 size —— 退化为 O(N log N)；
> ❌ 用 max-heap 思路（取最大）但 Python 的 `heapq` 是 min-heap —— 要么 negate priority，要么用 `nlargest`；
> ❌ Bucket sort 用 dict 而非 list `buckets[freq]` —— 需要 sorted keys 反而麻烦；
> ❌ 没考虑 freq 范围上限是 N（不是 max value）—— 数组用 max(nums) 大小会很慢。

> [!key]
> "频率前 k" 模式：Counter → bucket (O(N)) 或 size-k heap (O(N log k))。这是面试官最爱让你**说出多个方案 + 取舍**的题。

> [!followup]
> "K 个频率最低？" → bucket 反向扫；"实时流式数据 top k？" → Count-Min Sketch + min-heap；"k = 1 时？" → 直接 `max(Counter(nums).items(), key=lambda x: x[1])[0]`。
