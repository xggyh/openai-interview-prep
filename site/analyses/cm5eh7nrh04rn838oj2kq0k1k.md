## 题目本质

**LC 167 Two Sum II - Input Array Is Sorted**：升序数组，找两数之和 = target，返回 1-indexed 索引。

经典**双指针**题。比普通 Two Sum 简单 —— 输入已排序。

## Python 实现

```python
from typing import List

class Solution:
    def twoSum(self, numbers: List[int], target: int) -> List[int]:
        lo, hi = 0, len(numbers) - 1
        while lo < hi:
            s = numbers[lo] + numbers[hi]
            if s == target:
                return [lo + 1, hi + 1]
            elif s < target:
                lo += 1
            else:
                hi -= 1
        return []
```

## 复杂度

- 时间：**O(N)** 双指针一遍扫
- 空间：**O(1)**

## 为什么双指针正确

数组升序时：
- `s < target` → 必须增大 → 只能 lo++（hi-- 只会更小）
- `s > target` → 必须减小 → 只能 hi--

每次至少移一个指针，总步数 ≤ N，且不会漏正确组合（如果答案是 (i, j) 当 lo 到 i 时，hi 还 ≥ j；若 hi < j 之前会先碰到 i+x 让 s 偏小让 lo 继续 + 不会越过 j；反之类似）。

## 与普通 Two Sum (LC 1) 对比

| LC 1 (unsorted) | LC 167 (sorted) |
|---|---|
| 用 hash map O(N) 空间 | 双指针 O(1) 空间 |
| 一遍扫 | 双指针一遍 |

## 易错点

> [!pitfall]
> ❌ 返回 0-indexed —— 题目要 1-indexed；
> ❌ `lo <= hi` 而非 `lo < hi` —— 同位置取两次；
> ❌ 没排序就上双指针（在其他场景） —— 失效；
> ❌ 假设有唯一解：题目保证，但实际多解时双指针返回第一个找到的（也合理）。

> [!key]
> 升序数组 + 找和：第一反应双指针。这套适用于：3sum、4sum 的内层、smallest difference pair、closest sum。

> [!followup]
> "Three Sum (排序 + 双指针)？" → 固定一个 + 双指针扫剩余；"如果数组允许重复，需要去重？" → 跳过相邻相同；"找所有 pair 不止一个？" → 累加结果而非 return，跳过 dup；"如果数组是循环排序？" → 找 pivot 后双指针，复杂度仍 O(N)。
