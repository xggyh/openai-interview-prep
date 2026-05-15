## 题目本质

**LC 30 Substring with Concatenation of All Words**：words 是一组**等长**单词。在 s 中找所有起始 index，使 s 从该 index 开始的子串恰好是 words 中所有词的某个**排列拼接**。

## 解法

每个 word 长度 L 相同。**滑窗 + Counter**。

对每个起始偏移 i ∈ [0, L)，滑窗按 L 步进，维护当前窗口的 word counter，与 words 的 counter 比较。

## Python 实现

```python
from collections import Counter
from typing import List

class Solution:
    def findSubstring(self, s: str, words: List[str]) -> List[int]:
        if not words or not s: return []
        word_len = len(words[0])
        word_count = len(words)
        total_len = word_len * word_count
        if len(s) < total_len: return []

        target = Counter(words)
        result = []

        # 按 word_len 个不同起始偏移，分别做滑窗
        for offset in range(word_len):
            left = offset
            cur = Counter()
            count = 0
            for right in range(offset, len(s) - word_len + 1, word_len):
                w = s[right:right + word_len]
                if w not in target:
                    cur.clear()
                    count = 0
                    left = right + word_len
                    continue
                cur[w] += 1
                count += 1
                # 如果某 word 超量，移除左侧直到不超
                while cur[w] > target[w]:
                    lw = s[left:left + word_len]
                    cur[lw] -= 1
                    count -= 1
                    left += word_len
                if count == word_count:
                    result.append(left)
                    # 移动左指针准备下一窗口
                    lw = s[left:left + word_len]
                    cur[lw] -= 1
                    count -= 1
                    left += word_len
        return result
```

## 复杂度

- 时间：**O(N × L)**，N = len(s)，L = word_len。每偏移 O(N/L) 步，每步 O(L) substring + counter ops。总 O((N/L) × L × L) = O(N × L) 因为有 L 个偏移。
- 空间：O(words_count)

## 关键技术点

### 1. 等长 word 是关键约束

允许把 s 按 L 步进切成"token 序列"，然后做"sliding window over tokens"。

### 2. L 个起始偏移

`offset = 0, 1, ..., L-1`：每个偏移独立滑窗。一个 word 跨多偏移会被多次检查，但每次 O(L) 不重叠。

### 3. 超量缩窗

当窗口里 word w 出现次数 > target[w]，左指针右移直到 cur[w] == target[w]。这是滑窗标准做法。

### 4. 匹配后 advance

`count == word_count` 时记 result，左指针前进 L（下一窗口的同样长度区间）。

## 暴力做法

对每个 i ∈ [0, N - total_len]，把 s[i:i+total_len] 切成 word_count 个 L-长 token，比较 Counter。O((N-total_len) × word_count) = O(N × word_count)。简单但不如滑窗优。

## 易错点

> [!pitfall]
> ❌ 忽略等长前提 —— 算法依赖；
> ❌ 一次滑窗不分 L 个偏移 —— 漏掉某些 alignment；
> ❌ Counter 没维护增量 —— 每步重新 build O(words)；
> ❌ 超量缩窗时只 -- 一次没 while —— 仍超；
> ❌ 移动右指针时步长用 1 而非 L —— 退化为 char-level 滑窗，错。

> [!key]
> 等长 word 把字符串看作 token 序列。滑窗 + Counter 是字符匹配类（"找包含所有 X 的 substring"）的核心模式。同思想：LC 76 Min Window Substring、LC 438 Find All Anagrams。

> [!followup]
> "words 不等长？" → 退化为更难的版本，用 Aho-Corasick + DP；"允许 word 重叠？" → 滑窗步长改为 1，重复匹配；"返回匹配的 word 排列？" → DFS 在每个 result index 还原顺序。
