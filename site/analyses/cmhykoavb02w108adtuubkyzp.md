## 题目本质

经典 **Rotting Oranges** (LC 994) 的变种 —— 在 m × n 花朵网格上模拟疾病传播。基本传播规则是 4 方向、每分钟一步；但 hellointerview 上抓到的真实 OpenAI 报告里**变种是关键**：

> **每分钟，一个未感染的细胞被感染当且仅当它的 4 个邻居中至少有 T 个已感染**。求所有细胞都被感染所需的最少分钟数；若无法全部感染返回 -1。当 T=1 时退化为标准 994。

这是一道 **多源 BFS + 阈值传播** 题，本质考"层级扩散 + 同步推进"。

## 解题切入点

- **如果 T=1**：直接是 LC 994 多源 BFS。
- **如果 T≥2**：单细胞被感染不仅取决于自己有几个感染邻居，还取决于"本轮结束时"邻居们是否都已感染 —— 即**同一时间步的感染要同步生效**，不能按入队顺序串行更新。
- 经典 BFS 按"层"（level）处理就能保证同步性：每次弹出**整层**节点，先全部处理本层、再统一标记下一层、最后切换。

## 主解法

```python
from collections import deque
from typing import List

def disease_spread(grid: List[List[int]], T: int = 1) -> int:
    """
    grid[i][j]:
        0 = 空（不参与）
        1 = 健康
        2 = 已感染
    Returns 最少分钟数；若有健康细胞无法被感染返回 -1。
    """
    if not grid or not grid[0]:
        return 0
    R, C = len(grid), len(grid[0])
    # 多源 BFS 起点：所有初始感染
    q = deque()
    healthy = 0
    for i in range(R):
        for j in range(C):
            if grid[i][j] == 2:
                q.append((i, j))
            elif grid[i][j] == 1:
                healthy += 1
    if healthy == 0:
        return 0

    minutes = 0
    DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while q and healthy > 0:
        # 本轮：先统计每个 1 细胞的"感染邻居数"
        # 一种实现：用计数数组 cnt[i][j] 记录每个健康细胞的感染邻居数
        # T==1 时退化为普通 BFS，可省去 cnt
        if T == 1:
            level_size = len(q)
            for _ in range(level_size):
                x, y = q.popleft()
                for dx, dy in DIRS:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < R and 0 <= ny < C and grid[nx][ny] == 1:
                        grid[nx][ny] = 2
                        healthy -= 1
                        q.append((nx, ny))
        else:
            # 通用 T：本轮把所有"被感染邻居数 ≥ T"的健康细胞批量翻转
            cnt = {}
            for x, y in q:
                for dx, dy in DIRS:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < R and 0 <= ny < C and grid[nx][ny] == 1:
                        cnt[(nx, ny)] = cnt.get((nx, ny), 0) + 1
            newly_infected = [pos for pos, c in cnt.items() if c >= T]
            if not newly_infected:
                # 本轮无新感染 -> 卡住了
                return -1
            q.clear()
            for x, y in newly_infected:
                grid[x][y] = 2
                healthy -= 1
                q.append((x, y))
        minutes += 1

    return minutes if healthy == 0 else -1
```

**关键点：**
- 按"层"处理保证同步：本层所有感染细胞先一起对邻居计数 → 再统一翻转 → 计入 minute。
- 用 `cnt` dict 而非每层重新扫整张图（在稀疏感染时省时间）。
- `healthy` 计数提早终止 + 直接判 -1。

## 复杂度

- 时间：**O(R × C × max_minutes)**。最坏每步只感染 1 个 → max_minutes = R×C，总 O((R×C)²)。但实际 BFS 层数 ≤ 直径 = O(R+C)，多数情况是 O(R × C)。
- 空间：**O(R × C)** （队列 + cnt dict）。

## 易错点 / Red Flag

> [!pitfall]
> ❌ **逐个出队就把邻居感染**：在 T≥2 时错误，因为同一轮中先后到达的细胞会"串行"感染，产生连锁，分钟数偏小。必须按层处理。
> ❌ **不查 healthy == 0**：所有 1 都不连通时返回 0 vs -1 容易写错。
> ❌ **忘了空网格 / 全空 / 全感染** 边界。
> ❌ **就地修改 grid** 后忘了 healthy 计数 → 死循环或漏感染。

## 真实候选人变种

抓到的 OpenAI report 还提到过：
- "interviewer does not care about optimized solution, go with what will pass the test cases" —— **能跑过就行**，先写正确再优化。
- 另一些公司（Amazon 多）问的是标准 994。

> [!key]
> OpenAI 报告里出现 T≥2 的变种是真实的，要准备好"层级同步"的写法 —— 这是面试官区分 senior vs junior 的关键观察点。

> [!followup]
> "8 方向（含对角线）怎么改？" → DIRS 加 4 个对角线 case。"如果是无穷网格只给若干初始感染点？" → 用 dict 表示稀疏网格 + 同样多源 BFS。"如果传播速度不一样（每个细胞有不同 T）？" → cnt 比较改为 `cnt[(x,y)] >= T_at(x,y)`。"如果需要返回每个细胞被感染的时间？" → 在 BFS 翻转时记 `infection_time[(x,y)] = minutes`。
