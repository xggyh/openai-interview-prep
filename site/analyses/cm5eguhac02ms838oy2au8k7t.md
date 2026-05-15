## 题目本质

**LC 806 Number of Lines To Write String**：给一个字母宽度数组 `widths[26]`（每个字母占多少像素），和一个字符串 `s`。每行最大 100 像素，按顺序写下来。返回 `[行数, 最后一行的像素宽度]`。

## 解题思路

贪心扫一遍：维护当前行宽 `cur`，每个字符检查"能不能塞进当前行"，不能就换行。

## Python 实现

```python
from typing import List

class Solution:
    def numberOfLines(self, widths: List[int], s: str) -> List[int]:
        lines = 1
        cur = 0
        MAX = 100
        for ch in s:
            w = widths[ord(ch) - ord('a')]
            if cur + w > MAX:
                lines += 1
                cur = w
            else:
                cur += w
        return [lines, cur]
```

## 复杂度

- 时间：**O(N)**，N = len(s)
- 空间：O(1)

## 边界 case

```python
sol = Solution()
# 全 1 宽度，s = 26 a's → 100 像素一行刚好不够装第 26 个，2 行
widths = [10] + [1] * 25  # a=10, b-z=1
assert sol.numberOfLines(widths, "abcdefghijklmnopqrstuvwxyz") == [3, 60]
assert sol.numberOfLines([1]*26, "a") == [1, 1]
assert sol.numberOfLines([1]*26, "a"*100) == [1, 100]
assert sol.numberOfLines([1]*26, "a"*101) == [2, 1]
```

## 易错点

> [!pitfall]
> ❌ `lines = 0` 起始 —— 应该 1（空 string 也算 1 行，但实际 s 至少 1 字符）；
> ❌ 比较用 `>=` 而非 `>` —— 刚好 100 的不应换行；
> ❌ 换行后 cur = 0 然后 += w，等价于 cur = w 但要小心顺序；
> ❌ ord 索引忘了 `- ord('a')` —— index 越界；
> ❌ 假设 `s` 非空 —— 题目通常保证。

> [!key]
> 这是 Google 拿来做"暖场"的 easy 题。重点是把 if/else 写清楚 + 边界讨论清楚（"刚好 100 算不算？" 题目说 "If writing this letter would cause the line to exceed 100"，所以恰好等于 100 不需换行）。

> [!followup]
> "如果 width 数组超长（非 26 字母）？" → 用 dict 映射；"如果有空格 / 特殊符号要换行？" → 加入 widths 或特殊处理；"返回每行的内容？" → 在循环里 append 到 list of strings；"如果字符串有 unicode？" → 用 codepoint 索引，widths 改为 dict[char, int]。
