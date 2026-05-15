## 题目本质

**LC 2475 Number of Unequal Triplets in Array**：求三元组 (i,j,k) 数量，满足 i<j<k 且 nums[i], nums[j], nums[k] 两两不同。

## 解法

**计数 + 组合**：相同值的元素之间不可能组成 valid triplet（要求三者不同）。

对每个 distinct value v 与其频率 freq[v]：
- 选一个 nums[i] = v
- 选一个 nums[j] = u (u ≠ v)
- 选一个 nums[k] = w (w ≠ v, w ≠ u)

但 i<j<k 顺序要求让计数变复杂。**更简单：枚举中间元素 j**。

## 更简单方法：组合数

如果有 G 个不同值，频率分别 f1, f2, ..., fG。三元组（无序）从 3 个不同 group 中各取 1 个：

```
count = sum over all (i, j, k) triples of groups: f_i × f_j × f_k
      = (sum f) × (sum f × from later) × (sum f × from even later) - 简化为
      = enumeration
```

但因为题目要 i<j<k 的**位置**顺序（不是值的顺序），但 unequal triplet 数 = 三个不同值各取 1 个的方式数（位置自然有 6 种排列，但 (i,j,k) i<j<k 只有 1 种）。

Wait — i<j<k 是 indices，所以三个 index 有顺序。如果三个值 v1, v2, v3 不同，那对应位置就一种 i<j<k 排序方式（按位置自然排序）。所以**count = 三个不同值各选 1 个的方式数 = ΣΣΣ f_a × f_b × f_c (a, b, c 不同 group)**。

## Python 实现

```python
from collections import Counter
from typing import List

class Solution:
    def unequalTriplets(self, nums: List[int]) -> int:
        freq = list(Counter(nums).values())
        n = len(nums)
        total = 0
        # 枚举中间组：left_sum × f_b × right_sum
        left = 0
        for i, f in enumerate(freq):
            right = n - left - f
            total += left * f * right
            left += f
        return total
```

## 复杂度

- 时间：**O(N)**（Counter + 一遍 freq）
- 空间：O(unique)

## 关键技术点

### 1. 等价的分组思考

题目要求**值不同**。所以三个 index 选自 3 个不同 group，每 group 选 1 个，方式数 = f_a × f_b × f_c。i<j<k 是 indices 顺序，但只要值不同，无论 group 间顺序，必定有唯一的 i<j<k 排列（按 indices 排序）。

### 2. 枚举中间 group b

按某种 group 顺序遍历 b，统计：
- left = sum of f over 已经处理的 group（即 b 之前的所有 group）
- right = sum of f over 未处理的 group
- 三元组以 b 为中间值的数量 = left × f_b × right

每个 (a, b, c) triple 三个 group 顺序唯一对应一次"b 是中间"，所以累加无重复。

### 3. 为什么这样不重复计数

每个无序 triple {a, b, c} 在枚举 b ∈ {a, b, c} 时只会被算一次（具体取 b 时另两个一个在 left 一个在 right）。

实际上每个无序 group triple 会被算 3 次（每 group 当一次中间），但 left × right 也只数有序对，所以... 让我再核对：

- left × f_b × right：对每个 (a 在 left, b 是中间, c 在 right) —— 那 c 在 b 之后的 group 里
- a 和 c 在两侧，组合数 = left（所有 a 选法）× right（所有 c 选法）
- 一个 triple {a, b, c} 当 b 是中间 group 时：a 必须是 left 里的 (在 b 之前)，c 必须是 right 里的 (在 b 之后)
- group 的顺序是任意的（我们按 freq.values() 遍历），但每个 unordered triple {ga, gb, gc} 中只有 1 种排列让 ga < gb < gc → 只被算一次

**正确**，不重复。

## 边界 case

```python
sol = Solution()
assert sol.unequalTriplets([4,4,2,4,3]) == 3
# distinct values: {2,3,4} with freq 1,1,3 (顺序不定)
# 枚举：选一个 2, 一个 3, 一个 4 → 1*1*3 = 3
assert sol.unequalTriplets([1,1,1,1,1]) == 0
assert sol.unequalTriplets([1,2,3]) == 1
```

## 易错点

> [!pitfall]
> ❌ 三重 loop O(N³) —— TLE 大数据；
> ❌ 没意识到 i<j<k 是 indices 而非值的顺序 —— 公式偏差；
> ❌ 用 sort 后再算：sort 后值连续相同 group，可以直接 freq * left_sum * right_sum；正确；
> ❌ 忽略 freq=0 的情况：dict 不会有 0；
> ❌ left + f + right != n：常忘 right = n - left - f。

> [!key]
> "三元组 + 不同值" 类题：先想 group by value + 组合数。这套思路应用：LC 2367 Number of Arithmetic Triplets、LC 1995 Count Special Quadruplets。

> [!followup]
> "求 K 元组？" → 枚举中间几个 group + 累积 left/right；"求至少 K 不同？" → 容斥；"如果 i<j<k 必须有值递增？" → 排序后用 BIT 算 LIS-style。
