## 题目本质

**LC 2407 Longest Increasing Subsequence II**：求严格递增子序列长度，且相邻元素差 ≤ k。

普通 LIS O(N log N) 用二分 / 单调栈。带 k 约束需要支持 **range max query**。

## 解法

`dp[v]` = 以值 v 结尾的 LIS 长度。转移：`dp[v] = 1 + max(dp[u] for u in (v-k, v-1))`。需要**区间最大值查询 + 单点更新** → **Segment Tree**。

## Python 实现

```python
from typing import List

class SegTree:
    """支持区间 max query + 单点 update."""
    def __init__(self, n: int):
        self.n = n
        self.tree = [0] * (4 * n)

    def update(self, idx: int, val: int, node=1, lo=0, hi=None):
        if hi is None: hi = self.n - 1
        if lo == hi:
            self.tree[node] = max(self.tree[node], val)
            return
        mid = (lo + hi) // 2
        if idx <= mid:
            self.update(idx, val, 2*node, lo, mid)
        else:
            self.update(idx, val, 2*node+1, mid+1, hi)
        self.tree[node] = max(self.tree[2*node], self.tree[2*node+1])

    def query(self, l: int, r: int, node=1, lo=0, hi=None) -> int:
        if hi is None: hi = self.n - 1
        if r < lo or hi < l: return 0
        if l <= lo and hi <= r: return self.tree[node]
        mid = (lo + hi) // 2
        return max(self.query(l, r, 2*node, lo, mid),
                   self.query(l, r, 2*node+1, mid+1, hi))


class Solution:
    def lengthOfLIS(self, nums: List[int], k: int) -> int:
        max_val = max(nums)
        st = SegTree(max_val + 1)
        best = 0
        for x in nums:
            # 找 dp[x-k..x-1] 的 max
            l = max(0, x - k)
            r = x - 1
            prev = st.query(l, r) if r >= 0 else 0
            cur = prev + 1
            st.update(x, cur)
            best = max(best, cur)
        return best
```

## 复杂度

- 时间：**O(N log M)**，M = max value
- 空间：O(M) seg tree

## 关键技术点

### 1. 为什么需要 Seg Tree

普通 LIS 二分法不能处理 "差 ≤ k" 约束。BIT (Fenwick) 也能做但需 reverse-indexing 处理 max。Segment tree 最直观。

### 2. 值域作为索引

`dp[v]` 索引是值 v 不是位置 i。这样 query [x-k, x-1] 自然是值域范围。如果值域大要离散化。

### 3. 严格递增

转移用 `[x-k, x-1]` 不包含 x，保证严格小于。

### 4. 离散化（当 max_val 很大时）

```python
# Discretize values
vals = sorted(set(nums))
idx = {v: i for i, v in enumerate(vals)}
# 用 idx[v] 作 seg tree 索引
# 注意 "v-k" 要找映射后的范围
```

这题 max_val ≤ 1e5 不必离散化。

## 易错点

> [!pitfall]
> ❌ 普通 O(N log N) LIS 二分法 —— 不能加 k 约束；
> ❌ Seg tree 不支持 range max —— 标准 seg tree 改 sum 为 max；
> ❌ Query 范围 r < 0 时直接 query —— seg tree 边界处理；
> ❌ 误以为 k 是 index 距离 —— 题目是 value 差；
> ❌ 没初始化 prev = 0 —— 当 [x-k, x-1] 空时返回 0，cur = 1 表示自身。

> [!key]
> "约束的 LIS" 类问题：dp 索引改值域 + segment tree 维护值域 max。这是高级 DP 的标配。同模板：LC 1187 Make Array Strictly Increasing（dp + 二分）、LC 873 LIS pair。

> [!followup]
> "差 ∈ [a, b]？" → query [x-b, x-a]；"非严格递增？" → query [x-k, x]；"返回 LIS 自身？" → seg tree 节点存 (max_len, parent_idx)，回溯重建；"二维约束？" → CDQ 分治 / 二维 seg tree。
