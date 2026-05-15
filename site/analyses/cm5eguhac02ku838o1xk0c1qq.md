## 题目本质

**LC 736 Parse Lisp Expression**：解析嵌套 Lisp 表达式，支持 `let`（变量绑定）、`add`、`mult`、整数、变量。返回结果。

经典**递归下降解析 + 作用域栈**。Hard 题。

## 题目语义

```
expression = "(let x 2 (mult x (let x 3 y 4 (add x y))))"
// let x = 2
//   let x = 3, y = 4
//     add x y = 7
//   mult x (=2) 7 = 14
=> 14
```

## 解题思路

1. **Tokenize**：把 expr 切成 token list（括号 / 数字 / 标识符）
2. **递归 parse**：
   - 数字 → 返回 int
   - 变量 → 查 scope chain
   - `(op ...)` → 按 op 分发
3. **Scope**：每个 let 一个 scope frame，求值时优先从最内 scope 查

## Python 实现

```python
class Solution:
    def evaluate(self, expression: str) -> int:
        # Scope = list of dicts，最内 scope 在末尾
        scope: list[dict[str, int]] = [{}]

        # ---- tokenizer ----
        def tokenize(s: str) -> list[str]:
            tokens = []
            i = 0
            while i < len(s):
                if s[i] in "()":
                    tokens.append(s[i]); i += 1
                elif s[i] == " ":
                    i += 1
                else:
                    j = i
                    while j < len(s) and s[j] not in "() ":
                        j += 1
                    tokens.append(s[i:j])
                    i = j
            return tokens

        toks = tokenize(expression)
        pos = [0]   # 用 list 让闭包可修改

        # ---- parse + eval ----
        def lookup(name: str) -> int:
            for frame in reversed(scope):
                if name in frame:
                    return frame[name]
            raise KeyError(name)

        def parse_value() -> int:
            t = toks[pos[0]]
            if t == "(":
                pos[0] += 1
                op = toks[pos[0]]; pos[0] += 1
                if op == "add":
                    a = parse_value()
                    b = parse_value()
                    assert toks[pos[0]] == ")"; pos[0] += 1
                    return a + b
                if op == "mult":
                    a = parse_value()
                    b = parse_value()
                    assert toks[pos[0]] == ")"; pos[0] += 1
                    return a * b
                if op == "let":
                    scope.append({})
                    while True:
                        if toks[pos[0]] == "(":
                            # 下一个 token 是 expression
                            val = parse_value()
                            scope.pop()
                            assert toks[pos[0]] == ")"; pos[0] += 1
                            return val
                        # peek 下一个 token：是 var (后面跟值) 还是 expr 终值？
                        # 如果当前 token 后跟 ')'，则这就是 return 值
                        if pos[0] + 1 < len(toks) and toks[pos[0] + 1] == ")":
                            val = parse_value()
                            scope.pop()
                            assert toks[pos[0]] == ")"; pos[0] += 1
                            return val
                        # 否则 = (var, value-expr) 对
                        name = toks[pos[0]]; pos[0] += 1
                        val = parse_value()
                        scope[-1][name] = val
            # 不是 '('：要么数字要么变量
            pos[0] += 1
            if t.lstrip("-").isdigit():
                return int(t)
            return lookup(t)

        return parse_value()
```

## 复杂度

- 时间：**O(N)**，N = 表达式长度（每个 token 处理 O(1) 摊销，scope lookup 是 scope 深度，最坏 O(depth)，但 depth ≤ N）。**O(N²)** 最坏（深度嵌套 let）。
- 空间：**O(depth)** 调用栈 + scope。

## 关键设计点

### 1. 作用域链：栈

`let` 引入新作用域：push frame。结束 pop。变量查找从内到外：`for frame in reversed(scope)`。

### 2. let 的语法歧义

`(let x 2 ...)` 中 `...` 可能是：
- 更多变量绑定（如 `y 4 ...`）
- 或最终表达式（如 `(add x 1)` 或 `x`）

判断方法：看当前 token 后面是不是 `)` 或者 `(` 紧接。简化：直接 lookahead next token —— 如果 next 是 `)` 表示当前 token 是 return value（结束 let）。

### 3. 数字识别

`int(t)` 也能识别负数（`-3.4` 这种小数不在题目范围）。用 `t.lstrip("-").isdigit()` 判别可靠。

### 4. pos 用 list 闭包

Python 闭包无法重新绑定外层变量（要用 `nonlocal`）。把 pos 包成 list 用 `pos[0]` 修改简单。或用 `nonlocal pos`。

## 易错点

> [!pitfall]
> ❌ let 不开新 scope 直接改外层 —— 内层修改影响外层；
> ❌ scope lookup 只看最内 —— 找不到时应该往外走；
> ❌ let 解析时把 return value 当成 var binding —— 复杂的 lookahead 判断；
> ❌ tokenizer 不处理负号 / 多空格 / 嵌套；
> ❌ pos 用普通 int —— 闭包内修改无效。

> [!key]
> Lisp 解析是**编译器课程的 mini 版**：tokenizer → parser → evaluator。Scope 链是函数式语言核心。同模式：实现简单 calc、JSON parser、SQL WHERE 解析。

> [!followup]
> "支持函数定义 `(lambda x ...)`？" → 在 scope 里存 closure (params, body, captured scope)，调用时新 scope + 执行 body；"支持 if / cond？" → 加分支 op；"性能优化？" → AST 一次性构建后多次 eval（不必重复 parse）；"如何 detect 循环引用？" → eval 时不直接 substitute（lazy eval）。
