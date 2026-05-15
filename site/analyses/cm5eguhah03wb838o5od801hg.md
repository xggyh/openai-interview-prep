## 题目本质

**LC 2445 Number of Nodes With Value One**：完全二叉树（节点编号 1..n，1 是根），每个节点初始值 0。给一组 queries：对每个 query q，把以节点 q 为根的子树**翻转**（0↔1）。最后返回值为 1 的节点数。

## 解法

**位翻转 + lazy propagation**：

- 每个节点维护"自己的 flip 计数"
- 累计 flip 数（自身 + 所有祖先的 flip）为奇数则值是 1

实现：用 `flips[q] ^= 1`（每次 query 对应节点翻一下）。最后 DFS 累加 from root 到每节点的 flip XOR：

```python
class Solution:
    def numberOfNodes(self, n: int, queries: list[int]) -> int:
        from collections import Counter
        flips_at = Counter()
        for q in queries:
            flips_at[q] ^= 1   # 同一节点 query 偶数次抵消
        # 也可以用 set: 出现奇数次的节点
        toggle = set()
        for q, c in flips_at.items():
            if c == 1: toggle.add(q)

        # DFS: cumulative xor from root
        count = 0
        # 用 BFS/DFS 模拟完全二叉树（节点 i 的左 = 2i，右 = 2i+1）
        stack = [(1, 0)]   # (node, cum_xor)
        while stack:
            node, cum = stack.pop()
            if node > n: continue
            cum ^= 1 if node in toggle else 0
            if cum == 1:
                count += 1
            stack.append((2*node, cum))
            stack.append((2*node + 1, cum))
        return count
```

## 复杂度

- 时间：**O(N + Q)**，N 节点 + Q queries
- 空间：O(N) 递归栈 + toggle set

## 关键技术点

### 1. 翻转的奇偶性

同一节点 query 两次 == 不翻。所以最后只要计奇偶（XOR）。

### 2. 子树累积

某节点 v 的最终值 = XOR(所有祖先节点（含 v 自己）被 toggle 的奇偶数)。即从 root 到 v 的路径上所有 toggle 点的 XOR。

### 3. 完全二叉树用 1-indexed

节点 i 左子 = 2i，右子 = 2i+1，无 pointer 直接计算。

### 4. 同一 query 多次

用 Counter 或 set 处理：偶数次 → cancel；奇数次 → 留 toggle。

## 易错点

> [!pitfall]
> ❌ 直接 query 后立即递归 toggle 子树 —— 每 query O(子树 size)，总 O(NQ) 慢；
> ❌ 用 XOR 错误（把节点本身 toggle 多次，但子树外的不动）—— 必须先 dedup 奇偶；
> ❌ 递归深度 N → 大 N 用迭代 stack；
> ❌ 完全树节点编号忘了 1-indexed。

> [!key]
> 树上 lazy propagation + XOR：每节点最终值 = root-to-self path 上 XOR。同思想：LC 1457（路径 XOR）、Tree DP "继承父值"。

> [!followup]
> "如果不是完全树？" → 显式建树 + parent pointers + DFS；"返回每节点最终值列表？" → DFS 累积时记 result[node]=cum；"在线 query？" → 用 Euler tour + BIT/segment tree 维护子树 XOR。
