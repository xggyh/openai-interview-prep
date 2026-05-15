## 题目本质

**LC 223 Rectangle Area**：求两个矩形（轴对齐）的总覆盖面积（并集）。

## 解法

`总面积 = A + B - 交集`。交集用坐标相交公式。

## Python 实现

```python
class Solution:
    def computeArea(self, ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> int:
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        # 交集
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        overlap = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        return area_a + area_b - overlap
```

## 复杂度

- 时间：**O(1)**
- 空间：O(1)

## 关键点

### 1. 交集公式

两矩形交集左下角 = (max x1, max y1)，右上角 = (min x2, min y2)。若 width 或 height ≤ 0 表示不相交。

### 2. `max(0, ...)`

防止负数面积（无交集时）。

### 3. 不要算重复

A ∪ B = |A| + |B| - |A ∩ B|（容斥）。这是数学第一定理。

## 易错点

> [!pitfall]
> ❌ 算 overlap 时没 `max(0, ...)` —— 负数误算成"扣多"；
> ❌ 用 abs 替代 max(0, ...) —— 错；
> ❌ x1 < x2, y1 < y2 假设：题目保证；
> ❌ 整数溢出：Python 不会，Java/C++ 要用 long。

> [!key]
> 容斥原理 + 矩形几何。同模板：N 个矩形并集面积（扫描线 + 线段树）、点是否在矩形内、判断相交。

> [!followup]
> "N 个矩形并集？" → 扫描线 + 线段树（LC 850）；"如何只判相交不算面积？" → `ix2 > ix1 and iy2 > iy1`；"3D 立方体？" → 扩展 z 维；"如果矩形旋转？" → 不再轴对齐，要用 SAT (Separating Axis Theorem)。
