## 题目本质

**LC 2670 Find the Distinct Difference Array**：长度 n 的数组 nums。对每个 i，`diff[i] = |distinct in nums[:i+1]| - |distinct in nums[i+1:]|`。返回 diff。

## 解法

两遍扫描：
1. 右到左：维护 suffix 的 distinct set + count
2. 左到右：维护 prefix 的 distinct set + count，同时和当前 suffix count 相减

## Python 实现

```python
from typing import List

class Solution:
    def distinctDifferenceArray(self, nums: List[int]) -> List[int]:
        n = len(nums)
        # 1. 右扫：suffix_distinct[i] = nums[i+1:] 的 distinct 数
        suffix = [0] * (n + 1)
        seen = set()
        for i in range(n - 1, -1, -1):
            suffix[i] = len(seen)
            seen.add(nums[i])
        # 2. 左扫：prefix distinct + diff
        result = [0] * n
        prefix_set = set()
        for i in range(n):
            prefix_set.add(nums[i])
            result[i] = len(prefix_set) - suffix[i]
        return result
```

## 复杂度

- 时间：**O(N)**
- 空间：O(N) suffix 数组 + set

## 关键点

### 1. suffix[i] 定义

`suffix[i]` = `nums[i+1..n-1]` 的 distinct count，**不含 nums[i]**。所以在右扫时**先记录再加**。

### 2. prefix 同步前缀

左扫时**先加再算**：`prefix_set.add(nums[i])` 后 `len(prefix_set)` 才包含 nums[i]。

### 3. 边界

- i=0：prefix={nums[0]} → 1；suffix = nums[1:] distinct
- i=n-1：prefix = all distinct；suffix = 0
- n=1：result = [1] - [0] = [1]

## 易错点

> [!pitfall]
> ❌ suffix 定义把 nums[i] 包含进去 —— 公式偏差 1；
> ❌ 用嵌套 loop 每位算 distinct —— O(N²)；
> ❌ prefix_set 用 list 而非 set —— `in` 查 O(N)；
> ❌ suffix 数组大小写错 (n+1 vs n)。

> [!key]
> 双向扫描 + prefix/suffix 累积是 array 题的常用模式。同思想：Trapping Rain Water (LC 42)、Product of Array Except Self (LC 238)。

> [!followup]
> "找最大 diff 的 i？" → 同时记 max；"流式数据？" → 不能直接扫两遍，需要 online 算 distinct（HyperLogLog 估计）；"diff 是负值时？" → 不需特殊处理，公式自然支持。
