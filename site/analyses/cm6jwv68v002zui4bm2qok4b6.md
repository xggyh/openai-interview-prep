## 题目本质

**Find Root Node in Colored Tree with Pattern Constraints**：与 `Convert Graph to Binary Tree with Alternating Colors` 同类，更强约束 —— 颜色按 **6 种可能 3-color permutation** 中之一循环（如 R→W→B→R→W→B 或 R→B→W 或...）。返回任一 valid root，没有返回 -1。

## 解法

同前题，但试**所有 6 种 pattern 排列**：

```python
from itertools import permutations
from collections import defaultdict, deque

def find_root_multi_pattern(n, edges, colors):
    adj = defaultdict(set)
    for u, v in edges:
        adj[u].add(v); adj[v].add(u)

    def check(r: int, pattern: tuple) -> bool:
        if len(adj[r]) > 2: return False
        depth = {r: 0}
        q = deque([r])
        while q:
            u = q.popleft()
            if colors[u] != pattern[depth[u] % 3]:
                return False
            for v in adj[u]:
                if v in depth: continue
                depth[v] = depth[u] + 1
                q.append(v)
        return True

    color_set = sorted(set(colors))  # 假设有 3 个颜色
    if len(color_set) > 3: return -1   # 超过 3 色不在此变种范围
    for pattern in permutations(color_set):   # 6 种排列
        for r in range(n):
            if check(r, pattern):
                return r
    return -1
```

## 复杂度

- 时间：**O(P × V × (V + E))**，P = 6 (color permutations)。
- 空间：O(V + E)

## 关键技术点

### 1. 枚举所有 pattern

3 色有 3! = 6 个循环排列。如果题目允许 2 色变种或 4 色，pattern 数变。

### 2. Adjacent layer 颜色不同

pattern 用 list of distinct colors → adjacent layer 自然不同色。如果用 `[R, R, B]`（同色相邻）则违反"adjacent must differ"约束 → 排除。

### 3. 6 种 of 3-color cycle

- (R, B, W), (R, W, B), (B, R, W), (B, W, R), (W, R, B), (W, B, R)
- 这 6 种 cycle 是 3! 排列，每个对应不同 root 选择

实际可能等价（如 (R,B,W) 起点不同 == (B,W,R) 起点偏移），但代码遍历安全。

### 4. 仅当颜色全有时尝试 3-pattern

如果图里只 2 色，pattern 退化为 2-cycle。代码动态用 `set(colors)`。

## 易错点

> [!pitfall]
> ❌ 假设只一种 pattern —— 漏 valid root；
> ❌ 没排除"同色相邻"违法 pattern（如 (R, R, B)）；
> ❌ permutations 会产生 size > 3 的；需限制 size 3；
> ❌ check 函数没限制 root degree ≤ 2。

> [!key]
> "找满足复杂模式的 root" 通过**枚举模式 + 验证**解决。常数因子大但 V³ 不爆。

> [!followup]
> "K 色 K-cycle？" → permutations 数 = K!，V 大时不可行；优化：观察"layer 0 颜色 = root 颜色"，固定后 pattern[1], pattern[2] 等也固定 → 减为 (K-1)! 或更少；"动态加节点？" → incremental check 难，全图重算；"返回所有 valid root？" → 收集而非 return first，注意可能多个 root 各自有不同 valid pattern。
