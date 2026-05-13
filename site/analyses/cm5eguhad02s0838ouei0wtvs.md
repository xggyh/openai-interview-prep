## 题目本质

LeetCode 994 Rotting Oranges：m×n 网格，0=空 / 1=新鲜 / 2=腐烂。每分钟所有腐烂橘子 4 方向扩散到相邻新鲜橘子。求所有新鲜变腐烂的最短分钟数；若有新鲜永远无法腐烂返回 -1。

**多源 BFS** 经典题。OpenAI 真实报告 Senior 级，"interviewer does not care about optimized solution"。

## 解题思路

不是单源 BFS（一个起点），而是**多源 BFS**：所有初始 `2` 同时入队作为 level 0，每轮处理一层。

## Python 实现

```python
from collections import deque
from typing import List

class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        if not grid or not grid[0]: return 0
        R, C = len(grid), len(grid[0])
        q = deque()
        fresh = 0
        for r in range(R):
            for c in range(C):
                if grid[r][c] == 2:
                    q.append((r, c))
                elif grid[r][c] == 1:
                    fresh += 1
        if fresh == 0:
            return 0

        minutes = 0
        DIRS = [(-1,0),(1,0),(0,-1),(0,1)]
        while q and fresh > 0:
            for _ in range(len(q)):  # 处理整层
                r, c = q.popleft()
                for dr, dc in DIRS:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < R and 0 <= nc < C and grid[nr][nc] == 1:
                        grid[nr][nc] = 2
                        fresh -= 1
                        q.append((nr, nc))
            minutes += 1

        return minutes if fresh == 0 else -1
```

## 复杂度

- 时间：**O(R × C)**，每个 cell 最多入队一次
- 空间：**O(R × C)** 队列最坏装满

## 关键点

1. **多源初始化**：把所有 `2` 在循环开始前都 push 进队列（这就是"多源"）
2. **按层处理**：用 `for _ in range(len(q))` 把本层全部出队后再 `minutes += 1`
3. **提早终止**：`while q and fresh > 0`，没有新鲜橘子就不再增加 minutes
4. **-1 判定**：循环结束后还有 fresh，说明有不可达

## 边界 case

| Case | 期望返回 |
|---|---|
| 全空 grid | 0 |
| 全 1（无 2） | -1 |
| 全 2 | 0 |
| 单 cell `[[1]]` | -1 |
| 单 cell `[[2]]` | 0 |

## 易错点

> [!pitfall]
> ❌ **没按层处理**：直接 BFS 出队累加 1，每个 cell 都 +1 minute → 错；
> ❌ **fresh = 0 时返回 -1**：开局就没新鲜，应返回 0；
> ❌ **初始没把所有 2 入队**：错把它当单源 BFS；
> ❌ **修改 grid 而不更新 fresh** → 死循环或 -1 错判。

## 变种

OpenAI 抓到的真实变种（见列表中的 "Disease Spread in Flower Grid"）：**每个 cell 被感染需要 ≥ T 个感染邻居**。T=1 退化为标准 994；T≥2 需要按层同步推进（不能逐个出队就翻转，因为同一层内的传播必须并行）。详见 `Disease Spread in Flower Grid` 那一题的分析。

> [!key]
> 多源 BFS = "把所有起点放进 q 同时启动" + "按层数累计步数"。这套模板还能解：LC 1162 As Far From Land、LC 542 01 Matrix。

> [!followup]
> "如果是 8 方向（含对角）？" DIRS 加 4 个对角；"如果有些细胞免疫（永远不感染）？" 标记成 `3` 在传播时跳过；"返回每个 cell 被感染的具体时刻？" 用 dict `time[(r,c)]` 在 BFS 翻转时记 minutes。
