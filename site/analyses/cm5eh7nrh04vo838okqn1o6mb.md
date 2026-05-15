## 题目本质

**LC 312 Burst Balloons**：n 个气球各有分数 nums[i]。每次戳破气球 i 得 `left × nums[i] × right` 分（left/right 是当前相邻气球；边界视为 1）。气球戳破后相邻关系更新。求最大总分。

经典 **Interval DP** Hard。

## 解题思路

**反向思考**：不思考"先戳哪个"，而是**枚举最后戳哪个**。

`dp[l][r]` = 戳完 nums[l+1..r-1]（不含 l 和 r）能得的最大分数。其中 nums[l] 和 nums[r] 是"边界标记"（不实际戳）。

枚举区间内最后戳的 k：`dp[l][r] = max over k in (l, r) of dp[l][k] + dp[k][r] + nums[l] × nums[k] × nums[r]`

**为什么这样转移正确：** 当 k 是最后戳的，戳 k 时它的左右邻居就是 l 和 r（因为 (l, k) 和 (k, r) 区间内的气球都已戳完）。

## Python 实现

```python
from typing import List

class Solution:
    def maxCoins(self, nums: List[int]) -> int:
        # 两端加虚拟 1
        a = [1] + nums + [1]
        n = len(a)
        # dp[l][r] = 戳完开区间 (l, r) 内气球的最大分
        dp = [[0]*n for _ in range(n)]
        # 按区间长度递增枚举
        for length in range(2, n):
            for l in range(n - length):
                r = l + length
                best = 0
                for k in range(l + 1, r):
                    score = a[l] * a[k] * a[r] + dp[l][k] + dp[k][r]
                    best = max(best, score)
                dp[l][r] = best
        return dp[0][n - 1]
```

## 复杂度

- 时间：**O(N³)** 三重循环
- 空间：**O(N²)** DP 表

## 关键技术点

### 1. 两端加 1

便于处理边界。题目说"超出边界视为 1"。加虚拟 1 后所有计算统一。

### 2. 反向思考

正向"先戳哪个" 因为戳完邻居关系变 → 状态难表示。反向"最后戳哪个" 让 k 戳时邻居就是固定的 l 和 r。

### 3. 区间长度 ≥ 2 才有意义

`dp[l][r]` 区间 `(l, r)` 开区间至少含 1 个气球 → r - l ≥ 2。length 从 2 开始。

### 4. 递推顺序

按 length 升序，让小区间在大区间之前计算。`dp[l][k]` 和 `dp[k][r]` 都是更小区间。

## 边界 case

```python
sol = Solution()
assert sol.maxCoins([3,1,5,8]) == 167
# 戳 1: 3*1*5 = 15；剩 [3,5,8] 戳 5: 3*5*8 = 120；剩 [3,8] 戳 3: 1*3*8 = 24；剩 [8] 戳 8: 1*8*1 = 8 → 共 167
assert sol.maxCoins([]) == 0
assert sol.maxCoins([1]) == 1
```

## 易错点

> [!pitfall]
> ❌ 用正向"枚举先戳哪个"DP —— 状态难定义；
> ❌ 忘了加虚拟 1 边界 —— 公式 `a[l]*a[k]*a[r]` 在边界出错；
> ❌ 区间循环顺序错（按 l, r 直接 nested loop） —— 子问题未算先用；
> ❌ k 范围错 (l 和 r 不包括) —— k in [l+1, r-1]，即 range(l+1, r)。

> [!key]
> 区间 DP 经典：**反向思考 + 枚举最后操作**。同套路：LC 1547 Minimum Cost to Cut a Stick、LC 1000 Minimum Cost to Merge Stones、LC 1130 Min Cost Tree from Leaf Values。

> [!followup]
> "n 很大 (1000+)？" → O(N³) 大概率 TLE，需要更聪明算法或 monotonic 性质（一般无）；"返回最优戳法顺序？" → 回溯 dp，记录每个 dp[l][r] 的最优 k；"如果分数定义不同？" → 转移函数改即可，DP 框架不变。
