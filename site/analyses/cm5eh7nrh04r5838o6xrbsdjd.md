## 题目本质

**LC 149 Max Points on a Line**：给一组点 (x, y)，求**最多有多少点共线**。

经典**斜率 + hash** 题。Hard 因为精度问题。

## 解法

对每个 anchor 点 p：
- 计算其他点到 p 的斜率
- 用 dict 统计每个斜率的点数
- 答案 = max(同斜率点数) + 1（包含 anchor 自己）

枚举每个 anchor，取全局 max。

## 精度陷阱

直接用 float `dy / dx` 不可靠（浮点误差导致同斜率算成不同）。**用 `(dy/gcd, dx/gcd)` tuple 作 key**，化简到最简分数。

## Python 实现

```python
from math import gcd
from collections import defaultdict
from typing import List

class Solution:
    def maxPoints(self, points: List[List[int]]) -> int:
        n = len(points)
        if n <= 2: return n

        result = 0
        for i in range(n):
            slopes: dict[tuple, int] = defaultdict(int)
            duplicates = 1   # 起始包含自己
            for j in range(n):
                if i == j: continue
                dx = points[j][0] - points[i][0]
                dy = points[j][1] - points[i][1]
                if dx == 0 and dy == 0:
                    duplicates += 1
                    continue
                g = gcd(dx, dy)
                dx, dy = dx // g, dy // g
                # 规范化：dx > 0；如果 dx == 0 强制 dy > 0
                if dx < 0:
                    dx, dy = -dx, -dy
                elif dx == 0 and dy < 0:
                    dy = -dy
                slopes[(dy, dx)] += 1
            local_max = max(slopes.values(), default=0)
            result = max(result, local_max + duplicates)
        return result
```

## 复杂度

- 时间：**O(N²)** 双 loop
- 空间：O(N)（每 anchor 的 slopes dict）

## 关键技术点

### 1. 用 gcd 化简斜率

`gcd(dy, dx)` 把斜率化最简。Python `math.gcd` 接受负数返回非负 → 但符号处理要小心。

### 2. 符号规范化

`(dy, dx)` 和 `(-dy, -dx)` 同一斜率。规范化：让 dx > 0；如果 dx = 0（垂直线）让 dy > 0。

### 3. 重复点

两点完全相同 (dx=dy=0) 不形成线但贡献"点数"。单独 count `duplicates`。

### 4. n ≤ 2 边界

任何两点共线。直接返回 n。

## 易错点

> [!pitfall]
> ❌ 直接用 `dy/dx` 浮点 —— 精度坑（如 1/3 和 2/6 算不同）；
> ❌ gcd(0, x) = x，注意处理（垂直/水平线时一个为 0）；
> ❌ 重复点没单独处理 —— count 偏少；
> ❌ 符号规范化漏一种 case；
> ❌ `defaultdict(int)` 没考虑 anchor 自己不应纳入 slopes —— 用 if i==j skip。

> [!key]
> "共线" 题的核心：斜率 gcd 化简成 tuple hash。同套路：LC 356 Line Reflection (轴对称)、LC 1453 Maximum Points on Circle、Steiner Point 类几何题。

> [!followup]
> "100k 个点？" → O(N²) 难避免，但可以用 Hough Transform 估计概率最大线 (近似)；"3D 点 (x,y,z)？" → 用 (dx,dy,dz) 化简三元 tuple；"求最大共圆点？" → LC 1453，不同方法；"如果允许 ε 内共线（近似）？" → KD-tree + 容差比较。
