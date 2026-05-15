## 题目本质

**LC 79 Word Search**：m×n 网格能否拼出给定 word。相邻（4 方向）连接，**不能重用同一 cell**。返回 True/False。

## 解法

DFS 从每个 cell 起点 + 回溯。Visited 用 in-place mark。

## Python 实现

```python
from typing import List

class Solution:
    def exist(self, board: List[List[str]], word: str) -> bool:
        R, C = len(board), len(board[0])

        def dfs(r: int, c: int, i: int) -> bool:
            if i == len(word):
                return True
            if not (0 <= r < R and 0 <= c < C) or board[r][c] != word[i]:
                return False
            ch = board[r][c]
            board[r][c] = "#"
            found = (dfs(r-1, c, i+1) or dfs(r+1, c, i+1)
                  or dfs(r, c-1, i+1) or dfs(r, c+1, i+1))
            board[r][c] = ch
            return found

        for r in range(R):
            for c in range(C):
                if board[r][c] == word[0] and dfs(r, c, 0):
                    return True
        return False
```

## 复杂度

- 时间：**O(R × C × 4^L)**，L = word length
- 空间：O(L) 递归栈

## 关键点

### 1. In-place visited

`board[r][c] = "#"` 节省空间；回溯时恢复 `board[r][c] = ch`。

### 2. 早期剪枝

`board[r][c] != word[i]` 立即 return False，不必继续递归。

### 3. 起点优化

只在 `board[r][c] == word[0]` 时启动 DFS。

## 易错点

> [!pitfall]
> ❌ 回溯不恢复 board —— 下一起点搜索失败；
> ❌ visited 用 set 但忘了 remove —— 跨起点污染；
> ❌ DFS 顺序检查 (out of bounds + char match) —— 用 short-circuit `or` 自然处理；
> ❌ word 为空时返回 False —— 应返回 True（空 word trivially matches）。

> [!key]
> Backtracking + grid search 的经典入门题。Word Search II (LC 212) 是这题的多模式扩展（用 Trie）。

> [!followup]
> "8 方向？" → DIRS 加对角线；"允许重用 cell？" → 不再 mark visited，但要限制 word length 防死循环；"输出路径？" → DFS 累积坐标 list；"多 word 同时找？" → 用 Trie，参考 LC 212。
