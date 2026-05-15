## 题目本质

**LC 755 Pour Water**：高度数组 `heights`，从 `pourIdx` 倒水 V 次。每滴水按规则：
1. 先尝试向左找最低点（位置严格递减直到第一个不更低的）
2. 找不到再向右
3. 都找不到就停在 pourIdx

更新 heights[那个位置] += 1。返回最终 heights。

## 解法

每滴水模拟。每滴 O(N) 扫描左右。总 **O(V × N)**。

V ≤ 100, N ≤ 100 → 10k 操作，绝对 OK。

## Python 实现

```python
from typing import List

class Solution:
    def pourWater(self, heights: List[int], V: int, K: int) -> List[int]:
        for _ in range(V):
            best = K
            # 向左找最低
            for i in range(K - 1, -1, -1):
                if heights[i] > heights[i + 1]:
                    break   # 上坡，停止扫描
                if heights[i] < heights[best]:
                    best = i
            if best != K:
                heights[best] += 1
                continue
            # 向右找最低
            for i in range(K + 1, len(heights)):
                if heights[i] > heights[i - 1]:
                    break
                if heights[i] < heights[best]:
                    best = i
            heights[best] += 1
        return heights
```

## 复杂度

- 时间：**O(V × N)**
- 空间：O(1) in-place

## 关键技术点

### 1. 必须先左后右

题目明确："first try to flow left, then right"。即使右边有同样低的点也优先选左。所以左侧扫到最低（如果有）就停。

### 2. 不能爬上坡

"水流到比它高的地方就停止" → 扫描中遇到 heights[i] > heights[i+1] 立即 break（向左扫时）。

### 3. 严格小于

只有当某位置严格低于当前 best（初始 = K）时才更新 best。否则 best 保持。这保证了"最左侧最低点"。

向左扫从 K-1 倒序到 0，遇到更低就更新 best。向右扫从 K+1 正序到 n-1，同样。

### 4. best 初始 = K

如果整张图都比 pourIdx 高，水留在 K。

## 边界 case

```python
sol = Solution()
assert sol.pourWater([2,1,1,2,1,2,2], 4, 3) == [2,2,2,3,2,2,2]
assert sol.pourWater([1,2,3,4], 2, 2) == [2,3,3,4]
assert sol.pourWater([3,1,3], 5, 1) == [4,4,4]
```

## 易错点

> [!pitfall]
> ❌ 向左扫一遇到更低就停（不继续找更低）—— 错。要扫到坡顶或边界才停；
> ❌ 用 `>=` 而非 `>` 判断"严格更低" —— 平地不更新 best，应保持最左；
> ❌ 先右后左 —— 违反题意；
> ❌ V 大 (1e6+) 直接 O(VN) TLE：可以用 monotonic stack 优化但 LC 数据不需要。

> [!key]
> 物理模拟题：仔细读题 +一步一步模拟。同模式：LC 42 Trapping Rain Water、LC 407 Trapping Rain Water II。

> [!followup]
> "V 极大？" → 模拟到稳态后剩余的水都堆 pourIdx；"二维 grid 倒水？" → LC 407，min-heap 从边界往里漫；"水流速度 / 蒸发？" → 加时间维。
