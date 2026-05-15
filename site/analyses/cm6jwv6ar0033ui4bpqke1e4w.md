## 题目本质

**Convert Graph to Binary Tree with Alternating Colors**：给一个**连通无环无向图**，每节点最多 3 个邻居，节点有颜色（Black/White 或 Red/Black/White）。找一个节点作 root，使得"挂"起来后：
- 每节点最多 2 个子（成为 binary tree）
- 同层节点同色
- 相邻层颜色交替（如 R→B→W→R...）

## 解法

### Step 1: 找候选 root

每节点最多 3 邻居。如果作 root，其邻居都成它的 children → 但 binary tree 最多 2 children，所以 **root 必须是邻居数 ≤ 2** 的节点。

非 root 节点：除了 parent 之外还有最多 2 个 children，所以 **degree ≤ 3** (parent + 2 children) → 题目已保证。

但如果 root 是某节点 v，v 的所有邻居都是 children。所以 deg(v) ≤ 2 否则 binary tree 违反（root 没有 parent）。

### Step 2: 验证颜色约束

对每个候选 root v，BFS 从 v：
- 层数 d 的所有节点必须同色
- 颜色循环模式（R, B, W 重复 if 3-color；R, B 重复 if 2-color）

```python
from collections import defaultdict, deque

def find_root(n: int, edges: list[tuple[int,int]], colors: list[str],
              pattern: list[str]) -> int:
    """
    pattern: e.g. ['R','B','W'] 表示 layer 0 是 R, layer 1 是 B, layer 2 是 W, layer 3 是 R...
    Returns 一个 valid root index 或 -1
    """
    adj = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    def try_root(r: int) -> bool:
        if len(adj[r]) > 2:
            return False
        # BFS check
        depth = {r: 0}
        q = deque([r])
        while q:
            u = q.popleft()
            expected = pattern[depth[u] % len(pattern)]
            if colors[u] != expected:
                return False
            for v in adj[u]:
                if v in depth: continue
                # v 的 depth = u 的 depth + 1
                # v 的 children 数 ≤ 2 (parent u + 至多 2 children) → degree ≤ 3，已保证
                depth[v] = depth[u] + 1
                q.append(v)
        # 还要保证每节点除 parent 外最多 2 邻居（即 degree ≤ 3 with parent counted），题目已保证
        return True

    for r in range(n):
        if try_root(r):
            return r
    return -1
```

## 复杂度

- 每个候选 root 的 BFS: O(V + E)
- 总：**O(V × (V + E))**

V ≤ 1000 → 1M × edges，OK。

## 关键技术点

### 1. Root 候选限制

只有 degree ≤ 2 的节点能作 root（否则它的邻居超过 2 个 child）。

### 2. Binary tree 约束 (deg ≤ 3)

非 root 节点 degree ≤ 3 = parent + 2 children。题目已经保证（每节点 ≤ 3 邻居）。

### 3. 颜色模式由 pattern 给定

不同变种 pattern 可能是 ['R','W','B'] 或更长循环。代码用 `pattern[depth % len(pattern)]` 通用化。

### 4. BFS 自然分层

无向无环图（树）的 BFS 给出唯一分层。从某 root 出发的 BFS 中，每节点的 depth 唯一确定。

## 易错点

> [!pitfall]
> ❌ 没限制 root degree ≤ 2 —— 算到不可能的 root；
> ❌ Color pattern 假设固定长度（如总 3 色） —— 不一定，看题目；
> ❌ 把图作"有向"BFS —— 无向，要避免回头（depth set 记 visited）；
> ❌ 颜色 enumeration：题目给的 colors 列表是 char 列表，直接索引；
> ❌ 有环时 BFS 无限 —— 题目保证 acyclic。

> [!key]
> "找满足约束的 root" 类题：枚举候选 + 验证。约束分两类（结构性 like degree、属性性 like color）。同思路：LC 310 Minimum Height Trees、LC 834 Sum of Distances in Tree。

> [!followup]
> "返回所有 valid root？" → 收集而非 return first；"K 色循环？" → pattern 长 K；"动态加边？" → 需要 incremental algo（复杂）；"找 root 使深度最小？" → LC 310，topo-trim leaves。
