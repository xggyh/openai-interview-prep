## 题目本质

**LC 222 Count Complete Tree Nodes**：完全二叉树（complete tree）的节点数。**不能 O(N) 暴力遍历**，需要利用完全树性质做 **O(log² N)**。

## 解法

完全二叉树定义：除最后一层，所有层满；最后一层从左填。

利用性质：**左/右子树至少有一个是 perfect tree**（深度 h 的完全树的左或右子树是 perfect）。

- 算左子树最左路径深度 dl
- 算右子树最左路径深度 dr
- 如果 dl == dr：左子树 perfect (size = 2^dl - 1)，递归 right
- 否则：右子树 perfect (size = 2^dr - 1)，递归 left

## Python 实现

```python
from typing import Optional

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class Solution:
    def countNodes(self, root: Optional[TreeNode]) -> int:
        if not root:
            return 0
        # 左走到底
        lh = self._left_height(root)
        rh = self._right_height(root)
        if lh == rh:
            return (1 << lh) - 1   # perfect tree
        return 1 + self.countNodes(root.left) + self.countNodes(root.right)

    def _left_height(self, node):
        h = 0
        while node:
            h += 1
            node = node.left
        return h

    def _right_height(self, node):
        h = 0
        while node:
            h += 1
            node = node.right
        return h
```

## 复杂度

- 每层递归：算两次高度 O(log N)
- 递归深度：O(log N)
- 总：**O(log² N)**

## 关键技术点

### 1. Perfect tree 判定

`左走到底深度 == 右走到底深度` ⟺ 是 perfect tree。size = `2^h - 1`。

### 2. 否则递归两边

非 perfect 时，**左右子树至少有一个仍是完全树**。递归同算法。

### 3. 计数公式

`(1 << h) - 1`：h 层 perfect tree 节点数 = 2^h - 1。

## 边界 case

```python
# 空树 → 0
# 单节点 → 1
# 满 3 层：7 个节点
# 不满 3 层：算法分摊 O(log² N)
```

## 易错点

> [!pitfall]
> ❌ 朴素 O(N) DFS 数节点 —— 不利用完全树性质；
> ❌ Perfect tree 检测只看左高度 —— 必须左 == 右；
> ❌ `1 << h - 1` 不加括号 —— 优先级问题（实际 `1 << (h-1)` 是错的，应 `(1 << h) - 1`）；
> ❌ 递归到 None 没 return 0。

## 进阶：迭代版（O(log² N) 不变）

```python
def countNodes(root):
    if not root: return 0
    h = 0
    node = root
    while node.left:
        h += 1; node = node.left
    # 二分最后一层有多少节点 ∈ [0, 2^h]
    lo, hi = 0, (1 << h) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if exists(root, mid, h):
            lo = mid + 1
        else:
            hi = mid - 1
    # 总 = perfect 上层 + 最后一层节点数
    return ((1 << h) - 1) + lo

def exists(root, idx, h):
    """检查最后一层 idx 处是否有节点（按完全树 binary 索引）"""
    lo, hi = 0, (1 << h) - 1
    for _ in range(h):
        mid = (lo + hi) // 2
        if idx <= mid:
            root = root.left; hi = mid
        else:
            root = root.right; lo = mid + 1
    return root is not None
```

二分最后一层节点数。

> [!key]
> "完全二叉树" 的关键就在它"分摊性质"：每次递归都有一边是 perfect tree，能 O(1) 数清。Recursion T(N) = T(N/2) + O(log N) = O(log² N)。

> [!followup]
> "二叉搜索树（BST）的 size？" → 与本题无关，BST 没完全树保证，必须 O(N)；"用 augmented tree 维护 size 字段？" → 每次 insert/delete 同步 size，count 是 O(1)；"完全树的高度计算？" → 同 left_height；"完全树的 array 表示？" → A[1..n]，左子=2i，右子=2i+1。
