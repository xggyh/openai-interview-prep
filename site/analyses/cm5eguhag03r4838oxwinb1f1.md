## 题目本质

**LC 2258 Escape the Spreading Fire**：m×n 网格，0=空 / 1=火 / 2=墙。起点 (0,0)，终点 (m-1,n-1)。火每分钟向四方扩散。求出发前你**最多能等多少分钟**仍能到达终点（你每分钟走一格，先走再扩火）。返回 -1 不可逃；返回 1e9 永远可行。

**二分答案 + 双 BFS** 经典题，Google 高频。

## 解题切入点

- "最多等多少分钟" → 单调性：等得越久越难逃 → **二分等待时间 t**
- check(t)：你等 t 分钟后火扩散了 t 步，然后你和火同步推进。能不能到终点？
- 用 **多源 BFS 预计算** 每格被火点燃的最早时间 `fire_time[i][j]`
- 你从 (0,0) BFS，到达 (i,j) 的时间是 `t + dist[i][j]`。能通过当且仅当 `t + dist[i][j] < fire_time[i][j]`（终点允许等于）

## Python 实现

```python
from collections import deque
from typing import List

INF = float('inf')

class Solution:
    def maximumMinutes(self, grid: List[List[int]]) -> int:
        R, C = len(grid), len(grid[0])
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]

        # 1. Multi-source BFS：每格被火点燃的最早时刻
        fire = [[INF]*C for _ in range(R)]
        q = deque()
        for i in range(R):
            for j in range(C):
                if grid[i][j] == 1:
                    fire[i][j] = 0
                    q.append((i, j, 0))
        while q:
            x, y, t = q.popleft()
            for dx, dy in DIRS:
                nx, ny = x+dx, y+dy
                if 0<=nx<R and 0<=ny<C and grid[nx][ny] != 2 and fire[nx][ny] == INF:
                    fire[nx][ny] = t+1
                    q.append((nx, ny, t+1))

        # 2. check(t): 你等 t 分钟后能否到终点
        def can_escape(t: int) -> bool:
            seen = [[False]*C for _ in range(R)]
            seen[0][0] = True
            q = deque([(0, 0, t)])  # (x, y, your_time_at_this_cell)
            while q:
                x, y, ct = q.popleft()
                for dx, dy in DIRS:
                    nx, ny = x+dx, y+dy
                    if not (0<=nx<R and 0<=ny<C) or grid[nx][ny] == 2 or seen[nx][ny]:
                        continue
                    nt = ct + 1
                    if (nx, ny) == (R-1, C-1):
                        # 终点允许同时到达
                        if nt <= fire[nx][ny]:
                            return True
                        continue
                    if nt < fire[nx][ny]:
                        seen[nx][ny] = True
                        q.append((nx, ny, nt))
            return False

        # 3. 二分等待时间 t
        if not can_escape(0):
            return -1
        if can_escape(10**9):
            return 10**9
        lo, hi = 0, R * C
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if can_escape(mid):
                lo = mid
            else:
                hi = mid - 1
        return lo
```

## 复杂度

- 二分次数：O(log(R×C))
- 每次 check：BFS O(R×C)
- 火扩散预计算：O(R×C)
- 总：**O(R × C × log(R×C))**

## 关键技术点

### 1. 终点的特殊规则

题目允许"你和火同时到达终点"成功逃脱。所以终点判断 `<=`，其他格子是严格 `<`。这个细节是这道题最大的坑。

### 2. 为什么 hi 上限是 R×C 而不是 INF

最坏情况你只能等到第一个火快要扩到你的时候出发，即 `dist[(0,0)]` 之前。R×C 是 BFS 距离的上限。

### 3. 火无法到达的格子用 INF

如果某格被墙包围，火永远到不了 → fire_time = INF → 你可以无限晚出发，但其他格子可能受限。所以单独 `can_escape(10^9)` 测试是否所有等待都行。

## 易错点

> [!pitfall]
> ❌ 终点用 `<` 而非 `<=` —— 漏算"同时到达"成功 case；
> ❌ 没用 multi-source BFS 算火扩散，逐源 BFS 取 min —— 复杂度 × N（N 个起火点）；
> ❌ 二分时 `mid = (lo+hi)/2` 没 `+1` —— 死循环；
> ❌ 把"等待 t 分钟"理解成"你在 (0,0) 等 t 分钟然后火也停" —— 错，火每分钟都在扩，等 t 分钟 = 火扩 t 步；
> ❌ 把墙(2)也加入 fire/dist BFS —— 应跳过。

> [!key]
> "求最大允许值 + 单调性 check" → 二分答案。这套模式在 Google 高频：船只载重、最大相邻距离、最少时间等。多源 BFS 算"每格火到达时间" 是 grid 类问题的标准预处理。

> [!followup]
> "如果火 8 方向扩散？" → DIRS 改 8 方向；"如果终点也可以是火？" → 题面已隐含起点 / 终点不会初始为火；"如果允许你走斜线？" → BFS 步骤换 8 方向，距离仍是步数；"打印路径？" → 在 can_escape 里记录 parent。
