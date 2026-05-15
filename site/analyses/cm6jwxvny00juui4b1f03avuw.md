## 题目本质

**String Template Substitution with Variable Replacement**：template 字符串含占位符（如 `${var}`），替换为 mapping 中对应 value。**支持嵌套**：value 自身可包含 placeholder 需进一步解析。

类似 Jinja / Mustache 简化版，但有循环引用 + 递归展开。

## 解法

**递归 + visited set**（cycle detection）。

```python
import re

class TemplateError(Exception): pass

class TemplateEngine:
    PATTERN = re.compile(r'\$\{(\w+)\}')

    def __init__(self, mapping: dict[str, str]):
        self.map = mapping

    def render(self, template: str) -> str:
        return self._expand(template, set())

    def _expand(self, s: str, visited: set[str]) -> str:
        def repl(m):
            key = m.group(1)
            if key not in self.map:
                return m.group(0)   # 找不到保留原样（或 raise）
            if key in visited:
                raise TemplateError(f"circular reference at {key}")
            new_visited = visited | {key}
            return self._expand(self.map[key], new_visited)
        return self.PATTERN.sub(repl, s)
```

## 复杂度

- 时间：取决于嵌套深度 × template 长度。最坏 O(N × D)，D = 最大嵌套深度
- 空间：O(D) 递归栈

## 关键技术点

### 1. 递归展开

`${a}` → 替换为 map[a]，map[a] 自己可能含 `${b}` 继续展开。直到没有 placeholder。

### 2. Cycle Detection

如果 `a → b → a`，无限展开。**visited set** 在递归路径上记录已访问 key，再次遇到 raise。

### 3. Regex 占位符

`\$\{(\w+)\}` 匹配 `${var_name}`。如果支持嵌套语法 `${${prefix}_name}`，需要从内向外解析（先 expand 内层 placeholder）。

### 4. 回溯 visited

`new_visited = visited | {key}` 创建新 set，不污染外层调用（每条 expand 路径独立 visited）。

## 嵌套语法 `${${prefix}_name}` 处理

```python
def render_nested(s, mapping):
    # 先 expand 最内层占位（不含嵌套）
    while True:
        m = re.search(r'\$\{(\w+)\}', s)
        if not m: return s
        key = m.group(1)
        if key not in mapping: break
        s = s[:m.start()] + mapping[key] + s[m.end():]
    return s
```

迭代查找最内层 placeholder（regex `\w+` 不含 `${` 所以匹配的就是内层）。

## 易错点

> [!pitfall]
> ❌ 不做 cycle detection —— 递归爆栈；
> ❌ visited 用全局 set 不回溯 —— `a` 出现两条独立路径时第二次误判 cycle；
> ❌ Regex 错（如忘了 `\` 转义 `$` 和 `{}`）；
> ❌ 找不到 key 时不处理 —— 输出含原始 `${var}` 或应该 raise。

> [!key]
> 模板引擎核心：**递归 expand + cycle detection**。同模板用于：Makefile 变量、Bash $VAR 展开、TOML/YAML 引用、Lambda calc 替换。

> [!followup]
> "支持函数式占位 `${upper(name)}`？" → 解析 `name` 后再 apply function；"延迟 evaluation？" → 返回 lambda 而非 string；"性能（大模板）？" → 预 parse 成 AST 树，多次 render 时直接 walk；"streaming？" → 一边读一边输出，碰到完整 `${...}` 时展开。
