## 题目本质

**LC 1534 Count Good Triplets**：给数组 arr 和阈值 a, b, c。求三元组 (i, j, k) 数量，满足 i<j<k 且 |arr[i]-arr[j]|<=a 且 |arr[j]-arr[k]|<=b 且 |arr[i]-arr[k]|<=c。

## 解法

N ≤ 100 → O(N³) 直接暴力。

## Python 实现

```python
from typing import List

class Solution:
    def countGoodTriplets(self, arr: List[int], a: int, b: int, c: int) -> int:
        n = len(arr)
        count = 0
        for i in range(n - 2):
            for j in range(i + 1, n - 1):
                if abs(arr[i] - arr[j]) > a: continue   # 提早剪枝
                for k in range(j + 1, n):
                    if abs(arr[j] - arr[k]) <= b and abs(arr[i] - arr[k]) <= c:
                        count += 1
        return count
```

## 复杂度

- 时间：**O(N³)**，最坏 1e6 操作
- 空间：O(1)

## 关键技术点

### 1. 早期剪枝

外层 i, j 检查第一个条件 |arr[i]-arr[j]| > a 时 continue，避免内层 k 浪费。

### 2. 小 N 优化无必要

LC 数据 n ≤ 100，1e6 直接过。生产场景大 N 用 prefix BIT 等优化但面试不期望。

## 进阶 O(N²) 优化（大 N）

固定 j。算 valid i 的集合 和 valid k 的集合：

```python
# 固定 j：
# valid i: |arr[i] - arr[j]| <= a, i < j
# valid k: |arr[j] - arr[k]| <= b, k > j

# 还需 |arr[i] - arr[k]| <= c

# 朴素 O(N) per (i, k) 组合 → 总 O(N²)
# 进阶：BIT 记 arr[i] 的频率分布，查 [arr[k]-c, arr[k]+c] 范围内 count
```

总 O(N² log V)，V = value range。LC 不需。

## 易错点

> [!pitfall]
> ❌ 顺序循环 i < j < k 写错为 0 ≤ i,j,k < n —— 重复 + 顺序错；
> ❌ 三条件用 `or` 而非 `and` —— 错；
> ❌ 范围 i, j 上限错（应 j < n-1，k < n）；
> ❌ a/b/c 是 ≤ 还是 < —— 题面是 ≤。

> [!key]
> 三重循环加剪枝是 N 小时的最简方案。要展示**剪枝意识**（外层不满足条件就 skip 内层）。

> [!followup]
> "K 元组（更高维）？" → 增加 loop 维度；"N=1e5？" → 优化：BIT/segment tree 维护 prefix count，按 j 扫并查区间；"加权三元组（满足条件的 sum）？" → 同 BIT 改求和。
