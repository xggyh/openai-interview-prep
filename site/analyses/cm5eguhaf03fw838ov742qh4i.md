## 题目本质

**LC 1854 Maximum Population Year**：给一组 `[birth, death)`（左闭右开）区间，求**人口最多的年份**；如果有多年并列，返回最早的。

经典**扫描线 / 差分数组**题。Google 喜欢这类"区间打点求峰值"。

## 解题思路

每条 `(b, d)` 视为：
- 年份 b：+1 人
- 年份 d：-1 人（注意 d 是 exclusive，d 那年这个人已经死了）

**差分数组**：在 `delta[b] += 1; delta[d] -= 1`，然后做前缀和，找最大值。

约束：年份范围 1950 ≤ year ≤ 2050 → 数组大小 101，超快。

## Python 实现

```python
from typing import List

class Solution:
    def maximumPopulation(self, logs: List[List[int]]) -> int:
        # delta[y] = 第 y 年人口净变化
        # 数组索引：1950 ↔ 0, 2050 ↔ 100
        delta = [0] * 101
        for b, d in logs:
            delta[b - 1950] += 1
            delta[d - 1950] -= 1
        max_pop = 0
        max_year = 1950
        cur = 0
        for i, v in enumerate(delta):
            cur += v
            if cur > max_pop:
                max_pop = cur
                max_year = 1950 + i
        return max_year
```

## 复杂度

- 时间：**O(N + Y)**，Y = 年份范围
- 空间：**O(Y)**

## 关键点

### 1. 区间半开半闭：death 是 exclusive

题目说 "died in year d" 但 "did not contribute to population in year d"。所以 `delta[d] -= 1` 正确（在 d 那年就减）。

### 2. 求最早 → 顺序扫描，严格大于才更新

`if cur > max_pop`（用 `>` 不是 `>=`），保证遇到平局保留最早的。

### 3. 简单的 O(N²) 暴力

```python
def maximumPopulation(logs):
    counts = {}
    for b, d in logs:
        for y in range(b, d):
            counts[y] = counts.get(y, 0) + 1
    return min(y for y in counts if counts[y] == max(counts.values()))
```

N=2000, 跨度 100 → 200k ops，过得了。但 **diff array 是 O(N+Y)** 永远更快。

## 易错点

> [!pitfall]
> ❌ `delta[d-1] -= 1` 错位：题目 d 是 exclusive，不需要再减 1；
> ❌ 用 `>=` 比较 → 返回更晚的年份；
> ❌ 数组大小 100 越界：年份 2050 → idx 100 → 数组 size 至少 101；
> ❌ 没考虑边界 b == d（生死同年）：题目保证 b < d，但若题面变种允许 b==d，要 skip 或正确处理。

> [!key]
> 差分数组（diff array）+ 前缀和是处理"区间贡献求峰值/任一时刻总量"的标准武器。同类题：航班统计 (LC 1109)、会议室 II 时序版、HR shift schedule 找最忙时段。

> [!followup]
> "年份范围无界？" → 用排序事件代替数组（参考 Meeting Rooms II 扫描线）；"求人口最少？" → 同样扫描，记 min；"求每年人口列表？" → 直接输出前缀和数组。
