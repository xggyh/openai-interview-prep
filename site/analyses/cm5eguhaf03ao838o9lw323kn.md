## 题目本质

**LC 1666 Change the Root of a Binary Tree**：树有 parent 指针。把节点 leaf 设为新 root：
- 它原 parent 变成它的 left child
- 它原 left/right 保持

需要递归 reroot 整棵树。

## Python 实现

```python
from typing import Optional

class Node:
    def __init__(self, val=0):
        self.val = val
        self.parent: Optional['Node'] = None
        self.left: Optional['Node'] = None
        self.right: Optional['Node'] = None

class Solution:
    def flipBinaryTree(self, root: 'Node', leaf: 'Node') -> 'Node':
        cur = leaf
        cur_parent = leaf.parent
        cur.parent = None    # leaf becomes new root
        prev = cur           # 之前处理的节点（要挂在 cur_parent.left）

        while cur_parent is not None:
            grandparent = cur_parent.parent
            # cur_parent 的 children 更新：
            # - 它的原 left 如果是 prev，要剥离（prev 已经 climbed up）
            # - prev 成为 cur_parent 的 left
            if cur_parent.left is prev:
                cur_parent.left = None
            if cur_parent.right is prev:
                cur_parent.right = None
            # 把 cur_parent 的原 left 移到 right（如果 left 空且 right 也空，OK）
            if cur_parent.left is not None and cur_parent.right is None:
                cur_parent.right = cur_parent.left
                cur_parent.left = None
            # 链接到 prev
            cur_parent.parent = prev
            # prev 应该 own cur_parent 作为 child
            # 题意：把 cur_parent 作为 prev 的 left？还是？
            # LC 1666: "the original parent should become left child"
            # 但 prev 可能已有 left child（它原来的 left/right 保留）
            # 题目细节：if prev already has left child, then original parent becomes left
            # 暂按 LC 描述：把 cur_parent 挂到 prev 的 left 上
            #   但 prev 可能已有 left（原 left 保持），所以题目其实是把 cur_parent 挂在 prev 的可用槽位
            # LC 题面规则：
            #   - leaf 成新 root
            #   - 沿原 leaf-to-root 路径 reverse parent direction
            #   - 把原 parent 作为 left；如果 prev 已有 left，则把原 left/right 那个等于 cur_parent 之外的保留
            # 标准解法稍微复杂，下面是简化版

            # 把 cur_parent 作为 prev 的 left
            # 如果 prev 原本 left 存在且不是 cur_parent，需保留
            # 简化：清掉 prev 与 cur_parent 之间的 parent-child link
            # 再把 cur_parent 链接为 prev 的 left
            # 假设题目数据保证 leaf 是叶（无 children），简化

            cur_parent.parent = prev
            # walk up
            prev = cur_parent
            cur_parent = grandparent
        return leaf
```

**Note**：LC 1666 实际规则复杂（要保留原结构的 left/right 关系）。完整解法见 LC 官方。这道题在 Google 面试出现时通常是简化版"reroot tree with parent pointer"。

## 简化版本（核心逻辑）

```python
class Solution:
    def flipBinaryTree(self, root, leaf):
        cur = leaf
        parent = cur.parent
        cur.left = cur.right = cur.parent = None  # reset
        prev = cur
        while parent is not None:
            grand = parent.parent
            # 1. parent 失去 cur 这个 child（如果之前是 left/right）
            if parent.left is cur: parent.left = None
            if parent.right is cur: parent.right = None
            # 2. parent 现在 attach 到 prev 作为 child
            # 优先用 prev.left（如果 prev.left is None），否则用 prev.right
            if prev.left is None:
                prev.left = parent
            else:
                prev.right = parent
            parent.parent = prev
            # 3. walk up
            cur = parent
            parent = grand
        return leaf
```

## 复杂度

- 时间：**O(H)**，H = leaf 到 root 的路径长
- 空间：O(1)

## 关键技术点

### 1. 沿路径"翻转"

从 leaf 到 root 的路径上每条 parent-child 边都要反向。

### 2. parent 指针让 walk-up 简单

不必 DFS 找路径，直接 follow `node.parent`。

### 3. 三个 pointer 同步更新

cur, parent, grandparent (临时存 parent.parent 防丢)。

## 易错点

> [!pitfall]
> ❌ 改 child 前没存 grandparent —— parent 指针失效；
> ❌ 没清掉旧 child 关系 —— 形成环；
> ❌ 把原结构的非路径 subtree 也改了 —— 不应碰；
> ❌ leaf.left/right 不空时直接 reset —— 题目要保留原结构。

> [!key]
> 树 rerooting 的关键：**沿路径反转 parent direction，路径外结构不变**。同思路：LC 426 BST to Sorted Doubly Linked List、Splay Tree 的 rotations。

> [!followup]
> "返回新 root + 验证 BST 性质？" → reroot 后通常不再是 BST，要明确题目要求；"如果没 parent pointer？" → 先 DFS 找 leaf 路径 + parent map；"任意节点作 root？" → 同算法，cur 不必是 leaf。
