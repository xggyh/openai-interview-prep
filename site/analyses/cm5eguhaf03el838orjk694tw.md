## 题目本质

**LC 1807 Evaluate the Bracket Pairs of a String**：字符串 s 含 `(key)` 形式的占位符。给一组 (key, value) 映射，把所有 `(key)` 替换为 value；找不到 key 替换为 `"?"`。

## Python 实现

```python
from typing import List

class Solution:
    def evaluate(self, s: str, knowledge: List[List[str]]) -> str:
        kv = dict(knowledge)
        result = []
        i = 0
        while i < len(s):
            if s[i] == '(':
                j = s.index(')', i)
                key = s[i+1:j]
                result.append(kv.get(key, "?"))
                i = j + 1
            else:
                result.append(s[i])
                i += 1
        return "".join(result)
```

## 复杂度

- 时间：**O(N)**，N = len(s)
- 空间：O(K + N) 字典 + 输出

## 关键点

### 1. dict lookup

`dict.get(key, "?")` 优雅处理"找不到"。

### 2. 切片找闭括号

`s.index(')', i)` 从位置 i 开始找下一个 ')'。题目保证括号匹配且无嵌套。

### 3. 嵌套？

LC 1807 不嵌套。如果嵌套要递归 / 栈处理（类似 Decode String LC 394）。

## 易错点

> [!pitfall]
> ❌ 用正则 `re.sub` 配 lambda：可行但 import 重；
> ❌ 用 `s.replace(f"({k})", v)` 多次替换：O(N × K) 慢 + 替换后产生新 `(key)` 风险；
> ❌ 没处理 unknown key（应替 "?" 不是空）；
> ❌ 嵌套 `((a))` 情况不在题目内但要意识到。

> [!key]
> 字符串模板替换的最简形式 = 单次扫描 + dict lookup。这是工业级模板引擎（Jinja, Mustache）的内核简化版。

> [!followup]
> "嵌套占位符 `(a(b)c)`？" → 栈或递归（参考 Decode String）；"value 自身可能含 `(key)`？" → iterative substitution until 不变（类似 Lisp let）；"如何流式？" → 状态机逐字符。
