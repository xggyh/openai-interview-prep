## 题目本质

**Car Rental Optimization**：两个子问题：
1. 给一组 (entry_time, exit_time)，求**某一天最多同时存在多少辆车**
2. 给 N 辆车和一组租车请求 (pickup, return, request_id)，**用最少车辆**满足所有请求；返回每请求分配的车辆 ID

子问题 1 = 经典扫描线。子问题 2 = 区间染色 / interval graph coloring。

## 子问题 1：最大同时车数

扫描线 +1/-1，类似 Meeting Rooms II。

```python
def maxConcurrentCars(intervals):
    events = []
    for s, e in intervals:
        events.append((s, +1))
        events.append((e, -1))
    events.sort(key=lambda x: (x[0], x[1]))  # end 优先 -1
    cur = max_cnt = 0
    for _, d in events:
        cur += d
        max_cnt = max(max_cnt, cur)
    return max_cnt
```

## 子问题 2：最少车辆分配

经典**贪心 + min-heap**：

按 pickup 时间排序请求。维护"空闲车辆"min-heap (按下次可用时间)。每请求来到：
- 如果 heap 顶车辆 return_time ≤ 当前 pickup，复用它
- 否则分配新车

```python
import heapq
def assignCars(requests, N: int):
    # requests = [(pickup, return, id), ...]
    sorted_req = sorted(enumerate(requests), key=lambda x: x[1][0])
    free = []  # min-heap of (free_at, car_id)
    next_new_id = 0
    assignment: dict[int, int] = {}  # request_id -> car_id

    for orig_idx, (p, r, rid) in sorted_req:
        if free and free[0][0] <= p:
            _, car = heapq.heappop(free)
        else:
            if next_new_id >= N:
                assignment[rid] = -1  # 拒绝
                continue
            car = next_new_id
            next_new_id += 1
        assignment[rid] = car
        heapq.heappush(free, (r, car))
    return assignment
```

## 复杂度

- 子问题 1：O(N log N)
- 子问题 2：O(R log R)

## 关键技术点

### 1. 子问题 1：扫描线

事件按时间排序，tie-break 让 end (-1) 先于 start (+1)：因为 end == start 时车已离开，不算冲突。

### 2. 子问题 2：贪心 by pickup 时间

按 pickup 升序处理保证一旦能复用车就复用。"复用最早空闲的车" 用 min-heap 选 `free_at` 最小。

### 3. 与 LC 1854 / Meeting Rooms 关系

子问题 1 = LC 1854 Maximum Population Year 的连续版本。子问题 2 = LC 253 Meeting Rooms II 求最少房间 + 返回分配方案。

## 易错点

> [!pitfall]
> ❌ 事件 sort tie-break 错（start 先于 end → 算多 1 辆）；
> ❌ 子问题 2 heap 用 car_id 而非 return_time —— 选错 car；
> ❌ N 限制不检查 → 输出 car_id > N；
> ❌ 不维护原 request_id 顺序 → 输出乱序。

> [!key]
> Interval graph chromatic number = 最少颜色数 = 最大同时区间数。所以子问题 1 和子问题 2 答案相关：**最少车数 = 最大同时车数**（满足所有请求时）。

> [!followup]
> "返回每辆车的行程列表？" → 同贪心，维护 per-car schedule；"车有不同类型（SUV / sedan）？" → 多 heap，每类型一个；"取消请求？" → 重新分配 + 调整 heap；"实时数据流？" → online 算法，新请求来时 incremental。
