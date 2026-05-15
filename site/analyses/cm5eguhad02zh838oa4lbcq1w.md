## 题目本质

**LC 1263 Minimum Moves to Move a Box to Their Target Location**：grid 上有 player、box、target、wall。Player 推 box (只能 from 反方向)；Player 自由移动到 box 旁但不能穿 wall/box。求 box 到 target 的最少**推动次数**。返回 -1 不可。

## 解法

**双层 BFS**：状态 = (box_pos, player_pos)。状态空间大但每"推 box"算一次 step。

```python
from collections import deque
from typing import List

class Solution:
    def minPushBox(self, grid: List[List[str]]) -> int:
        R, C = len(grid), len(grid[0])
        for r in range(R):
            for c in range(C):
                if grid[r][c] == 'B': box = (r, c)
                if grid[r][c] == 'S': player = (r, c)
                if grid[r][c] == 'T': target = (r, c)
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]

        def passable(r, c, blocked):
            return (0 <= r < R and 0 <= c < C and grid[r][c] != '#' and (r,c) != blocked)

        def player_can_reach(start, dest, blocked_box):
            """Player from start can reach dest without stepping on blocked_box / wall."""
            if start == dest: return True
            q = deque([start])
            seen = {start}
            while q:
                r, c = q.popleft()
                for dr, dc in DIRS:
                    nr, nc = r+dr, c+dc
                    if (nr, nc) == dest:
                        return True
                    if passable(nr, nc, blocked_box) and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        q.append((nr, nc))
            return False

        # 状态 = (box, player_pos)；但只需 (box, side player came from)
        # 0-1 BFS：推动 = 1 步，player 自由移动 = 0 步
        # 简化：deque BFS by box positions，记 visited[box][prev_player_side]
        visited = set()
        q = deque([(0, box, player)])
        # use plain BFS: pushed steps as level
        # actually use Dijkstra-like: priority queue with push count
        import heapq
        pq = [(0, box[0], box[1], player[0], player[1])]
        visited = set()
        while pq:
            steps, br, bc, pr, pc = heapq.heappop(pq)
            if (br, bc) == target:
                return steps
            if (br, bc, pr, pc) in visited: continue
            visited.add((br, bc, pr, pc))
            for dr, dc in DIRS:
                # box moves to (br+dr, bc+dc), player must be at (br-dr, bc-dc)
                new_br, new_bc = br + dr, bc + dc
                need_pr, need_pc = br - dr, bc - dc
                if not (0 <= new_br < R and 0 <= new_bc < C and grid[new_br][new_bc] != '#'):
                    continue
                if not (0 <= need_pr < R and 0 <= need_pc < C and grid[need_pr][need_pc] != '#'):
                    continue
                # Player must reach need_pos without passing through box
                if player_can_reach((pr, pc), (need_pr, need_pc), (br, bc)):
                    heapq.heappush(pq, (steps + 1, new_br, new_bc, new_br, new_bc))
        return -1
```

## 复杂度

- 状态：O(R² × C²)（box pos × player pos）
- 每状态 player_can_reach 是 O(R × C)
- 总：**O((R × C)³)**

R, C ≤ 20 → 64 万 × 400 = ~250M，紧但能过。

## 关键技术点

### 1. 状态包含 player 位置

不是只 box 位置 —— 同 box 位置，player 在不同侧能推的方向不同。

### 2. 推动方向 = player 在反方向

推 box 向右 → player 在 box 左侧。所以需要 `player_can_reach((br-dr, bc-dc))`。

### 3. Player 移动用 BFS 子算法

每次 box 状态扩展前，先确认 player 能从当前位置到 box 的"反方向"。

### 4. 0-1 BFS 或 Dijkstra

推动 = 1 步；player 移动 = 0 步。可以用 deque（0 走 push front，1 走 push back）替代 heap 优化常数。

## 易错点

> [!pitfall]
> ❌ 把 player 移动也当成 step —— 题目只数推动；
> ❌ Player 路径中允许穿过 box —— 不行；
> ❌ 状态只 (box) 不含 player —— 漏推方向；
> ❌ Dijkstra 没用 visited set —— 重复扩展 TLE。

> [!key]
> 经典"推箱子"游戏（Sokoban）的简化版。状态空间大题：**(物体 pos, 玩家 pos) 联合状态**。同思路：LC 773 Sliding Puzzle、迷宫双人协作。

> [!followup]
> "多 box？" → 状态加 box 数维，搜索爆炸（NP-hard general Sokoban）；"返回推动序列？" → 父指针回溯；"A* 加速？" → Manhattan distance 作 heuristic。
