## 题目本质

**LC 253 Meeting Rooms II**：给一组会议 `[(start, end), ...]`，求最少需要几间会议室才能让所有会议都开（不冲突）。

经典 **"最多并发区间数"** 题。OpenAI Senior 级，1 人报告。

## 解题思路（两种主流解法）

### 方法 A：扫描线（Sweep Line / Chronological Sort）⭐

把所有事件按时间排序：start 是 +1（需要一间），end 是 -1（释放一间）。扫一遍维护当前并发数，最大值就是答案。

```python
def minMeetingRooms(intervals: list[list[int]]) -> int:
    events = []
    for s, e in intervals:
        events.append((s, +1))
        events.append((e, -1))
    # 注意：同一时刻 end 事件应在 start 之前处理（10 点结束 = 10 点开始不冲突）
    events.sort(key=lambda x: (x[0], x[1]))
    rooms = 0
    max_rooms = 0
    for _, delta in events:
        rooms += delta
        max_rooms = max(max_rooms, rooms)
    return max_rooms
```

**关键**：tie-breaker 让 end 先于 start —— `delta = -1 < +1` 所以 `(time, -1)` 在 `(time, +1)` 前。

### 方法 B：min-heap（按结束时间）⭐

按 start 排序遍历会议。维护一个 min-heap，存"当前正在用的会议室的结束时间"。

每个新会议：
- 看堆顶（最早结束的房间）：如果其 end ≤ 新会议 start → 这间房可复用，pop + push 新 end
- 否则 → 需新房，push 新 end

```python
import heapq

def minMeetingRooms(intervals):
    if not intervals: return 0
    intervals.sort(key=lambda x: x[0])  # 按 start 升序
    heap = []   # 存正在用的房间的 end times
    for s, e in intervals:
        if heap and heap[0] <= s:
            heapq.heappop(heap)
        heapq.heappush(heap, e)
    return len(heap)
```

## 复杂度

- 两种方法都是 **O(N log N)**（sort 主导）
- 空间 O(N)

## 哪种方法更好？

| 维度 | 扫描线 | min-heap |
|---|---|---|
| 直觉 | "每个时刻有几个会议正在开" | "维护可复用的房间池" |
| 实现 | 略短 | 略复杂 |
| 扩展 | 容易加权（不同 start/end 影响）| 直接套区间贪心模板 |
| 适合的变种 | "求每个时刻并发数曲线" | "找最早结束的资源" |

面试两个都掌握。**扫描线**通常更优雅。

## 关键边界：`end == start` 算不算冲突？

题目通常**不算**（10:00 结束 = 10:00 另一会议开始可以）。所以：
- 扫描线：tie-break 让 end 先于 start
- min-heap：`heap[0] <= s` 用 `<=` 而非 `<`

如果题面 "endpoint 闭区间" 则改成严格冲突。

## 变种 1：LC 252 Meeting Rooms

> "是否能用一间房开完所有会议"

```python
def canAttendMeetings(intervals):
    intervals.sort(key=lambda x: x[0])
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i-1][1]:
            return False
    return True
```

## 变种 2：返回每个房间排期

不只是数量，要列出哪间房开哪些会议。

```python
def assignMeetingRooms(intervals):
    intervals = sorted(enumerate(intervals), key=lambda x: x[1][0])
    rooms = []  # rooms[i] = list of meeting indices
    heap = []   # (end_time, room_id)
    for orig_idx, (s, e) in intervals:
        if heap and heap[0][0] <= s:
            end, rid = heapq.heappop(heap)
            rooms[rid].append(orig_idx)
            heapq.heappush(heap, (e, rid))
        else:
            rid = len(rooms)
            rooms.append([orig_idx])
            heapq.heappush(heap, (e, rid))
    return rooms
```

## 变种 3：每个会议室有不同容量

如果会议有 attendees 数，房间有 capacity —— 需要"最小容量满足"的房间。可用 sortedcontainers.SortedList。

## 边界 case

```python
assert minMeetingRooms([]) == 0
assert minMeetingRooms([[0, 30]]) == 1
assert minMeetingRooms([[0, 30], [5, 10], [15, 20]]) == 2
assert minMeetingRooms([[7, 10], [2, 4]]) == 1
# 不重叠（端点接触）
assert minMeetingRooms([[1, 5], [5, 10], [10, 15]]) == 1
```

## 易错点

> [!pitfall]
> ❌ 扫描线 sort 时 tie-break 忽略，end == start 时 +1/-1 顺序错 —— 算多 1 间；
> ❌ min-heap 比较用 `<` 而非 `<=` —— 端点接触算冲突；
> ❌ 没 sort 直接扫 —— 错；
> ❌ 用 brute force `for t in range(0, MAX)` 数并发 —— 时间太大时 TLE。

> [!key]
> "最多并发区间" 类题的两个标准解法：(1) 扫描线 + 排序事件；(2) 按 start 排序 + min-heap by end time。前者更通用（适合"任意时刻并发"），后者更直观（房间复用）。

> [!followup]
> "返回每个时刻的并发数？" → 扫描线累计 prefix；"如果会议室有不同 type（普通 / VIP）？" → per-type 独立 heap，分配时按优先级；"如果是 calendar UI 实时分配？" → 每来新会议 O(log N) heap 操作，可保证实时性。
