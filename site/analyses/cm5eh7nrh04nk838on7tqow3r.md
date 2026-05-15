## 题目本质

**LC 20 Valid Parentheses**：判断 `( ) [ ] { }` 组成的字符串是否合法。

## 解法

**栈**：遇到开括号 push，遇到闭括号 pop 检查匹配。

## Python 实现

```python
class Solution:
    def isValid(self, s: str) -> bool:
        pair = {")": "(", "]": "[", "}": "{"}
        stack = []
        for ch in s:
            if ch in "([{":
                stack.append(ch)
            else:
                if not stack or stack[-1] != pair[ch]:
                    return False
                stack.pop()
        return not stack
```

## 复杂度

- 时间：**O(N)**
- 空间：O(N) 栈

## 易错点

> [!pitfall]
> ❌ 忘了最终 `return not stack` —— `"((("` 应返回 False；
> ❌ pair map 方向反 —— 用闭→开方便 lookup；
> ❌ Pop 前没检查 stack 空 —— IndexError。

> [!key]
> 括号匹配是栈最纯粹的应用。这套思路通用于 calculator、HTML/XML 验证、Lisp 语法检查。

> [!followup]
> "如果只允许一种括号？" → 简单：count + 不能让 count 变负；"如果允许 wildcard `*` 当任意？" → 用两个 count 区间 [lo, hi] 维护可能的 open 数（LC 678）；"输出第一个错位的位置？" → push 时记 index，pop 检查时拿出来；"匹配最大有效长度？" → LC 32 用 DP / 栈。
