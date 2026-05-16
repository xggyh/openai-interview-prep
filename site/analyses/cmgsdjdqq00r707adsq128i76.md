## 题目本质

设计 **Elevator Control System**：建筑里 N 个 elevator，handle floor request 调度让乘客等待 / 行程时间最小。

经典 LLD / 实时调度问题。

## 需求

- 1 建筑 4-16 elevators
- 50 floors
- < 30s avg wait time
- 高峰 + 闲时调度不同

## 设计

### 1. Request types

- **Hall call**: 楼层按按钮 (up / down)
- **Cab call**: 在 elevator 内按目标楼层

Hall call = 需要 elevator 服务这一层。Cab call = 该 elevator 必须停这层。

### 2. State per elevator

```python
@dataclass
class Elevator:
    id: int
    current_floor: int
    direction: 'up' | 'down' | 'idle'
    door_state: 'open' | 'closed'
    stops: set[int]            # 计划停的 floor
    capacity: int
    occupied: int
```

### 3. 调度算法

**经典 SCAN (LOOK)**：每 elevator 朝一方向走到 last stop 在那个方向，反向。新 request 加进 stops，按方向插入。

**Smart dispatching for N elevators**:

```python
def assign_hall_call(floor, direction, elevators):
    best, best_cost = None, float('inf')
    for e in elevators:
        cost = estimate_pickup_time(e, floor, direction)
        if cost < best_cost:
            best_cost = cost
            best = e
    best.stops.add(floor)
    return best

def estimate_pickup_time(elev, floor, direction):
    if elev.direction == 'idle':
        return abs(elev.current_floor - floor) * SECONDS_PER_FLOOR
    if elev.direction == 'up' and elev.current_floor < floor and direction == 'up':
        # 同向，路上
        return (floor - elev.current_floor) * SECONDS_PER_FLOOR + len(elev.stops) * STOP_TIME
    if elev.direction == 'down' and elev.current_floor > floor and direction == 'down':
        return (elev.current_floor - floor) * SECONDS_PER_FLOOR + len(elev.stops) * STOP_TIME
    # 反向，要先走完当前方向再回头
    if elev.direction == 'up':
        max_up = max(elev.stops or {elev.current_floor})
        return (max_up - elev.current_floor + max_up - floor) * SECONDS_PER_FLOOR + ...
    ...
```

### 4. Idle 策略

闲时 elevators 不能都停 1F。Idle distribution：
- Off-hours: 平均散在不同 floor
- High-rise building: 2 个停 1F（人员入口），其他停中间 floor
- Learning: 基于 historical pattern (8AM 上班高峰多 1F 起)

### 5. 高峰 mode

- Morning rush (8-9 AM)：大量"楼层 N → 1F"请求。Some elevators dedicated to 主电梯入口 service。
- Lunch rush (12-1 PM)：双向流。
- Evening (5-6 PM)：相反 morning。

Schedule changes elevator policy。

### 6. Failure handling

电梯 stuck → trigger emergency call。Other elevators take over floor assignments。

### 7. Safety

- Door open detection during motion → emergency stop
- Capacity overflow alarm
- Fire mode: all return to 1F + lock

### 8. Smart features

- Destination dispatch (modern buildings): user 输入 destination floor before boarding → 系统分配电梯。Reduce stops + crowding。
- Smartphone calling for elevator via app
- Predict + pre-position based on calendar events

## OOP 设计

```python
class Elevator: state, move, open_door, ...
class ControlPanel: receive_call, ...
class Scheduler: assign_call(call, elevators)
class Building: floors, elevators, scheduler
```

策略模式：不同 scheduling algorithm (SCAN / nearest car / DCS) 实现统一 Strategy interface。

## 易错点

> [!pitfall]
> ❌ FCFS scheduling → low throughput；
> ❌ 单 elevator 拿所有 call → 其他 idle；
> ❌ 不区分 hall vs cab → 调度错误；
> ❌ Idle 全部停 1F → 上下班高峰差；
> ❌ 不实现 safety mode → 事故。

> [!key]
> 三大要点：(1) **SCAN/LOOK + multi-elevator dispatch**；(2) **Idle pre-positioning** 基于 time + pattern；(3) **State machine + safety overrides**。

> [!followup]
> "如何 simulate 测试调度算法？" → discrete event simulation；"ML-driven dispatch？" → user count 预测 + reinforcement learning；"Cross-tower elevators in skyscraper？" → multi-shaft 协调，express vs local。
