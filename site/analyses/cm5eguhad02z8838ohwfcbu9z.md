## 题目本质

**LC 1254 Number of Closed Islands**：grid 中 `0=陆地, 1=水`。求**完全被水包围**（不接触 grid 边界）的陆地岛屿数量。

## 解题思路

两阶段 DFS：
1. **先从所有边界陆地出发 DFS**，把它们染色（视为水）—— 这样剩下的陆地全部不接触边界
2. 然后对剩下的陆地 DFS 数岛

## Python 实现

```python
from typing import List

class Solution:
    def closedIsland(self, grid: List[List[int]]) -> int:
        if not grid: return 0
        R, C = len(grid), len(grid[0])
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]

        def dfs(r: int, c: int):
            if not (0 <= r < R and 0 <= c < C) or grid[r][c] != 0:
                return
            grid[r][c] = 1   # 标记为水
            for dr, dc in DIRS:
                dfs(r+dr, c+dc)

        # 边界陆地 DFS 消除
        for r in range(R):
            for c in range(C):
                if (r == 0 or r == R-1 or c == 0 or c == C-1) and grid[r][c] == 0:
                    dfs(r, c)
        # 数内部岛
        count = 0
        for r in range(1, R-1):
            for c in range(1, C-1):
                if grid[r][c] == 0:
                    count += 1
                    dfs(r, c)
        return count
```

## 复杂度

- 时间：**O(R × C)**，每个 cell 最多 DFS 一次
- 空间：O(R × C) 递归栈（最坏蛇形 grid）

## 关键点

### 1. 边界 sink 技巧

先把"接触边界"的陆地都"淹没"，剩下的陆地按定义都是 closed。这避免了在主 DFS 里判断"是否触边界"的复杂 propagate 标记。

### 2. In-place modify vs visited set

`grid[r][c] = 1` 直接改原数组省内存，但会破坏输入。如果不能改，用 `visited` set。

### 3. 数完内岛后 grid 已全 1

DFS 把所有陆地都改成 1。如果调用方还要再用 grid，要复制。

## 易错点

> [!pitfall]
> ❌ 直接数 island 不消除边界 —— 把接触边界的也算进去；
> ❌ 主 DFS 里 propagate "touched_boundary" flag —— 实现复杂且易错；
> ❌ DFS 边界判断写在第二个 if（值检查）之前 —— OK 但要先 range check 否则 IndexError；
> ❌ 把 1 当 land：题目是 0 = land。

> [!key]
> "排除边界相关" 套路：先逆向消除（边界 DFS），再正向数。同模板：LC 130 Surrounded Regions、LC 1020 Number of Enclaves。

> [!followup]
> "返回最大 closed island 面积？" → DFS 记 size，取 max；"8 方向？" → DIRS 扩展；"求所有 closed island 的总面积？" → 累加。
