## 题目本质

**Count Islands in Binary Trees**：二叉树每个节点值是 0 或 1。求 "islands"（值为 1 的连通分量）数量。还有变种：返回每个 island 的 size、unique island shapes 等。

类似 grid 数岛屿，但拓扑是树。Google 1st-onsite L4 真题。

## 解题思路

DFS 树。维护"当前是否在 island 内"。每当从 0 跳到 1（即父是 0 或 None，自己是 1），开启新 island，count++。然后继续 DFS，把同 island 内的 1 都遍历完。

## Python 实现

```python
from typing import Optional, List

class TreeNode:
    def __init__(self, val: int = 0, left: 'TreeNode' = None, right: 'TreeNode' = None):
        self.val = val; self.left = left; self.right = right

class Solution:
    def countIslands(self, root: Optional[TreeNode]) -> int:
        """A 'island' is a maximal connected subgraph of nodes with value 1."""
        if not root: return 0
        count = 0
        # DFS with parent's value as context
        def dfs(node: Optional[TreeNode], parent_val: int):
            nonlocal count
            if not node: return
            if node.val == 1 and parent_val == 0:
                count += 1   # new island starts
            dfs(node.left, node.val)
            dfs(node.right, node.val)
        dfs(root, 0)  # 视为根的父值是 0
        return count

    def islandSizes(self, root: Optional[TreeNode]) -> List[int]:
        """Return sizes of all islands."""
        sizes = []
        def dfs(node: Optional[TreeNode]) -> int:
            """Returns size of island containing node, or 0 if node.val == 0."""
            if not node or node.val == 0:
                # 仍递归子树（可能开新岛）
                if node:
                    dfs(node.left); dfs(node.right)
                return 0
            size = 1 + dfs_continue(node.left) + dfs_continue(node.right)
            return size
        def dfs_continue(node):
            """Like dfs but doesn't add to sizes; continues current island."""
            if not node or node.val == 0:
                if node: dfs(node.left); dfs(node.right)
                return 0
            return 1 + dfs_continue(node.left) + dfs_continue(node.right)
        # 顶层 wrapper：遍历所有节点，从每个"island root"开始测 size
        def find_island_roots(node, parent_val):
            if not node: return
            if node.val == 1 and parent_val == 0:
                sizes.append(dfs_continue(node))
            else:
                find_island_roots(node.left, node.val if node else 0)
                find_island_roots(node.right, node.val if node else 0)
        find_island_roots(root, 0)
        return sizes
```

## 复杂度

- 时间：**O(N)**，每个节点访问 O(1) 次
- 空间：O(H) 递归栈（H = 树高）

## 关键技术点

### 1. "Island 起点" 判别

节点 v 是某 island 的起点 ⟺ `v.val == 1 且 parent.val == 0`（或 v 是根且 root.val == 1）。代码里把 "root 的 parent value" 视为 0 处理。

### 2. 不是 grid 题：树没有"邻居 = up/down/left/right"

树的连通性只看 parent-child。即父节点是 1，且自己是 1，就属同一 island。

### 3. 三个常见问题（按提到的真实变种）

| 变种 | 解法 |
|---|---|
| count islands | DFS + parent_val |
| size of each island | DFS 每个 island 起点开始累加 |
| unique island shapes | 把每个 island 序列化为 string，用 set 去重 |
| max island size | 同 size 计算 + 取 max |

## 边界 case

```python
#       1
#      / \
#     0   1
#    / \   \
#   1   1   0
#            \
#             1
# 期望 3 islands: {root}, {root.left.left}, {root.left.right}, {root.right.right.right}
# 等等：1-0-1-1（root + left.left）—— root 是 1，left 是 0，所以 root 自己一个 island；
# left.left 是 1，parent=0，新岛；
# left.right 是 1，parent=0，新岛；
# right 是 1，parent=1（root），同 root 一岛？是的。但 root.right.right 是 0...
# 重新看：root(1)-right(1) 是同岛。
```

实际 island 是按 "连续 1 的极大子树"：从根 DFS，碰到 1-1 还在同岛；碰到 0 就断；下一次 0-1 再起新岛。

## 易错点

> [!pitfall]
> ❌ 把题目当 grid 处理 —— 树没有左右邻居概念；
> ❌ "island root" 判别忘了 root 节点 special case —— 视为 parent=0 处理；
> ❌ 数 size 时只递归左不递归右 —— size 算偏；
> ❌ Unique shapes 用 list 而非序列化 string —— hash 不上。

> [!key]
> 树上的连通分量计数 = DFS + 跟踪父节点值变化。这套思路也适用于：染色变化点检测、tree-edit distance、二叉树切割问题。

> [!followup]
> "Unique island shapes？" → 把每个 island 用 canonical 序列化（如 preorder traversal with '#' for null + value）然后塞 set；"如果每个节点有任意 children（n-ary tree）？" → DFS 改为遍历 children list；"如果允许"island 内可以包含 0"（即给定阈值）？" → DFS 用 score 累加替代严格 1。
