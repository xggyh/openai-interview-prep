## 题目本质

**LC 56 Merge Intervals**：给一组区间，合并所有重叠的，返回不重叠的区间列表。

经典中的经典。Google / Meta / Amazon 都常问。

## 解题思路

按 start 升序排序后，扫一遍：当前区间能和最后一个合并就合并（更新 end），不能就 push 新区间。

## Python 实现

```python
from typing import List

class Solution:
    def merge(self, intervals: List[List[int]]) -> List[List[int]]:
        if not intervals: return []
        intervals.sort(key=lambda x: x[0])
        merged = [intervals[0][:]]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return merged
```

## 复杂度

- 时间：**O(N log N)** 排序主导
- 空间：O(N) 输出

## 关键点

### 1. 排序按 start

按 start 升序后，对任何 (s,e) 来说：如果 `s <= 前一个的 end`，必合并；否则一定不重叠（因为后续 s 更大）。

### 2. `<=` 还是 `<`

题目"[1,4] and [4,5]" 通常合并为 `[1,5]`（端点接触算重叠）。所以 `<=`。少数变种用 `<`（端点接触不合并）。澄清！

### 3. 不修改输入

`intervals[0][:]` slice copy。否则更新 `merged[-1][1]` 会改原始数组。

## 边界 case

```python
sol = Solution()
assert sol.merge([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert sol.merge([[1,4],[4,5]]) == [[1,5]]
assert sol.merge([]) == []
assert sol.merge([[1,4],[2,3]]) == [[1,4]]   # 包含
assert sol.merge([[1,4],[0,4]]) == [[0,4]]
```

## 易错点

> [!pitfall]
> ❌ 按 end 排序而非 start —— 算法错；
> ❌ `merged[-1][1] = e` 直接覆盖而非 max —— 如果当前区间被前一个包含，结果错（例 `[1,5]+[2,3]` 应是 `[1,5]`，错算成 `[1,3]`）；
> ❌ 修改输入 intervals —— 调用方再用就坏；
> ❌ 没考虑空输入。

> [!key]
> 区间合并模板：**排序 + 单调扫**。同模板可解：插入区间、会议室、删除区间、覆盖问题。"按起点排序"是区间题第一步。

> [!followup]
> "实时插入新区间？" → 用 SortedList 维护，每次 O(log N) 找位置 + 合并；"求区间的并集长度？" → 合并后累加 (e-s)；"求覆盖一个点的所有区间？" → 扫描线 + active set；"区间求 max overlap？" → 扫描线 +1/-1。
