## 题目本质

**LC 416 Partition Equal Subset Sum**：数组能否分成**两个和相等**的子集。

经典 **0/1 Knapsack DP** —— 等价于"能否选出子集和 = total/2"。

## 解法

1. 如果 total 是奇数，必不能。返回 False。
2. target = total / 2。DP：`dp[i]` = 能否选出子集和恰好为 i。
3. 0/1 knapsack 风格：每元素决定要 or 不要。

## Python 实现（一维 DP）

```python
from typing import List

class Solution:
    def canPartition(self, nums: List[int]) -> bool:
        total = sum(nums)
        if total % 2: return False
        target = total // 2
        dp = [False] * (target + 1)
        dp[0] = True   # 空子集和 0
        for x in nums:
            # 必须倒序更新，避免同一元素被用多次
            for j in range(target, x - 1, -1):
                dp[j] = dp[j] or dp[j - x]
        return dp[target]
```

## 复杂度

- 时间：**O(N × target)** = O(N × sum/2)
- 空间：O(target) 一维 DP

## 关键点

### 1. 一维 DP 倒序

`dp[j] = dp[j] or dp[j - x]` 更新依赖 `dp[j-x]`（更小的 j）。**倒序遍历 j** 保证 `dp[j-x]` 是上一轮（不含 x）的值。

正序会导致同一 x 被多次"使用"（变成完全背包）。

### 2. dp[0] = True

空子集和 0 是 trivially 可行的 base。

### 3. Bit-set 优化（Python 大整数）

```python
def canPartition(self, nums):
    total = sum(nums)
    if total % 2: return False
    target = total // 2
    bits = 1   # bit i = 1 表示和 i 可达
    for x in nums:
        bits |= bits << x
    return (bits >> target) & 1 == 1
```

每个 x 用一次 bit shift + OR，O(N × target / 64) 极快。

## 边界 case

```python
sol = Solution()
assert sol.canPartition([1,5,11,5]) == True
assert sol.canPartition([1,2,3,5]) == False
assert sol.canPartition([1,1]) == True
assert sol.canPartition([1]) == False
```

## 易错点

> [!pitfall]
> ❌ 一维 DP 正序更新 —— 完全背包；
> ❌ 没判断 total 奇偶 —— 浪费计算；
> ❌ dp 大小写错（应是 target+1）；
> ❌ 初始 dp[0]=False —— 全 False 永远；
> ❌ 二维 DP 浪费 O(N×target) 空间（但更直观，面试可先写）。

> [!key]
> 0/1 knapsack 的经典变种 —— "求和=target 的子集存在性"。同模板：LC 494 Target Sum、LC 474 Ones and Zeroes、LC 1049 Last Stone Weight II。**bit-set 优化是 LC 上面试加分项**。

> [!followup]
> "返回切分方案？" → 回溯 dp，倒推选了哪些；"K 个相等子集 (K > 2)？" → LC 698，回溯 + 剪枝；"每元素可用多次？" → 完全背包（正序更新）；"如果 num 很大但 N 小？" → meet-in-the-middle，分两半各 2^(N/2) 枚举。
