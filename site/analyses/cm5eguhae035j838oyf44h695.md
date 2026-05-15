## 题目本质

**LC 1481 Least Number of Unique Integers after K Removals**：移除恰好 k 个元素后，剩下数组的 unique 元素数量最小。

## 解法

贪心：优先删除**频率最小的整数**（一次性把它清空，比把同一高频整数砍一半更划算）。

1. Count freq
2. 按 freq 升序排序
3. 顺序消耗 k：每删除一种 (freq 个) ，k 减 freq，unique-- ；如果 k 不够删完整种，则停止

## Python 实现

```python
from collections import Counter
from typing import List

class Solution:
    def findLeastNumOfUniqueInts(self, arr: List[int], k: int) -> int:
        freq = Counter(arr).values()
        sorted_freq = sorted(freq)
        unique = len(sorted_freq)
        for f in sorted_freq:
            if k >= f:
                k -= f
                unique -= 1
            else:
                break
        return unique
```

## 复杂度

- 时间：**O(N + U log U)**，U = unique count
- 空间：O(U)

## 关键点

### 1. 贪心正确性

要让 unique 最小 → 尽可能多地完全删掉某些整数。删掉一个 freq=f 的整数花 f 次操作，让 unique 减 1。**优先选 f 最小的**（性价比最高）。

### 2. 处理 k 用完

如果 `k < f`，删不完这种整数，但它仍然存在于数组里 → unique 不减。break。

### 3. Bucket sort 优化

如果想做 O(N) 而非 O(U log U)：

```python
freq = Counter(arr)
buckets = [0] * (len(arr) + 1)
for f in freq.values():
    buckets[f] += 1
unique = sum(buckets)
for f in range(1, len(arr) + 1):
    if buckets[f] == 0: continue
    can_remove = min(buckets[f], k // f)
    unique -= can_remove
    k -= can_remove * f
    if k < f: break
return unique
```

复杂度 O(N)。LC 数据下 sort 也 OK。

## 易错点

> [!pitfall]
> ❌ 删除最高频的 —— 一次操作只减 1 个，浪费；
> ❌ k=0 时返回 0 —— 错，应返回 unique 总数；
> ❌ k 大于总和时返回 0 —— 题目通常保证 k ≤ len(arr)；
> ❌ 用 list 频繁 sort —— 一次 sort 后顺序固定。

> [!key]
> 经典贪心 "选最便宜的购买" 模式。性价比 = "unique 减少量 / 操作数" → 选 f 最小的 ratio = 1/f 最大。

> [!followup]
> "最大化 unique（保留 k 个）？" → 反过来：保留 freq 最低的，相当于答案 = 多少种 freq 能塞进 k；"加权 unique？" → 改为 1/(f × weight) 排序；"分布式数据？" → MapReduce: count → 全局 sort by freq。
