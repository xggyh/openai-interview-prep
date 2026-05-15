## 题目本质

**LC 187 Repeated DNA Sequences**：DNA 字符串，找所有长度 10 出现**多于一次**的子串。返回 list（去重）。

## 解法

滑动窗口 + hash set。扫一遍，每 10 字符子串 hash 看是否见过。

## Python 实现

```python
from typing import List

class Solution:
    def findRepeatedDnaSequences(self, s: str) -> List[str]:
        seen: set[str] = set()
        repeated: set[str] = set()
        for i in range(len(s) - 9):
            sub = s[i:i+10]
            if sub in seen:
                repeated.add(sub)
            else:
                seen.add(sub)
        return list(repeated)
```

## 复杂度

- 时间：**O(N × 10)** = O(N)（hash 一个 10-char string 是 O(10)）
- 空间：O(N)（最多 N 个 unique substring）

## 进阶：Rolling Hash

如果 substring 长度 K 大，直接 hash O(K) 每次。Rabin-Karp rolling hash 把 hash 计算降为 O(1) per shift：

```python
def find_repeated(s, K=10):
    if len(s) < K: return []
    # 4 nucleotides → base 4
    base, mod = 4, 2**63 - 1
    mapping = {'A':0, 'C':1, 'G':2, 'T':3}
    h = 0
    for i in range(K):
        h = h * base + mapping[s[i]]
    seen, repeated = {h}, set()
    high_pow = base ** (K-1)
    for i in range(K, len(s)):
        # rolling: remove s[i-K], add s[i]
        h = (h - mapping[s[i-K]] * high_pow) * base + mapping[s[i]]
        if h in seen:
            repeated.add(s[i-K+1:i+1])
        else:
            seen.add(h)
    return list(repeated)
```

LC 数据 N ≤ 1e5，朴素 O(10N) 也过。Rolling hash 是 follow-up 谈话点。

## 关键点

### 1. 滑窗 K=10

每个 substring 长度 10 是固定的。`for i in range(len(s)-9)` 不要算错边界。

### 2. set 去重

`repeated` 用 set 避免一个 substring 出现 3+ 次时多次 push。

### 3. Bit encoding（更优雅）

A/C/G/T 各 2 bit → 10 char × 2 bit = 20 bit < 32 bit。可以把 substring 编码成 int 作为 hash key，省空间。

## 易错点

> [!pitfall]
> ❌ 循环边界 `range(len(s)-10)` 漏最后一个 substring（应是 -9）；
> ❌ 用 list 而非 set 去重 —— 重复元素 + 慢；
> ❌ Rolling hash 模数选不好（如 2**32）易碰撞；
> ❌ 假设字符集只 ACGT —— 题目通常保证，但代码可加 assert。

> [!key]
> 滑动窗口 + hash set 找重复子串是面试经典套路。Rolling hash 是优化点，回答 follow-up 时提到加分。

> [!followup]
> "K 任意大小？" → 直接 substring slice + set 即可；K 极大用 rolling hash；"返回最长重复 substring？" → LC 1044，二分长度 + rolling hash；"流式 DNA 数据？" → 维护 sliding window hash set；"找出现次数 ≥ k 次？" → 用 Counter 代替 set + threshold filter。
