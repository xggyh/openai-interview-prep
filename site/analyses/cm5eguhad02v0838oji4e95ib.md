## 题目本质

**LC 1102 Path With Maximum Minimum Value**：grid 上从左上到右下的路径（4 方向），求所有路径中"路径最小值"的**最大**值。即 max over paths of (min over cells on path of grid[i][j])。

## 解法

**最大化 minimum** 类问题 → 二分 / 贪心。

### 方法 1：Max-Heap + BFS（推荐）

像 Dijkstra：每次扩展当前最大可达 cell。

```python
import heapq
from typing import List

class Solution:
    def maximumMinimumPath(self, grid: List[List[int]]) -> int:
        R, C = len(grid), len(grid[0])
        seen = [[False]*C for _ in range(R)]
        # max-heap by cell value
        heap = [(-grid[0][0], 0, 0)]
        seen[0][0] = True
        best = grid[0][0]
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]
        while heap:
            v, r, c = heapq.heappop(heap)
            best = min(best, -v)
            if (r, c) == (R-1, C-1):
                return best
            for dr, dc in DIRS:
                nr, nc = r+dr, c+dc
                if 0 <= nr < R and 0 <= nc < C and not seen[nr][nc]:
                    seen[nr][nc] = True
                    heapq.heappush(heap, (-grid[nr][nc], nr, nc))
        return best
```

### 方法 2：Union-Find（更高效）

按值降序处理 cell。每个 cell 加入"激活集"，与已激活的邻居 union。当 (0,0) 和 (R-1, C-1) 同一连通分量时，**当前阈值**就是答案。

## 复杂度

| 方法 | 时间 |
|---|---|
| Max-heap | O(R × C × log(R×C)) |
| Union-Find | O(R × C × α(R×C)) ≈ O(R×C) |

## 关键技术点

### 1. 为什么 Max-Heap 正确

总是从"剩下未访问 cell 中值最大者"扩展。当终点被弹出时，当前路径上 min 值就是 best。

因为路径上的 cell 都是先于终点被弹出的（按值降序），路径 min 就是路径中**最后弹出**的（即最小）。

### 2. seen 在 enqueue 时标

避免重复入队同一 cell（不同优先级版本）。

### 3. Initial best = grid[0][0]

进入 (0,0) 时就要包含其值。

## 易错点

> [!pitfall]
> ❌ 普通 BFS / DFS —— 不能保证最大 min；
> ❌ 用普通 Dijkstra 累加 —— 题目是 min 不是 sum；
> ❌ Heap 用 (value, ...) 不 negate —— Python heapq 是 min-heap，要 negate；
> ❌ seen 在 dequeue 时标 —— 重复入队浪费。

> [!key]
> "最大化 minimum" / "最小化 maximum" 模式：用 max-heap BFS 或 Union-Find 加边按权重排序。这套思路：LC 778 Swim in Rising Water、LC 1631 Path with Minimum Effort（最小化 max）。

> [!followup]
> "二分答案？" → `can_reach(threshold)` 用 BFS 只走 ≥ threshold cell；二分 threshold；"加权 cell？" → 把 value 当通行成本，最大流 / max-bottleneck path；"8 方向？" → DIRS 扩展。
