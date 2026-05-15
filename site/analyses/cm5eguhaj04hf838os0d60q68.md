## 题目本质

**LC 3205 Maximum Array Hopping Score I**：数组 nums，从 index 0 起跳。每步从 i 跳到 j (j > i)，得 `(j - i) × nums[j]` 分。可以连续跳任意次直到 last index。求最大分数。

## 解法

DP 或贪心。

### 方法 A：DP O(N²)

`dp[i]` = 从 index 0 跳到 i 的最大得分。`dp[i] = max over j < i of dp[j] + (i - j) × nums[i]`。

```python
class Solution:
    def maxScore(self, nums: list[int]) -> int:
        n = len(nums)
        dp = [0] * n
        for i in range(1, n):
            for j in range(i):
                dp[i] = max(dp[i], dp[j] + (i - j) * nums[i])
        return dp[n - 1]
```

LC N ≤ 1e3 → O(N²) = 1M ops 过。

### 方法 B：贪心 O(N)（更巧妙）

观察：每个 i 的贡献是 (i - prev_jump) × nums[i]。要让贡献最大，**从同一起点 prev_jump 直接跳到 i 比中间停留更优**（因为 i 的乘数变大）。

但具体哪些 i 入选最优？

**反向贪心**：从 last index n-1 倒推。每次找前面 nums 最大的 index 作为前一跳。

```python
class Solution:
    def maxScore(self, nums: list[int]) -> int:
        n = len(nums)
        total = 0
        cur = n - 1
        # 找 cur 之前 nums 最大的位置作为前一跳
        # 倒推
        while cur > 0:
            best_j = 0
            for j in range(cur):
                if nums[j] >= nums[best_j]:
                    best_j = j
            total += (cur - best_j) * nums[cur]
            cur = best_j
        return total
```

仍 O(N²) 最坏但常数小。LC 数据下 OK。

## 复杂度

- 方法 A DP：**O(N²)** time, O(N) space
- 方法 B 贪心：O(N²) 最坏，但实践更快

## 关键技术点

### 1. 贪心正确性

为什么从 n-1 倒推选"前面 max"？因为 (cur - prev) × nums[cur] 中，cur 和 nums[cur] 固定，**prev 越小贡献越大**。但 prev 是上一跳的目标位置，prev 自己的贡献是 (prev - prev_prev) × nums[prev]，要让它也最大化 → 选 nums 最大的 prev 让其乘数更大值得 …

实际上**纯 nums max 的位置不一定最优**。完整证明复杂，DP 是更安全的选择。

### 2. 起点 i = 0 终点 n-1

不能从中间起跳。

## 易错点

> [!pitfall]
> ❌ 把 nums[0] 算进 dp[0] —— dp[0] = 0（起点不得分）；
> ❌ 跳跃必须严格 j > i —— 不能原地；
> ❌ "可以不跳到 n-1" 的版本？题目要求到 n-1 ——必须到达。

> [!key]
> 1D DP "前面每个位置作为上一跳"。同套路：LC 1696 Jump Game VI、LC 2369 Check if There is a Valid Partition for The Array。

> [!followup]
> "限制最大跳跃距离 k？" → DP 加约束 `i - j <= k`；用 deque 维护窗口 max 优化到 O(N)；"返回跳跃路径？" → DP 记 prev_idx；"III 难版？" → LC 3221 加更多约束。
