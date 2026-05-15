## 题目本质

**LC 139 Word Break**：给字符串 `s` 和字典 `wordDict`，判断能否把 `s` 切分成字典里的词的拼接。`s` 长度 ≤ 300，单词 ≤ 20 字符，字典 ≤ 1000 个词。

**DP** 经典题，Google 高频。

## 解题思路

`dp[i]` = `s[0:i]` 能否被 break。
- base: `dp[0] = True`（空串 trivially OK）
- 转移：`dp[i] = True` 当且仅当存在 `j ∈ [0, i)` 使 `dp[j] == True` 且 `s[j:i] ∈ wordSet`

## Python 实现

```python
from typing import List

class Solution:
    def wordBreak(self, s: str, wordDict: List[str]) -> bool:
        word_set = set(wordDict)
        n = len(s)
        dp = [False] * (n + 1)
        dp[0] = True
        for i in range(1, n + 1):
            for j in range(i):
                if dp[j] and s[j:i] in word_set:
                    dp[i] = True
                    break
        return dp[n]
```

## 优化版：只看 j 在合理 word length 范围

```python
class Solution:
    def wordBreak(self, s: str, wordDict: List[str]) -> bool:
        word_set = set(wordDict)
        max_len = max(map(len, wordDict)) if wordDict else 0
        n = len(s)
        dp = [False] * (n + 1)
        dp[0] = True
        for i in range(1, n + 1):
            # 只检查长度 ≤ max_len 的后缀
            for j in range(max(0, i - max_len), i):
                if dp[j] and s[j:i] in word_set:
                    dp[i] = True
                    break
        return dp[n]
```

把 inner loop 截到 `max_len` 内，避免无用扫描。

## 复杂度

- 时间：**O(N² × L)**（朴素，N = len(s)，L = avg word length，因为 substring slice 和 hash 各 O(L)）
- 优化后：**O(N × max_len × L)**
- 空间：O(N + total_dict_chars)

## 替代：BFS / DFS + Memoization

```python
class Solution:
    def wordBreak(self, s: str, wordDict: List[str]) -> bool:
        word_set = set(wordDict)
        from functools import lru_cache
        @lru_cache(maxsize=None)
        def helper(idx: int) -> bool:
            if idx == len(s):
                return True
            return any(s[idx:idx+L] in word_set and helper(idx+L)
                       for L in range(1, len(s)-idx+1))
        return helper(0)
```

更直观但常数大。

## 关键技术点

### 1. 为什么 break inner loop

找到任一拆分就够了，不必继续看其他 j。

### 2. 字典转 set

`in wordDict` (list) 是 O(K)，K = 字典大小。转 set 后 O(1)。

### 3. Substring `s[j:i]` 的成本

Python `s[j:i]` 是 O(i-j) —— 实际复杂度比表面看多一维 L。所以理论上 N² × L。当 L 大时（如 1000），瓶颈在 substring 本身。

## 边界 case

```python
assert Solution().wordBreak("leetcode", ["leet","code"]) == True
assert Solution().wordBreak("applepenapple", ["apple","pen"]) == True
assert Solution().wordBreak("catsandog", ["cats","dog","sand","and","cat"]) == False
assert Solution().wordBreak("", ["a"]) == True            # 空串
assert Solution().wordBreak("a", []) == False             # 空字典
```

## 易错点

> [!pitfall]
> ❌ `dp` 大小忘了 +1（要存 dp[N]）；
> ❌ `dp[0]` 没置 True —— 永远 False；
> ❌ 字典用 list 直接 `s[j:i] in wordDict` —— O(N²×K) 慢；
> ❌ 转 set 后忘了考虑空字典；
> ❌ DFS 解忘了 memoization —— 指数时间。

> [!key]
> 经典 1D DP："s 前 i 位"是 state，转移枚举最后一个 word 的起点 j。这套模式还能解：LC 140 word break II（返回所有切分）、LC 1255（高分单词 DP）。

> [!followup]
> "返回所有切分方案？" → LC 140，DFS + memoization 记录所有路径；"返回最少 word 数？" → DP 改为最小值；"如果字典超大（1M+）？" → 用 Trie 替换 set，inner loop 沿 Trie 一字一字匹配；"流式输入 s？" → 不再可行，词典 Aho-Corasick 多模匹配。
