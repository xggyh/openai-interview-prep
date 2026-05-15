## 题目本质

**LC 3350 Adjacent Increasing Subarrays Detection II**：找最大 k 使得存在两个**相邻**严格递增子数组，长度都为 k。返回最大 k。

## 解法

1. 算 `inc[i]` = 以 i 结尾的最长严格递增 run 长度
2. 对每个位置 i，能否做 (k 长 ending at i) + (k 长 starting at i+1)
3. 二分 k 或贪心扫描

**贪心两次扫**：
- 算所有"以 i 起的递增 run 长度"为 `runs[i]`
- 答案 = max over i of `max(runs[i]//2, min(runs[i], runs[i + runs[i]]))`

## Python 实现

```python
from typing import List

class Solution:
    def maxIncreasingSubarrays(self, nums: List[int]) -> int:
        n = len(nums)
        # runs[i] = 从 i 开始严格递增 run 的长度
        runs = [1] * n
        for i in range(n - 2, -1, -1):
            if nums[i] < nums[i + 1]:
                runs[i] = runs[i + 1] + 1
        best = 0
        for i in range(n):
            # 选项 A：把 runs[i] 平分成两段
            best = max(best, runs[i] // 2)
            # 选项 B：runs[i] 这段（长 r）+ 下一段
            r = runs[i]
            nxt_start = i + r
            if nxt_start < n:
                nxt_r = runs[nxt_start]
                best = max(best, min(r, nxt_r))
        return best
```

## 复杂度

- 时间：**O(N)**
- 空间：O(N) runs

## 关键技术点

### 1. runs[i] 含义

从 index i 开始向右连续严格递增的最长长度。倒序计算：if nums[i]<nums[i+1] then runs[i]=runs[i+1]+1 else 1。

### 2. 两种 split 方式

- A. 单一递增段 runs[i] 截两半：每段 runs[i]//2
- B. 当前段 + 紧邻下段：min(runs[i], runs[i + runs[i]])

每个 i 取两种最大。

### 3. 边界

`nxt_start = i + runs[i]` 可能 >= n（最后一段）。check 边界。

## 易错点

> [!pitfall]
> ❌ 用二分 + check 是 O(N log N)，简单扫 O(N) 已足；
> ❌ runs 正向计算混乱 —— 倒序更自然（从右往左）；
> ❌ "严格" vs "非严格" 递增 —— 题目通常严格用 `<`；
> ❌ 单一段截半时用 `//` 整除（k 是整数）。

> [!key]
> "连续 run 长度" 是 array 题常见预处理。同模板：LC 1437 Check If All 1's Are at Least Length K Places Away、LC 2348 Number of Zero-Filled Subarrays。

> [!followup]
> "返回两段具体起点？" → 记录 best 时同步存 i 和 nxt_start；"求 k 段 ?" → 滑窗 + sliding max 不够，要 DP；"严格递减子数组？" → 对称改 inc 条件。
