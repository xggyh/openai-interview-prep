## 题目本质

**LC 1381 Design a Stack With Increment Operation**：实现栈：
- `push(x)`：超过 maxSize 不 push
- `pop()`：弹出栈顶；空时返回 -1
- `increment(k, val)`：栈底 k 个元素都 +val

直接增加每元素是 O(K) per call。如何 O(1) 摊销？

## 解法 — Lazy Propagation

维护辅助数组 `inc[i]`：表示"位置 i 及以下的所有元素都要再加 inc[i]"。`increment(k, val)` 只更新 `inc[min(k, size) - 1] += val`，O(1)。

`pop` 时：弹出元素值 = stack[top] + inc[top]；然后把 `inc[top]` 累加到 `inc[top-1]`（lazy 向下传递）；最后清 inc[top]。

## Python 实现

```python
class CustomStack:
    def __init__(self, maxSize: int):
        self.max = maxSize
        self.stack: list[int] = []
        self.inc: list[int] = []   # 同长度，inc[i] 影响 stack[0..i]

    def push(self, x: int) -> None:
        if len(self.stack) < self.max:
            self.stack.append(x)
            self.inc.append(0)

    def pop(self) -> int:
        if not self.stack: return -1
        i = len(self.stack) - 1
        result = self.stack.pop() + self.inc[i]
        delta = self.inc.pop()
        if i > 0:
            self.inc[i - 1] += delta
        return result

    def increment(self, k: int, val: int) -> None:
        if not self.stack: return
        idx = min(k, len(self.stack)) - 1
        self.inc[idx] += val
```

## 复杂度

| 操作 | 时间 |
|---|---|
| push | O(1) |
| pop | O(1) |
| increment | O(1) |

## 关键技术点

### 1. Lazy Propagation 思想

不立即把 +val 分发给所有 k 个元素，而是只标记"以下都 +val"。读取时累计。

### 2. Pop 时下传

弹出栈顶后，原来作用于 [0..top] 的 inc 现在只该作用于 [0..top-1]。把 `inc[top]` 加到 `inc[top-1]`，然后 pop。

### 3. min(k, size)

k 可能 > 当前 size，截断到 size。

### 4. 边界：栈空

`pop` 返回 -1；`increment` no-op。

## 暴力做法（O(K) increment）

```python
class CustomStack:
    def increment(self, k, val):
        for i in range(min(k, len(self.stack))):
            self.stack[i] += val
```

清晰但 increment 是 O(K)。LC 数据足够，但 lazy 是面试加分。

## 易错点

> [!pitfall]
> ❌ Increment 直接加每个元素 —— 单次 O(K)，多次累加 TLE 数据；
> ❌ pop 时忘了把 inc 传给下一个；
> ❌ inc 数组长度和 stack 不同步 —— off-by-one；
> ❌ increment 当 k > size 时不截断 —— index 越界。

> [!key]
> Lazy propagation 是 segment tree、BIT、splay tree 的精髓。也用于：区间染色（painting）、区间 add+查询 sum、分布式 cache invalidation。

> [!followup]
> "Increment 顶 k 个而非底？" → 维护 inc[i] 反义；"Increment 中间一段 [l, r]？" → 差分数组；"返回当前栈底/顶？" → peek 类似 pop 但不弹。
