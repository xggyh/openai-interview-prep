## 题目本质

实现一个 **Spreadsheet with formulas**：cell 可以包含静态值或公式（含对其他 cell 的引用），公式所依赖的 cell 变化时**自动重算**。

OpenAI Senior 级 1 人报告。考点：**依赖图 + 拓扑排序 + 循环引用检测 + memoization**。

## 题目语义

```python
sheet = Spreadsheet()
sheet.set("A1", "10")
sheet.set("A2", "20")
sheet.set("B1", "=A1 + A2")            # 公式
sheet.set("B2", "=B1 * 2")             # 引用其他公式
print(sheet.get("B1"))                 # 30
print(sheet.get("B2"))                 # 60

sheet.set("A1", "100")                 # 修改源
print(sheet.get("B2"))                 # (100+20)*2 = 240   ← 自动重算

sheet.set("A1", "=B1")                 # 循环引用
# raises CycleError
```

## 解题思路

1. **公式解析**：`=A1 + A2 * 3` → AST 或 token list；找出依赖 cells
2. **依赖图**：cell → set of cells it depends on (reverse: cell → cells that depend on it)
3. **修改源 cell** → 遍历 dependents BFS/DFS 重算（用 memoization 避免重复）
4. **循环检测**：set 公式时模拟更新 graph，DFS 找环

## Python 实现

```python
import re
from collections import defaultdict
from typing import Optional

class CycleError(Exception):
    pass

# ----- 公式解析 -----
CELL_RE = re.compile(r'[A-Z]+\d+')

def extract_refs(expr: str) -> set[str]:
    """从公式表达式中找出所有 cell 引用"""
    return set(CELL_RE.findall(expr))

def eval_expr(expr: str, get_value) -> float:
    """求值：先 substitute 引用，再 eval。
    生产环境用专门的 expression parser，这里简化用 eval (危险) 并 sanitize"""
    def replace_cell(m):
        cell = m.group(0)
        v = get_value(cell)
        return str(v) if v is not None else '0'
    safe = CELL_RE.sub(replace_cell, expr)
    # 只允许数字 + 运算符 + 括号
    if not re.fullmatch(r'[\d\s\+\-\*\/\(\)\.]+', safe):
        raise ValueError(f"invalid expression: {expr}")
    return eval(safe)

# ----- Spreadsheet -----
class Spreadsheet:
    def __init__(self):
        # cell -> formula string (含 '=' 前缀) 或 plain value string
        self._raw: dict[str, str] = {}
        # cell -> cached numeric value（None 表示需重算）
        self._value: dict[str, Optional[float]] = {}
        # forward dep: cell -> cells it depends on
        self._deps: dict[str, set[str]] = defaultdict(set)
        # reverse dep: cell -> cells that depend on it
        self._dependents: dict[str, set[str]] = defaultdict(set)

    def set(self, cell: str, raw: str) -> None:
        # 解析新依赖
        new_deps = extract_refs(raw[1:]) if raw.startswith('=') else set()
        # 循环检测：从 cell 出发 follow new_deps，看能否回到 cell
        if self._would_create_cycle(cell, new_deps):
            raise CycleError(f"setting {cell} = {raw} creates a cycle")

        # 移除旧 dependency 在 reverse map 里
        for old_dep in self._deps[cell]:
            self._dependents[old_dep].discard(cell)
        # 安装新依赖
        self._deps[cell] = new_deps
        for d in new_deps:
            self._dependents[d].add(cell)

        self._raw[cell] = raw
        self._invalidate(cell)

    def get(self, cell: str) -> Optional[float]:
        return self._compute(cell)

    def _compute(self, cell: str) -> Optional[float]:
        if cell not in self._raw:
            return None
        if self._value.get(cell) is not None:
            return self._value[cell]
        raw = self._raw[cell]
        if raw.startswith('='):
            value = eval_expr(raw[1:], get_value=lambda c: self._compute(c))
        else:
            try:
                value = float(raw)
            except ValueError:
                value = 0  # 或当字符串
        self._value[cell] = value
        return value

    def _invalidate(self, cell: str) -> None:
        """BFS 清除该 cell 及其所有下游 cell 的缓存"""
        from collections import deque
        q = deque([cell])
        seen = set()
        while q:
            c = q.popleft()
            if c in seen:
                continue
            seen.add(c)
            self._value[c] = None
            for d in self._dependents[c]:
                q.append(d)

    def _would_create_cycle(self, cell: str, new_deps: set[str]) -> bool:
        """从 new_deps 各自出发 DFS，看能否到 cell"""
        for start in new_deps:
            stack = [start]
            seen = set()
            while stack:
                cur = stack.pop()
                if cur == cell:
                    return True
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(self._deps[cur])
        return False
```

## 复杂度

- `set(cell, ...)`: 循环检测 DFS O(N + E)；invalidate O(下游 size)
- `get(cell)`: 第一次 O(子树 size)；缓存命中 O(1)
- 总开销：每次值变 → 仅下游被重算 = O(affected cells)

## 关键设计点

### 1. 拓扑排序自动重算 vs Lazy 求值

两种策略：

**A. Lazy（推荐）**：set 时只 invalidate cache；get 时按需 recompute。
- 优点：set 快，多次连续 set 不浪费重算
- 缺点：第一次 get 慢

**B. Eager**：set 时 BFS/DFS 拓扑排序所有 affected cells 重算。
- 优点：get 永远 O(1)
- 缺点：set 慢；连续 set 浪费

通常 **A 更好**（用户改了输入立即看结果，但不是每次中间改都看）。

### 2. 循环检测时机

不是等求值时发现 stack overflow，而是 **set 时立即检测**：从新 dependency 出发 DFS，看能否回到 cell 自己。

### 3. Cache invalidation

修改 A1 → B1 (depends on A1) cache 失效 → C1 (depends on B1) 也失效 → 用 reverse-dep graph BFS。

### 4. 公式语法

简化版：只支持 `+ - * /` 和 cell 引用。生产应该有 lexer + parser，支持 `SUM(A1:A10)`, `IF(...)`, 字符串 concat 等。

```python
# 更完整的 parser 用 shunting-yard 算法
class FormulaLexer: ...
class FormulaParser:
    def parse(self, tokens) -> AST: ...
class FormulaEvaluator:
    def eval(self, ast, env) -> Value: ...
```

### 5. 范围引用 SUM(A1:A10)

把 range expand 成 list of cells；公式 dep 集合包含所有 cell。`SUM` / `AVG` 等函数 eval 时收集所有 cell value。

## 替代：直接拓扑排序

按依赖拓扑序求值，一次性把所有 cell 算完：

```python
def recompute_all(self):
    # Kahn's algorithm
    indeg = {c: len(self._deps[c]) for c in self._raw}
    q = deque([c for c, d in indeg.items() if d == 0])
    while q:
        c = q.popleft()
        self._value[c] = self._compute_no_cache(c)
        for dep in self._dependents[c]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                q.append(dep)
```

## 易错点

> [!pitfall]
> ❌ 公式 eval 用 `eval(raw)` 不 sanitize —— 任意 code execution；
> ❌ 循环检测放到求值时（递归栈溢出才发现）—— 应该 set 时检测；
> ❌ Cache invalidation 不传递下游 —— stale value；
> ❌ 修改 cell 时不更新 reverse-dep map —— 后续 invalidation 漏；
> ❌ 公式里有空格 (`=A1 + A2`) 解析失败 —— 用 regex 容忍空白。

> [!key]
> 三大要点：(1) **依赖图（forward + reverse）**；(2) **set 时检测 cycle，invalidate cache**；(3) **lazy compute + memoization** —— 避免重复算。这套也适用于 Excel、Google Sheets、Notion DB、reactive UI 框架（Vue/MobX）的依赖追踪。

> [!followup]
> "如何支持 functions (SUM, IF)？" → 加 lexer + parser，eval 时 dispatch 函数名；"如何 collaborative editing？" → CRDT on cell content + 同步公式图；"性能：1M cells？" → 不能每次扫整图，按 dep 局部更新 (这就是 Excel 的 dirty cell propagation)。
