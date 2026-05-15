## 题目本质

**LC 230 Kth Smallest Element in a BST**：BST 中第 k 小元素。

## 解法

**中序遍历是升序**。遍历到第 k 个时返回。

## Python 实现（迭代中序）

```python
from typing import Optional

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class Solution:
    def kthSmallest(self, root: Optional[TreeNode], k: int) -> int:
        stack = []
        cur = root
        while cur or stack:
            while cur:
                stack.append(cur)
                cur = cur.left
            cur = stack.pop()
            k -= 1
            if k == 0:
                return cur.val
            cur = cur.right
```

## 复杂度

- 时间：**O(H + k)**，H = 树高（一开始要走到最左 = H 步）
- 空间：O(H) 栈

最坏（skewed tree）H = O(N)。Balanced 时 O(log N + k)。

## 递归版（更短但易写错）

```python
class Solution:
    def kthSmallest(self, root, k):
        self.k = k
        self.res = None
        def inorder(node):
            if not node or self.res is not None: return
            inorder(node.left)
            self.k -= 1
            if self.k == 0:
                self.res = node.val
                return
            inorder(node.right)
        inorder(root)
        return self.res
```

## Follow-up：BST 频繁修改 + 频繁 query kth

每次 O(H + k) 不够。在每个 node 多维护 `size = 左子树 + 右子树 + 1`：

```python
def kthSmallest(root, k):
    cur = root
    while cur:
        left_size = cur.left.size if cur.left else 0
        if k <= left_size:
            cur = cur.left
        elif k == left_size + 1:
            return cur.val
        else:
            k -= left_size + 1
            cur = cur.right
```

每次 O(H)。修改时同步 size。这就是 **augmented BST / order-statistic tree**。

## 易错点

> [!pitfall]
> ❌ 中序变前序/后序 —— 不再升序；
> ❌ k 从 1 还是 0 开始：题目通常 1-indexed；
> ❌ k 减到 0 后没 return —— 继续遍历完整树；
> ❌ 递归版 self.res 不用早停 —— TLE 大树。

> [!key]
> BST + 中序 = 升序遍历。同思路：找 BST 第 k 大（反向中序，先 right 后 left）、BST 验证（中序检查严格单调）、BST 中位数。

> [!followup]
> "BST 经常变动 (insert/delete)？" → augmented BST 维护 size；"找 [k1, k2] 范围所有元素？" → 修改中序记录 count 之间的；"BST 自平衡？" → AVL / RBT，size 维护逻辑一样；"非 BST 普通树？" → 不能用中序，要 heap-of-k 或 quickselect。
