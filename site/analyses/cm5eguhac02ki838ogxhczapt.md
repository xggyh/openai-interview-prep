## 题目本质

**LC 724 Find Pivot Index**：返回数组中第一个 pivot index —— 左侧和等于右侧和。

## 解法

总和 - prefix_sum - nums[i] = right_sum。当 prefix_sum == total - prefix_sum - nums[i] 即 `2 × prefix_sum + nums[i] == total` 时是 pivot。

## Python 实现

```python
from typing import List

class Solution:
    def pivotIndex(self, nums: List[int]) -> int:
        total = sum(nums)
        left = 0
        for i, x in enumerate(nums):
            if 2 * left + x == total:
                return i
            left += x
        return -1
```

## 复杂度

- 时间：**O(N)**
- 空间：O(1)

## 关键点

### 1. 推导

```
left_sum_at_i + nums[i] + right_sum_at_i = total
要求 left_sum_at_i == right_sum_at_i
    → 2 * left_sum + nums[i] = total
```

### 2. 边界 case

- 首位 (i=0)：left=0；只看 nums[i] == total - 其他 sum
- 末位 (i=n-1)：right=0；同理
- 空数组：返回 -1
- 单元素：left=0, right=0 → pivot=0

## 易错点

> [!pitfall]
> ❌ 算 right_sum 用循环 → 二重循环 O(N²)；
> ❌ 包含 nums[i] 在 left 里再比较 —— 公式错位；
> ❌ 没考虑负数 —— 公式仍工作；
> ❌ 多个 pivot 时返回最后一个 —— 题目要最小 index。

> [!key]
> 前缀和 + 一次扫描。这套适用于：subarray sum 等于 target、left-right 等价检测。

> [!followup]
> "找所有 pivot？" → 收集而非 return；"二维 grid 的 pivot row/col？" → 对每 row/col 算 sum 后同法；"包含特定元素的最小 pivot？" → 加约束即可。
