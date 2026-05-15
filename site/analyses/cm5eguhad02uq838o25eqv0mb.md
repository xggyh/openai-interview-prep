## 题目本质

**LC 1092 Shortest Common Supersequence**：返回**最短**的字符串，使其同时包含 s1 和 s2 作为 subsequence。Hard 题。

## 解法

**LCS + 重建**。
1. 找 LCS(s1, s2)（最长公共子序列）
2. 输出 = s1 + s2 - LCS（重叠部分只算一次）

实现：DP 算 LCS 长度，回溯重建 SCS。

## Python 实现

```python
class Solution:
    def shortestCommonSupersequence(self, s1: str, s2: str) -> str:
        m, n = len(s1), len(s2)
        # dp[i][j] = LCS length of s1[:i], s2[:j]
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(1, m+1):
            for j in range(1, n+1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        # 回溯重建 SCS
        i, j = m, n
        result = []
        while i > 0 and j > 0:
            if s1[i-1] == s2[j-1]:
                result.append(s1[i-1])
                i -= 1; j -= 1
            elif dp[i-1][j] >= dp[i][j-1]:
                result.append(s1[i-1])
                i -= 1
            else:
                result.append(s2[j-1])
                j -= 1
        # 处理剩余前缀
        while i > 0:
            result.append(s1[i-1]); i -= 1
        while j > 0:
            result.append(s2[j-1]); j -= 1
        return "".join(reversed(result))
```

## 复杂度

- 时间：**O(M × N)**
- 空间：O(M × N) DP 表

## 关键技术点

### 1. SCS = M + N - LCS

LCS 部分在两个 string 都出现，**只算一次**。所以 SCS 长度 = M + N - LCS_length。

### 2. 回溯方向

从 dp[m][n] 倒推：
- s1[i-1] == s2[j-1]：是 LCS 的一部分，append + i,j 都减
- 否则：根据 dp[i-1][j] vs dp[i][j-1] 决定从 s1 拿一个 char 还是 s2 拿一个

### 3. 拼接顺序

倒序构建（从尾巴开始），最后 reverse。

### 4. 剩余前缀

`i > 0` 或 `j > 0` 时，其中一个 string 还没用完，全部 append。

## 边界 case

```python
sol = Solution()
assert sol.shortestCommonSupersequence("abac", "cab") == "cabac"  # 或同长度的其他答案
# LCS = "ab" or "ac"，SCS 长度 = 4+3-2 = 5
assert sol.shortestCommonSupersequence("abc", "") == "abc"
assert sol.shortestCommonSupersequence("", "xyz") == "xyz"
```

## 易错点

> [!pitfall]
> ❌ LCS DP 边界 i=0 or j=0 时 dp=0（用 +1 size 数组自然处理）；
> ❌ 回溯方向反 —— 应从 (m, n) 倒推；
> ❌ s1==s2 时 append 两次 —— 必须只 append 一次；
> ❌ 处理剩余前缀漏一边 —— 两边都要 while；
> ❌ 拼好后没 reverse —— 顺序反。

> [!key]
> SCS = LCS + 重建。LCS 是字符串 DP 之神。同模板：Edit Distance (LC 72)、Distinct Subsequences (LC 115)、Interleaving String (LC 97)。

> [!followup]
> "找最长 supersequence？" → 没意义（无限长）；"K 个 string 的 SCS？" → NP-hard 一般；K=3 时 O(N³) DP；"返回 SCS 的字典序最小者？" → 回溯时 tie-break 选小字符；"打印 LCS 自身？" → 同样回溯，只在相等时 append。
