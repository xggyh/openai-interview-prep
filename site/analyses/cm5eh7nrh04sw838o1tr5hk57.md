## 题目本质

**LC 212 Word Search II**：m×n 网格里搜索给定字典中的所有单词。单词由 grid 相邻字符（4 方向）组成，**不能重用同一 cell**。返回找到的单词列表。

经典**Trie + DFS + 回溯**。Hard。

## 朴素 vs Trie 优化

**朴素**：对每个 word 做一次 LC 79 (Word Search)。复杂度 O(W × R × C × 4^L)，W = 单词数。慢。

**Trie**：把所有 word 建 Trie，DFS grid 时沿 Trie 走（自然 prune），找到 leaf 就 record。复杂度 O(R × C × 4^L_max)，W 因子消失。

## Python 实现

```python
from typing import List

class TrieNode:
    def __init__(self):
        self.children: dict[str, 'TrieNode'] = {}
        self.word: str | None = None   # 在 leaf 存完整 word（方便 record）

class Solution:
    def findWords(self, board: List[List[str]], words: List[str]) -> List[str]:
        # 1. Build Trie
        root = TrieNode()
        for w in words:
            node = root
            for c in w:
                if c not in node.children:
                    node.children[c] = TrieNode()
                node = node.children[c]
            node.word = w

        R, C = len(board), len(board[0])
        result = []

        def dfs(r: int, c: int, node: TrieNode):
            ch = board[r][c]
            if ch not in node.children:
                return
            nxt = node.children[ch]
            if nxt.word is not None:
                result.append(nxt.word)
                nxt.word = None    # 去重 + 防重复 push
            board[r][c] = "#"   # mark visited
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < R and 0 <= nc < C and board[nr][nc] != "#":
                    dfs(nr, nc, nxt)
            board[r][c] = ch    # restore

            # Pruning: 如果 nxt 没 children 了，从父 node 移除（减少未来搜索）
            if not nxt.children:
                node.children.pop(ch, None)

        for r in range(R):
            for c in range(C):
                dfs(r, c, root)

        return result
```

## 复杂度

- 建 Trie：O(total chars in words)
- DFS：每个 cell 起点 → 最深 4^L_max（实际远小，因为 Trie 早 prune）
- 总：**O(R × C × 4^L_max)**，远小于"每词独立 DFS"的 O(W × R × C × 4^L)

## 关键技术点

### 1. Trie 把所有 word 共享 prefix

如果 `["cat", "car", "card"]`，共享 prefix "ca"。Trie 上从 root 走 c→a 时，遇到下一字符是 't' 还是 'r' 各自分叉，**不必为每个 word 重新搜**。

### 2. DFS 沿 Trie 走

不是先有 word，再 grid 搜。而是 grid DFS 一步，Trie 一步。Trie 上有该子节点就继续，没有就终止该分支。**搜索剪枝**自动发生。

### 3. 标记 visited

把 `board[r][c]` 临时改为 `"#"`，DFS 回溯时还原。这样不用额外 visited set。

### 4. Trie 剪枝（性能加分）

DFS 完一条分支后，如果当前 Trie node 已无 children（所有 word 都找到了），把它从父 node 移除。下次 DFS 走到这里就立即返回。

LC 212 测试集开启这个剪枝差 5-10x 性能。

### 5. word=None 去重

找到 word 后把 leaf 的 `.word` 清零。这样不会把同一个 word 多次 append（grid 上可能有多条路径拼出同一 word）。

## 边界 case

```python
board = [
    ["o","a","a","n"],
    ["e","t","a","e"],
    ["i","h","k","r"],
    ["i","f","l","v"]
]
words = ["oath","pea","eat","rain"]
# 期望: ["eat", "oath"]
```

## 易错点

> [!pitfall]
> ❌ 对每个 word 独立 DFS —— TLE；
> ❌ Visited 用 set 而非 in-place `#` —— 工作但常数大；
> ❌ 找到 word 不清零 → 重复加入 result；
> ❌ Trie 不 prune —— 仍能 AC 但慢；
> ❌ 回溯时忘恢复 `board[r][c] = ch` —— 网格被破坏；
> ❌ DFS 不检查 `ch not in node.children` 立即返回 —— 多走无用路径。

> [!key]
> 多模匹配 + grid 搜索 = Trie + DFS。"Trie 上走" 把搜索复杂度从 `O(W × 路径)` 降到 `O(路径)`。这套思路也用于：拼字游戏、DNA 模式匹配、敏感词过滤。

> [!followup]
> "如果 word 长度可超过 R×C？" → Trie 仍工作，但 DFS 永远找不到（visited 用完）；"如果允许重用 cell？" → 不要 mark visited，但要 cycle detection 或限制深度；"如果 board 巨大？" → 把高频字符做 spatial index 加速起点选择；"输出每 word 在 grid 上的路径？" → DFS 记录路径，找到时复制。
