## 题目本质

**LC 2655 Find Maximal Uncovered Ranges**：给整数 `n`（数轴长度，[0, n-1]）和一组**已覆盖区间** `ranges = [[l1,r1],[l2,r2],...]`，求**未被覆盖的最大连续区间**列表（合并相邻、按起点排序）。

经典**区间合并 + 反向求空隙**。

## 解题思路

1. 把 `ranges` 按起点升序
2. **合并重叠区间** → 得到 disjoint covered intervals
3. 扫描合并后的覆盖区间，列出**相邻间隙** + **两端开头 / 结尾的空白**

## Python 实现

```python
from typing import List

class Solution:
    def findMaximalUncoveredRanges(self, n: int, ranges: List[List[int]]) -> List[List[int]]:
        if not ranges:
            return [[0, n - 1]]

        # 1. 按起点排序
        ranges.sort(key=lambda x: x[0])

        # 2. 合并重叠（或紧邻）区间
        merged = [ranges[0][:]]
        for l, r in ranges[1:]:
            last = merged[-1]
            if l <= last[1] + 1:    # 相邻也合并（1-2 + 3-4 -> 1-4）
                last[1] = max(last[1], r)
            else:
                merged.append([l, r])

        # 3. 找空隙 + 两端
        result = []
        if merged[0][0] > 0:
            result.append([0, merged[0][0] - 1])
        for i in range(1, len(merged)):
            prev_end = merged[i-1][1]
            cur_start = merged[i][0]
            if cur_start > prev_end + 1:
                result.append([prev_end + 1, cur_start - 1])
        if merged[-1][1] < n - 1:
            result.append([merged[-1][1] + 1, n - 1])
        return result
```

## 复杂度

- 排序：O(R log R)，R = ranges 长度
- 合并 + 扫描：O(R)
- 总：**O(R log R)**

## 关键技术点

### 1. 相邻区间也合并

`[1,2]` 和 `[3,4]` 之间 **没有未覆盖** 整数（数轴是整数）。所以合并条件用 `l <= last[1] + 1` 而不是 `l <= last[1]`。

如果题目区间是连续实数（不是整数），改用 `l <= last[1]`。

### 2. Edge: 全空

`ranges = []` → 整个 `[0, n-1]` 都未覆盖。

### 3. Edge: 完全覆盖

合并结果 = `[[0, n-1]]` → 三个 if 都不进，返回空列表。

### 4. 不要修改输入

`merged = [ranges[0][:]]` 用 slice copy，避免改用户传入的 list。

## 边界 case

```python
sol = Solution()
assert sol.findMaximalUncoveredRanges(10, []) == [[0, 9]]
assert sol.findMaximalUncoveredRanges(10, [[0, 9]]) == []
assert sol.findMaximalUncoveredRanges(10, [[2, 4], [6, 8]]) == [[0, 1], [5, 5], [9, 9]]
assert sol.findMaximalUncoveredRanges(5, [[1, 2], [3, 4]]) == [[0, 0]]   # 相邻合并
assert sol.findMaximalUncoveredRanges(10, [[0, 5], [3, 8]]) == [[9, 9]]
```

## 易错点

> [!pitfall]
> ❌ 没排序就合并 —— `[[3,5],[1,2]]` 直接合并漏掉先后；
> ❌ 整数轴用 `l <= last[1]` 而非 `+1` —— `[1,2],[3,4]` 错算成两段；
> ❌ 忘了两端开头 / 结尾的空白；
> ❌ 修改输入 `ranges` —— 调用方再用就坏；
> ❌ 用 set 存所有覆盖点 + 找差 —— n 大时 O(n) 内存爆。

> [!key]
> "区间合并 + 反向求 gap" 是这类题模板：先排序合并，再扫缝隙。同模板：LC 56 Merge Intervals、LC 57 Insert Interval、LC 252 Meeting Rooms、LC 763 Partition Labels（变种）。

> [!followup]
> "如果是 query 多次（n 个 ranges 来了走了）？" → 用 SortedList / interval tree 维护合并状态，每次 O(log N)；"如果数轴是 [L, R] 不是 [0, n-1]？" → 边界判断换成 L 和 R；"如果区间是实数（continuous）？" → 合并条件用 `<` 而非 `<=` 或 `+1` 视语义。
