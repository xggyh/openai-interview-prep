## 题目本质

**LC 394 Decode String**：解码格式 `k[encoded_string]`，k 是次数，可嵌套。例 `"3[a2[c]]"` → `"accaccacc"`。

## 解法

**栈**：遇 `[` push 当前状态 (counter_str, partial_result)；遇 `]` pop 拼接。

## Python 实现

```python
class Solution:
    def decodeString(self, s: str) -> str:
        stack: list[tuple[int, str]] = []   # (k, prefix)
        cur = ""
        k = 0
        for ch in s:
            if ch.isdigit():
                k = k * 10 + int(ch)
            elif ch == "[":
                stack.append((k, cur))
                k = 0
                cur = ""
            elif ch == "]":
                cnt, prev = stack.pop()
                cur = prev + cur * cnt
            else:
                cur += ch
        return cur
```

## 复杂度

- 时间：**O(N + |output|)**
- 空间：O(嵌套深度 + 输出长度)

## 关键点

### 1. k 可能是多位数

`"123[a]"`：遇到 '1' k=1，'2' k=12，'3' k=123。累加用 `k = k * 10 + int(ch)`。

### 2. 嵌套用栈

每遇 `[`，把外层 "当前结果 + 即将用的 k" push 入栈，重置 cur 开始新嵌套。`]` 时 pop 外层，把 `cur × k + prev` 拼回。

### 3. 字符直接累加 cur

普通字符 / 数字 / 括号外的，直接 `cur += ch`。

## 边界 case

```python
sol = Solution()
assert sol.decodeString("3[a]2[bc]") == "aaabcbc"
assert sol.decodeString("3[a2[c]]") == "accaccacc"
assert sol.decodeString("2[abc]3[cd]ef") == "abcabccdcdcdef"
assert sol.decodeString("") == ""
assert sol.decodeString("abc") == "abc"
```

## 易错点

> [!pitfall]
> ❌ k 只支持 1 位 —— `123[a]` 算成 `1[a]23[a]`；
> ❌ Pop 顺序：先 pop 出 (k, prev)，新 cur = prev + 旧 cur * k —— 注意 prev 在前；
> ❌ 在 `]` 时 stack 空：题目保证合法，但工业级要 sanity check；
> ❌ 用递归实现：可行但 stack 直观。

> [!key]
> 嵌套表达式 = 栈。同模板：calculator (LC 224, 227)、Lisp 解析、JSON 解析。

> [!followup]
> "支持负数 k？" → 输出反转 `s[::-1]` × abs(k)；"流式输入？" → 同样栈，逐字符处理；"返回每个 '[' 的展开范围？" → 栈里再记 start_idx；"非数字 prefix？" → 加变量类型 stack。
