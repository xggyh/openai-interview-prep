## 题目本质

**LC 913 Cat and Mouse**：图上有猫鼠游戏。鼠从节点 1，猫从节点 2，洞在节点 0。鼠先走。猫不能进洞，但鼠可以。鼠胜利：进洞；猫胜利：抓到鼠；平局：状态重复。最优博弈，求结果。返回 1（鼠胜）/ 2（猫胜）/ 0（平局）。

经典 **game theory + BFS / DFS with memoization (minimax)** 题。Hard。

## 解题思路

**状态**：`(mouse_pos, cat_pos, turn)`，turn = 0 (mouse) / 1 (cat)。共 N² × 2 个状态。

**结果**：
- `mouse_pos == 0` → 1 (mouse wins)
- `mouse_pos == cat_pos` → 2 (cat wins)
- 其他：递归

**对于谁的回合**：
- Mouse turn：mouse 想赢，找有"mouse wins" 后继；找不到才考虑"draw"，最后才"cat wins"
- Cat turn：cat 想赢

**关键 trick — Retrograde Analysis（逆向 BFS）**：
- 起点是已知结果的终态（mouse=0 或 mouse==cat）
- 反向 propagate：如果一个状态的所有后继都是 cat 赢，且现在是 mouse 回合，那这个状态是 cat 赢

直接 minimax DFS 会有循环（鼠猫绕圈 = draw），必须用逆向方法。

## Python 实现

```python
from collections import deque
from typing import List

DRAW, MOUSE, CAT = 0, 1, 2

class Solution:
    def catMouseGame(self, graph: List[List[int]]) -> int:
        N = len(graph)
        # color[m][c][turn] = 0 (unknown/draw) / 1 (mouse wins) / 2 (cat wins)
        color = [[[0]*2 for _ in range(N)] for _ in range(N)]
        # degree[m][c][turn] = 该状态有几个未确定后继
        degree = [[[0]*2 for _ in range(N)] for _ in range(N)]
        for m in range(N):
            for c in range(N):
                degree[m][c][0] = len(graph[m])  # mouse turn: mouse moves
                degree[m][c][1] = len(graph[c])
                # cat 不能进 0
                if 0 in graph[c]:
                    degree[m][c][1] -= 1

        q = deque()
        # 初始化终态：mouse=0 → mouse wins；mouse==cat → cat wins
        for i in range(N):
            for t in range(2):
                color[0][i][t] = MOUSE
                q.append((0, i, t, MOUSE))
                if i > 0:
                    color[i][i][t] = CAT
                    q.append((i, i, t, CAT))

        # 逆向 BFS
        while q:
            m, c, t, win = q.popleft()
            # 找出所有"前驱"状态：上一步是另一个玩家，移动后到 (m, c, t)
            prev_turn = 1 - t
            # 前驱 mouse 位置
            if prev_turn == 0:
                # 上一步是 mouse turn，mouse 移到 m
                # 前驱：mouse 在某个 prev_m（neighbor of m），cat 在 c
                for prev_m in graph[m]:
                    if color[prev_m][c][prev_turn] == DRAW:
                        if win == MOUSE and prev_turn == 0:
                            # mouse 选 → mouse 想要 mouse wins → 立即确定
                            color[prev_m][c][prev_turn] = MOUSE
                            q.append((prev_m, c, prev_turn, MOUSE))
                        elif win == CAT and prev_turn == 0:
                            # mouse 不会主动选 cat wins，除非所有后继都是 cat wins
                            degree[prev_m][c][prev_turn] -= 1
                            if degree[prev_m][c][prev_turn] == 0:
                                color[prev_m][c][prev_turn] = CAT
                                q.append((prev_m, c, prev_turn, CAT))
            else:
                # 上一步是 cat turn，cat 移到 c
                for prev_c in graph[c]:
                    if prev_c == 0:
                        continue  # cat 不能进 0
                    if color[m][prev_c][prev_turn] == DRAW:
                        if win == CAT and prev_turn == 1:
                            color[m][prev_c][prev_turn] = CAT
                            q.append((m, prev_c, prev_turn, CAT))
                        elif win == MOUSE and prev_turn == 1:
                            degree[m][prev_c][prev_turn] -= 1
                            if degree[m][prev_c][prev_turn] == 0:
                                color[m][prev_c][prev_turn] = MOUSE
                                q.append((m, prev_c, prev_turn, MOUSE))

        return color[1][2][0]   # 起始状态：mouse=1, cat=2, mouse turn
```

## 复杂度

- 状态数：O(N²)
- 每状态最多被 visited 一次（color 不为 DRAW 之后不再 enqueue）
- 每个状态遍历邻居 O(degree)
- 总：**O(N³)**（包含邻居展开）

## 关键技术点

### 1. 为什么不用普通 minimax DFS

普通 minimax 在有环图上死循环。"鼠猫绕圈" 是 valid draw 但 DFS 没法判断。逆向 BFS（retrograde analysis）从终态向前推，自然处理了"未确定 = draw"。

### 2. degree 计数

mouse 是 minimizer 的回合（对 cat 而言），它会想避免 cat 赢。所以当 cat 想让 mouse 输（即想要 cat wins），mouse 在上一步只会被迫选 cat wins 当且仅当**所有后继都是 cat wins**。degree 记录剩余未确定后继数 —— 到 0 时整个状态确定。

### 3. cat 不能进 0

`if 0 in graph[c]: degree--`。逆向 BFS 时检查 `prev_c == 0 → skip`。

### 4. 起始状态

题目固定起始 `mouse=1, cat=2, turn=mouse`。返回 `color[1][2][0]`。

## 易错点

> [!pitfall]
> ❌ 用普通 minimax DFS —— 死循环；
> ❌ cat 进 0 没禁止 —— 答案错；
> ❌ Retrograde BFS 时把"未确定 = 0"和"DRAW = 0"混淆 —— 题目正好都是 0，但逻辑上 unknown != draw 直到所有都处理完；
> ❌ degree 初始化时忘了 cat-不能-进-0 的修正。

> [!key]
> 这道题是 LC 上 hard 中的 hard。核心思想：**状态空间博弈用逆向 BFS 而非 DFS**。同套路：四子棋判胜负、围棋小型 endgame solver、对抗搜索 with cycles。

> [!followup]
> "猫和鼠不同速度（每回合可走 K 步）？" → 状态加 step 计数；"图允许多边？" → 邻接表里重复邻居即可；"扩展到 3 玩家？" → state 加第三玩家位置；"用 reinforcement learning 训练？" → minimax 的 ML 版本（DQN with self-play）。
