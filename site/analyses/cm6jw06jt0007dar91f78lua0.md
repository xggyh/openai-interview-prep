## 题目本质

**Problem About Interns and Flats Using a Greedy Approach**：给 N 个实习生，每人偏好 single-occupancy 或 shared apartment。给定 single 和 shared 房源数量限制，**最大化满意的实习生数**（按偏好分配）；或最小化总距离。

经典**匹配 / 贪心**题。

## 子问题

### 子问题 1：满足偏好最大化

```python
def assign_apartments(interns: list[str], n_single: int, n_shared: int):
    """interns[i] = 'single' or 'shared'"""
    want_single = sum(1 for x in interns if x == 'single')
    want_shared = sum(1 for x in interns if x == 'shared')
    happy = min(want_single, n_single) + min(want_shared, n_shared)
    # 剩下的人分配到错配类型（如果还有空房）
    extra_singles = max(0, want_single - n_single)
    extra_shared = max(0, want_shared - n_shared)
    free_singles_after = n_single - min(want_single, n_single)
    free_shared_after = n_shared - min(want_shared, n_shared)
    # 错配
    forced = min(extra_singles, free_shared_after) + min(extra_shared, free_singles_after)
    placed = happy + forced
    unplaced = len(interns) - placed
    return {'happy': happy, 'placed': placed, 'unplaced': unplaced}
```

### 子问题 2：最小化总距离

每个 intern 有 location，apartments 有 location。求**总距离最小**的分配（满足 capacity + 偏好）。

经典 **bipartite matching + min cost assignment**：Hungarian 算法 / minimum cost max flow。

```python
# 简化：假设 n_intern == n_apartments，求 minimum sum distance
# Hungarian: O(N³)
# 或 scipy.optimize.linear_sum_assignment（实现 Jonker-Volgenant）
import numpy as np
from scipy.optimize import linear_sum_assignment

def min_distance(intern_locs, apartment_locs):
    cost = np.array([[abs(i[0]-a[0]) + abs(i[1]-a[1])
                      for a in apartment_locs] for i in intern_locs])
    row, col = linear_sum_assignment(cost)
    return cost[row, col].sum()
```

## 复杂度

- 子问题 1：**O(N)**
- 子问题 2：**O(N³)** (Hungarian)

## 关键技术点

### 1. 子问题 1 是简单 count

每类需求和供给取 min 即"完美匹配"。剩余可错配。

### 2. 子问题 2 是 assignment problem

如果只是按偏好分组后**组内**最小距离：对每组独立排序 + 配对（O(N log N)）。如果**整体**最小距离则需 Hungarian。

### 3. 贪心 vs 最优

子问题 1 贪心最优（local choices 独立）。子问题 2 贪心**不一定**最优（需要全局优化）。

## 易错点

> [!pitfall]
> ❌ 子问题 2 用 "按 intern 顺序贪心选最近 apartment" —— 局部最优不全局；
> ❌ 假设 n_intern == n_apartment：实际可能不等；多余的部分不分配；
> ❌ 距离公式：欧氏 vs 曼哈顿 —— 题目而定；
> ❌ 偏好不可妥协的版本（违反偏好 = 不分配）VS 可妥协（warn + 分配）。

> [!key]
> 资源分配题永远先问：(1) 是否有偏好约束？(2) 优化目标是 count / sum / max-min？(3) 贪心是否能保证最优？子问题 1 是 counting；子问题 2 是 LP / Hungarian。

> [!followup]
> "动态加入新 intern？" → 维护当前空闲房列表，新人来时贪心选最近；"如果 intern 有优先级（先来先服务）？" → 按到达顺序贪心；"实际 Google 实习配房？" → 还要考虑 dorm、性别、cleaning 时间窗口等复杂约束。
