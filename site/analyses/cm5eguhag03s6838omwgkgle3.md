## 题目本质

**LC 2296 Design a Text Editor**：实现 cursor-based 文本编辑器：
- `addText(s)`：在光标位置插入 s，光标右移
- `deleteText(k)`：删除光标左侧 k 个字符，返回实际删除数
- `cursorLeft(k)` / `cursorRight(k)`：光标移动；返回光标左侧最多 10 个字符

## 解法

**双栈 / 双向 deque** 模拟光标：
- `left`：光标左侧字符栈（top = 光标紧邻左）
- `right`：光标右侧字符栈（top = 光标紧邻右）

光标移动 = 字符从一栈移到另一栈。

## Python 实现

```python
class TextEditor:
    def __init__(self):
        self.left: list[str] = []
        self.right: list[str] = []

    def addText(self, text: str) -> None:
        for ch in text:
            self.left.append(ch)

    def deleteText(self, k: int) -> int:
        to_del = min(k, len(self.left))
        for _ in range(to_del):
            self.left.pop()
        return to_del

    def cursorLeft(self, k: int) -> str:
        for _ in range(min(k, len(self.left))):
            self.right.append(self.left.pop())
        return self._last10()

    def cursorRight(self, k: int) -> str:
        for _ in range(min(k, len(self.right))):
            self.left.append(self.right.pop())
        return self._last10()

    def _last10(self) -> str:
        if len(self.left) >= 10:
            return ''.join(self.left[-10:])
        return ''.join(self.left)
```

## 复杂度

| 操作 | 时间 |
|---|---|
| addText | O(L)，L = text 长度 |
| deleteText | O(K) 摊销 |
| cursorLeft/Right | O(K) 移动 |
| _last10 | O(1) 切片（最多 10 字符） |

## 关键技术点

### 1. 双栈表示光标位置

`left` 末尾 = 光标紧左字符；`right` 末尾 = 光标紧右字符。移动光标 = pop 一栈 push 另一栈。

### 2. 删除从 left pop

`deleteText` 只影响光标左侧字符（删的是光标左边）。

### 3. 返回光标左 10 字符

```python
return ''.join(self.left[-10:])
```

切片自动处理 < 10 的情况。

### 4. 为什么不用单 string + index

可以但 string 插入 / 删除是 O(N)。双栈让每个 char 最多在两栈间转移 2 次（push + pop），摊销 O(1)。

## 替代：Doubly Linked List

更"通用"但实现复杂。双栈对这题足够且更快。

## 易错点

> [!pitfall]
> ❌ 单栈 / 单 list 模拟 —— 光标移动 O(N)；
> ❌ deleteText 删 right 栈 —— 题目是删光标左；
> ❌ cursorLeft 直接修改 cursor 数字而不动数据 —— 光标位置和数据不一致；
> ❌ _last10 没处理 < 10 字符。

> [!key]
> 双栈 / 双 deque 表示游标位置是文本编辑器的标准技巧。同思想：LC 1472 Browser History、LC 705 Design HashSet、LC 1670 Design Front Middle Back Queue。

> [!followup]
> "支持 undo？" → 加 operation stack，每 op 记反操作；"支持 selection？" → 维护 anchor index；"多用户协作？" → CRDT（参考 CoderPad 题）；"大文档分页加载？" → linked list of chunks 而非全字符栈。
