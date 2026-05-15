## 题目本质

**LC 2812 Find the Safest Path in a Grid**：grid 中 1 = 小偷，0 = 空。路径 safeness 定义 = 路径上所有 cell 到**最近小偷**的曼哈顿距离的最小值。求 (0,0) 到 (n-1,n-1) 路径的最大 safeness。

## 解法

**多源 BFS + 二分答案** 或 **Max-Heap BFS**。

### Phase 1: 多源 BFS 算 cell 到最近小偷距离

```python
from collections import deque
import heapq
from typing import List

class Solution:
    def maximumSafenessFactor(self, grid: List[List[int]]) -> int:
        n = len(grid)
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]
        # dist[i][j] = (i,j) 到最近小偷的曼哈顿距离
        dist = [[-1]*n for _ in range(n)]
        q = deque()
        for r in range(n):
            for c in range(n):
                if grid[r][c] == 1:
                    dist[r][c] = 0
                    q.append((r, c))
        while q:
            r, c = q.popleft()
            for dr, dc in DIRS:
                nr, nc = r+dr, c+dc
                if 0<=nr<n and 0<=nc<n and dist[nr][nc] == -1:
                    dist[nr][nc] = dist[r][c] + 1
                    q.append((nr, nc))

        # Phase 2: Max-heap from (0,0) by current cell's dist
        seen = [[False]*n for _ in range(n)]
        # heap = (-dist, r, c)
        pq = [(-dist[0][0], 0, 0)]
        seen[0][0] = True
        while pq:
            negd, r, c = heapq.heappop(pq)
            if (r, c) == (n-1, n-1):
                return -negd
            for dr, dc in DIRS:
                nr, nc = r+dr, c+dc
                if 0<=nr<n and 0<=nc<n and not seen[nr][nc]:
                    seen[nr][nc] = True
                    # 经过该 cell 的 safeness 受限于 min(当前, dist[nr][nc])
                    new_safeness = min(-negd, dist[nr][nc])
                    heapq.heappush(pq, (-new_safeness, nr, nc))
        return 0
```

## 复杂度

- Phase 1: O(N²)（多源 BFS）
- Phase 2: O(N² log N)（max-heap 扫每 cell）
- 总：**O(N² log N)**

## 关键技术点

### 1. 多源 BFS 算距离

所有小偷一起入队作为 level 0。BFS 自然算出每 cell 到最近小偷的曼哈顿距离（因为 BFS 在网格上 = 曼哈顿）。

### 2. Max-heap 类似 LC 1102

路径上的 safeness = path min。要最大化 → max-heap 优先扩展"当前 safeness 最大的"未访问 cell。

### 3. Safeness 单调下降

从 (0,0) 沿 max-heap 扩展，safeness 单调不增。到 (n-1,n-1) 时弹出的 safeness 就是答案。

## 替代：二分答案

二分 safeness 值 t：check 是否存在 (0,0)→(n-1,n-1) 仅经过 dist >= t 的 cell。O(N² log(maxDist))。

## 易错点

> [!pitfall]
> ❌ 用 sum-path 算距离而非 min-path —— 题意是 min；
> ❌ 用 Euclidean 距离而非 Manhattan —— grid 上 BFS 步数 = Manhattan；
> ❌ Heap 没用 max（用 min-heap negate 或反向）；
> ❌ Visited 在 push 时不加 —— 重复入队。

> [!key]
> 多源 BFS 算"每 cell 到最近 X" 是 grid 题常用预处理。max-min path 用 max-heap BFS 类似 Dijkstra 思路。

> [!followup]
> "Min-max path（最小化 max）？" → min-heap；"路径上的 sum？" → 普通 Dijkstra；"返回路径？" → 记 parent，从终点回溯。
