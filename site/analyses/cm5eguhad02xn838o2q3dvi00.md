## 题目本质

**LC 1197 Minimum Knight Moves**：国际象棋骑士从 `(0,0)` 出发，每步走 L 形（±2, ±1 或 ±1, ±2）。求到 `(x, y)` 的最少步数。无限棋盘。

经典**BFS** + 利用**对称性**优化。

## 解题思路

### 朴素 BFS
8 个方向 BFS，visited set。`-300 ≤ x, y ≤ 300`，状态空间 ~360k，可解。

### 对称性优化
骑士跳跃在 4 象限对称。只考虑 `(|x|, |y|)`（折叠到第一象限），visited set 只存正数坐标，大幅减少搜索。

## Python 实现（带对称性）

```python
from collections import deque

class Solution:
    def minKnightMoves(self, x: int, y: int) -> int:
        x, y = abs(x), abs(y)
        if x == 0 and y == 0:
            return 0
        # 8 个 L 移动
        DIRS = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
        q = deque([(0, 0, 0)])
        seen = {(0, 0)}
        while q:
            cx, cy, steps = q.popleft()
            for dx, dy in DIRS:
                nx, ny = cx + dx, cy + dy
                if nx == x and ny == y:
                    return steps + 1
                # 折叠到第一象限：只允许 (nx, ny) >= (-2, -2)（防止跨过原点）
                if nx < -2 or ny < -2:
                    continue
                key = (nx, ny)
                if key not in seen:
                    seen.add(key)
                    q.append((nx, ny, steps + 1))
```

**为什么 -2？** 折叠到 `(|x|, |y|)` 后，骑士最远跳 2 步会到 -2。允许小负数能让目标在轴上时通过原点附近 detour。完全严格 ≥ 0 会算偏。

## 朴素 BFS（不优化）

```python
class Solution:
    def minKnightMoves(self, x: int, y: int) -> int:
        DIRS = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
        target = (x, y)
        q = deque([(0, 0, 0)])
        seen = {(0, 0)}
        while q:
            cx, cy, s = q.popleft()
            if (cx, cy) == target:
                return s
            for dx, dy in DIRS:
                nx, ny = cx+dx, cy+dy
                if (nx, ny) not in seen and -310 <= nx <= 310 and -310 <= ny <= 310:
                    seen.add((nx, ny))
                    q.append((nx, ny, s+1))
        return -1
```

## 双向 BFS（更快）

从 (0,0) 和目标同时 BFS，相遇时返回 step 和。**搜索空间 √2 倍优化**。LC 数据下不必要。

## 公式法（O(1)）

骑士到 (x, y) 的最少步数有闭式公式（基于 max(|x|, |y|) 和 (|x|+|y|) 的关系），但**面试不期望背公式**。BFS 是标准答案。

## 复杂度

- 朴素 BFS：O(N²)，N = 坐标范围
- 对称性：O((N/2)²) ≈ 4x 加速
- 双向 BFS：O(N²/2)

## 易错点

> [!pitfall]
> ❌ 不限制搜索范围 —— 无限棋盘 BFS 永远跑；
> ❌ 折叠对称性用严格 `nx >= 0, ny >= 0` —— 漏掉某些路径；
> ❌ 8 方向 list 写错（漏 / 写 (1,1)）；
> ❌ Visited 在 enqueue 时不加 —— 重复入队 TLE；
> ❌ 用 DFS 而非 BFS —— 不能保证最短。

> [!key]
> 单源最短路径 + 无权图 = BFS 必杀。对称性优化是这道题的"亮点"，能在面试上加分。LC 1197 数据范围 ±300 比较温和，朴素 BFS 也过。

> [!followup]
> "有限棋盘（如 8x8）？" → BFS 加 bounds check；"加障碍？" → BFS 跳过障碍；"求所有最短路径数量？" → BFS 时累加 count；"3D 棋盘？" → 12 个 L 方向。
