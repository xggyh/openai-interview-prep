## 题目本质

**LC 249 Group Shifted Strings**：把字符串按"shifting 等价类"分组。两个字符串等价当且仅当它们能通过 **shift（所有字符同步 +k）** 互相转换。例如 `"abc"` 和 `"bcd"` 等价（都 shift +1）。

经典**hash key normalization**题。

## 解题思路

为每个 string 算一个 **规范化 key**：把它 shift 到"第一个字符是 'a'" 那种规范化形式。

例：
- `"abc"` → 第一个字符 a→a (offset 0)，整体不变 → `"abc"`
- `"bcd"` → 第一个字符 b → a (offset -1)，整体减 1 → `"abc"`
- `"xyz"` → x → a (offset -23 mod 26 = 3)，但 xyz +3 = abc → `"abc"`

或者用**相邻字符差**作为 key：`"abc"` 差是 `(1, 1)`，`"bcd"` 差也是 `(1, 1)`，`"xyz"` 差也是 `(1, 1)`。差完全相等就同类。

差分法更稳健，因为不需要考虑 26 模运算。

## Python 实现（差分 key）

```python
from collections import defaultdict
from typing import List

class Solution:
    def groupStrings(self, strings: List[str]) -> List[List[str]]:
        groups = defaultdict(list)
        for s in strings:
            # key = tuple of (s[i+1] - s[i]) mod 26
            if len(s) == 1:
                key = ()
            else:
                diffs = tuple((ord(s[i+1]) - ord(s[i])) % 26 for i in range(len(s) - 1))
                key = diffs
            groups[key].append(s)
        return list(groups.values())
```

## 关键点

### 1. 为什么 mod 26

Shift 是 wrap-around：`y + 1 = z`，`z + 1 = a`（不是 `{`）。差分必须 mod 26。

例：`"az"` 差是 `(25,)`。`"ba"` 差也是 `(25,)`（b→a 是 -1，mod 26 = 25）。它们等价吗？

- `"az"` shift +1 = `"ba"` ✓ 等价
- 差 mod 26 都是 25 ✓ key 相同

### 2. 单字符 string

`"a"`, `"b"`, `"c"` 都互相 shift 等价，但他们没有 diff（长度 1）。用 key = `()`（空 tuple）把它们都分到一组。

### 3. 为什么不直接用 "shift 到 a 开头" 作 key

那个方法也对：

```python
def normalize(s):
    offset = ord(s[0]) - ord('a')
    return ''.join(chr((ord(c) - ord('a') - offset) % 26 + ord('a')) for c in s)
```

但差分法更短 + 直接是 tuple 不需要 string concat。

## 复杂度

- 时间：**O(N × L)**，N = strings 数，L = avg length
- 空间：O(N × L) 用于 group dict

## 边界 case

```python
sol = Solution()
result = sol.groupStrings(["abc","bcd","acef","xyz","az","ba","a","z"])
# 期望分组：
# ["abc","bcd","xyz"]    (diff (1,1))
# ["acef"]               (diff (2,2,1))
# ["az","ba"]            (diff (25,))
# ["a","z"]              (single char)
sorted_result = sorted(sorted(g) for g in result)
print(sorted_result)
```

## 易错点

> [!pitfall]
> ❌ 差分忘 mod 26 —— `"az"` 和 `"ba"` 算成不同组；
> ❌ 单字符 key 用空 string 而非 tuple —— 跟其他长度 1 区分但可能与某些怪异 key 撞；用 tuple 安全；
> ❌ 用 dict 但 key 是 list —— list 不 hashable；
> ❌ 改写"全部 shift 到 'a' 开头"时算 offset 没 mod —— `"xyz"` 把 'x' shift 到 'a' 要 mod。

> [!key]
> "等价类分组" 题的核心：找一个**规范化函数**让等价的元素映射到同一 key。这类问题还有：LC 49 Group Anagrams（key = sorted string）、LC 36 Valid Sudoku（key = (row, col, box) tuple）、LC 1010 Pairs of Songs（key = duration mod 60）。

> [!followup]
> "如果允许大小写都算 shift？" → 26 改 52，分别处理大小写；"如果是 unicode？" → 用 char codepoint，mod 改成 unicode range；"如果用 reverse（z→y→x...）shift？" → 那就是 -1 操作，差分仍 mod 26；"如何处理 case-insensitive？" → 先全转小写再分组。
