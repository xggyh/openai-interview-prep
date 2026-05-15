## 题目本质

**LC 2402 Meeting Rooms III**：n 个会议室（编号 0..n-1）。给一组会议 `[start, end]`。规则：
- 优先选**编号最小**的空闲房间
- 没空闲时，挑**最早结束**的房间排队等（会议被延后到那房间空闲）
- 多个房间同时空闲时优先编号小

返回**举办最多会议的房间编号**（并列返回编号最小）。

经典**双 heap**题。

## 解题思路

维护两个 heap：
1. `free_rooms`：min-heap of 编号，当前空闲房间
2. `busy_rooms`：min-heap of (end_time, room_id)，正在用的房间

排序 meetings 按 start。每个 meeting：
- 先把 `busy_rooms` 里 end_time ≤ start 的房间 pop 出来 push 到 free
- 如果 free 不空：取出最小编号；分配
- 否则：等最早结束的房间（end_time, id），新 meeting 延后到 end_time 开始，end_time += (orig_end - orig_start)

## Python 实现

```python
import heapq
from typing import List

class Solution:
    def mostBooked(self, n: int, meetings: List[List[int]]) -> int:
        meetings.sort(key=lambda x: x[0])
        free = list(range(n))     # min-heap of room ids
        heapq.heapify(free)
        busy = []                 # min-heap of (end_time, room_id)
        count = [0] * n           # count[r] = 房间 r 主持的会议数

        for s, e in meetings:
            duration = e - s
            # 1. 释放到 s 已结束的房间
            while busy and busy[0][0] <= s:
                _, rid = heapq.heappop(busy)
                heapq.heappush(free, rid)
            # 2. 分配
            if free:
                rid = heapq.heappop(free)
                heapq.heappush(busy, (e, rid))
                count[rid] += 1
            else:
                end_time, rid = heapq.heappop(busy)
                # 会议从 end_time 开始，延后 duration
                heapq.heappush(busy, (end_time + duration, rid))
                count[rid] += 1

        # 找 count 最大的房间编号（并列返回最小编号）
        max_count = max(count)
        return count.index(max_count)
```

## 复杂度

- 时间：**O((N + M) log N)**，M = meetings 数。每个 meeting heap 操作 log(N)。
- 空间：O(N)

## 关键技术点

### 1. 双 heap 设计

- `free`：min-heap by room_id —— 用于"找编号最小的空闲"
- `busy`：min-heap by end_time —— 用于"找最早结束的"，tie-break by room_id（heapq 比较 tuple 自然处理）

### 2. 延后会议

如果当前都 busy，新会议不是被丢弃，而是排队到"最早结束的房间"。新会议**延后 duration** 而非 hard time → end_time + duration。

例：meeting (4, 10) 来了但都 busy；最早结束是 (6, 3) → 这个 meeting 排队，从 t=6 开始，持续 (10-4)=6 → end = 6+6 = 12 → push (12, 3) 回 busy。

### 3. count 最大但编号最小

Python `list.index(value)` 找首个 max，自然是编号最小的。

### 4. 严格 `<=` 还是 `<`

题目 "if at time t one meeting ends and another starts at t, the one that ends has higher priority"。所以 `busy[0][0] <= s` 用 `<=`（end == start 算不冲突，房间已空）。

## 边界 case

```python
sol = Solution()
assert sol.mostBooked(2, [[0,10],[1,5],[2,7],[3,4]]) == 0
# room 0: (0,10)
# room 1: (1,5)
# at t=2, both busy. 等。最早结束 (5, 1)。meeting (2,7) duration=5, 排到 room 1, end=5+5=10.
# at t=3, both busy (room 0 to 10, room 1 to 10). meeting (3,4) duration=1, 最早 (10,0)（编号小），排到 0, end=10+1=11.
# count: [2, 2] -> index 0
assert sol.mostBooked(3, [[1,20],[2,10],[3,5],[4,9],[6,8]]) == 1
```

## 易错点

> [!pitfall]
> ❌ 延后会议时把 end 算成 max(s, busy_end) + duration（× 错，应是 busy_end + duration）；
> ❌ free heap 用 list 而非 heap —— pop 最小 O(N)；
> ❌ `busy[0][0] < s` 用 `<` 而非 `<=` —— 边界会议挤占；
> ❌ tie-break：用 (end_time, room_id) 自然处理；用 (end_time,) 单元素 tuple 会忽略 room_id 优先；
> ❌ 找 max count 用 reverse sort + 取首 —— 可能不是最小编号；用 `count.index(max(count))` 正确。

> [!key]
> "事件调度" 模式：双 heap（空闲池 + 忙队列）+ 按时间扫。同模板：医院床位调度、停车场分配、磁盘 IO 调度。Tie-break 设计是这类题的灵魂。

> [!followup]
> "如果不允许延后（超时丢弃）？" → free 空时直接 skip；"加 room 容量（人数）？" → 每 meeting 需要的房间 size，free heap 改为 SortedList by (capacity, room_id)；"取消会议？" → busy heap 需要 lazy delete（用 dict 标记 cancelled，pop 时 skip）。
