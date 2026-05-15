## 题目本质

**LC 366 Find Leaves of Binary Tree**：反复"剪掉叶子"，返回每一轮的叶子值列表。

例如：
```
    1
   / \
  2   3
 / \
4   5
```
- Round 1: [4, 5, 3] (剪掉这些叶子)
- Round 2: [2]
- Round 3: [1]

## 解法

DFS 计算每个节点的**高度**（叶子高度 = 0，向上累积）。同高度的节点在同一轮被剪掉。

## Python 实现

```python
from typing import Optional, List
from collections import defaultdict

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class Solution:
    def findLeaves(self, root: Optional[TreeNode]) -> List[List[int]]:
        layers = defaultdict(list)
        def height(node):
            if not node:
                return -1
            h = 1 + max(height(node.left), height(node.right))
            layers[h].append(node.val)
            return h
        height(root)
        return [layers[h] for h in sorted(layers)]
```

## 复杂度

- 时间：**O(N)**
- 空间：O(N) layers + 递归栈

## 关键点

### 1. 高度而非深度

**叶子 height = 0**（不是根 depth = 0）。叶子被剪后，原父变叶子 → height 1 → 第二轮。

```
height(node) = 1 + max(height(left), height(right))
height(None) = -1   ← 关键 base case
```

`height(None) = -1` 让叶子（左右都是 None）的 height = `1 + max(-1, -1) = 0`。

### 2. 同 height 在同一 list

defaultdict 按 height 分组，最后按 height 升序输出。

### 3. 不需要真删节点

只需要按 height 分组就行，等价于"反复剪叶子"。

## 易错点

> [!pitfall]
> ❌ 用 depth 而非 height —— 根 layer 在最浅，与题意反；
> ❌ height(None) 用 0 而非 -1 —— 叶子 height 算 1，公式偏差；
> ❌ 真去模拟"剪叶子 + 多轮 traversal" —— O(N²) 慢；
> ❌ 没 sort layers —— 输出顺序混乱。

> [!key]
> 树的高度等价于"被剪到的轮数"。这套思路也能解：拓扑排序的 layer 划分（Kahn BFS）、DAG 的最长路径分层、依赖图的批次调度。

> [!followup]
> "返回每个节点被剪的轮次？" → return dict node → layer；"找特定 layer 的节点？" → 同算法，只取该 layer；"如果不是二叉树（n-ary）？" → height 公式扩展为 max(children heights)；"流式 + 多次 query？" → 一次性算完所有 height 缓存。
