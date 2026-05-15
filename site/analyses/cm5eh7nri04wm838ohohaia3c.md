## 题目本质

**LC 346 Moving Average from Data Stream**：实现固定窗口大小的移动平均。`next(val)` 返回当前窗口的均值。

## 解法

队列 + 累计和（避免每次重算）。

## Python 实现

```python
from collections import deque

class MovingAverage:
    def __init__(self, size: int):
        self.size = size
        self.q: deque[int] = deque()
        self.total = 0

    def next(self, val: int) -> float:
        self.q.append(val)
        self.total += val
        if len(self.q) > self.size:
            self.total -= self.q.popleft()
        return self.total / len(self.q)
```

## 复杂度

- `next`: **O(1)** 摊销
- 空间: O(size)

## 关键点

### 1. 累计和增量更新

不要每次 `sum(self.q) / len(self.q)` —— 那是 O(size) per call。增量维护 total，O(1)。

### 2. 浮点除 vs 整除

Python 3 `/` 是浮点除。如果用 `//` 会截断。题目要 float 返回。

### 3. 窗口未满时

题目语义：窗口未满直接均值（用当前所有元素）。代码自然处理。

## 易错点

> [!pitfall]
> ❌ 用 list 而非 deque —— `pop(0)` O(N)；
> ❌ 不维护 running sum —— next O(size)；
> ❌ size = 0 边界：题目通常保证 size ≥ 1；
> ❌ 返回 int 除以 int 时用 `/` 不是 `//`。

> [!key]
> 滑动窗口固定大小 + 增量统计 = O(1) per op。同模板用于：滚动 max/min（用 monotonic deque）、滚动 median（用 two heaps）、滚动 variance。

> [!followup]
> "动态调整 window size？" → 重置或 shrink；"窗口内 max/min？" → 单调 deque 维护；"加权移动平均？" → 维护加权和 + 加权 count（注意 popleft 的权重）；"如果数据流可重放？" → 不需要 queue，索引访问。
