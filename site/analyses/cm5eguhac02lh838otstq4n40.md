## 题目本质

**LC 759 Employee Free Time**：N 个员工各自 schedule（list of busy intervals）。所有员工**共同空闲**的时间段（即没有任何人 busy 的时段）。返回排序的 free intervals。

## 解法

**Sweep line + min-heap**：所有 busy intervals 合并起来，找 gap。

### 方法 A：扁平化 + 合并

把所有员工的 intervals 拼成一个 list，按 start 排序，merge 重叠区间。剩下的 gap 就是 free time。

```python
from typing import List

class Interval:
    def __init__(self, start: int = 0, end: int = 0):
        self.start = start; self.end = end

class Solution:
    def employeeFreeTime(self, schedule: List[List[Interval]]) -> List[Interval]:
        all_iv = []
        for emp in schedule:
            for iv in emp:
                all_iv.append((iv.start, iv.end))
        all_iv.sort()
        merged = []
        for s, e in all_iv:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        # Gap between consecutive merged intervals
        free = []
        for i in range(1, len(merged)):
            if merged[i][0] > merged[i-1][1]:
                free.append(Interval(merged[i-1][1], merged[i][0]))
        return free
```

### 方法 B：min-heap（K-way merge，更优雅）

利用每个员工的 schedule 已**按 start 排序**这一前提（题目通常保证）。用 min-heap K-way merge。

```python
import heapq

class Solution:
    def employeeFreeTime(self, schedule: List[List[Interval]]) -> List[Interval]:
        heap = []  # (start, emp_idx, interval_idx)
        for i, emp in enumerate(schedule):
            if emp:
                heapq.heappush(heap, (emp[0].start, i, 0))
        free = []
        prev_end = None
        while heap:
            start, ei, ii = heapq.heappop(heap)
            iv = schedule[ei][ii]
            if prev_end is not None and start > prev_end:
                free.append(Interval(prev_end, start))
            prev_end = max(prev_end or 0, iv.end)
            if ii + 1 < len(schedule[ei]):
                nxt = schedule[ei][ii + 1]
                heapq.heappush(heap, (nxt.start, ei, ii + 1))
        return free
```

## 复杂度

- 方法 A：O(N log N)，N = 总 intervals
- 方法 B：O(N log K)，K = 员工数（heap size）

## 关键技术点

### 1. 利用 sorted-per-employee

如果每员工自己已排序，K-way merge 利用这点，整体只需 O(N log K)。

### 2. 合并重叠（gap > 0 才算 free）

`prev_end` 永远是已合并区间的右端点。只有新区间 start > prev_end 时才有 gap。

### 3. 边界

- 单员工：无 free time（除非他没 schedule，返回空）
- 完全无交集的员工：方法 A merge 后 = 各自原区间，gap 就是相邻空隙

## 易错点

> [!pitfall]
> ❌ 没合并重叠 —— 把重叠 interval 的"gap"误算成 free（实际仍 busy）；
> ❌ `prev_end = max(prev_end, iv.end)` 在 `prev_end == None` 时报错 —— 用 `or 0` 或 `if prev_end is None`；
> ❌ 用 list.append 后没排序 —— gap 检测错；方法 A 必须先 sort；
> ❌ 把 list of Interval 当成 list of [s,e]：题目用 Interval class，注意 attribute 访问。

> [!key]
> Interval 题三板斧：(1) 排序 + 单调扫；(2) min-heap K-way merge；(3) 扫描线 +1/-1。LC 759 是 (1)(2) 的混合。

> [!followup]
> "找所有员工都 free 的最长时段？" → 同样算 free，取 max length；"找 K 个员工 free 的时段（不要求全部）？" → 扫描线 + busy count <= N-K 时算 free；"动态 schedule 变更？" → SortedList / interval tree。
