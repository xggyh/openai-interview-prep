## 题目本质

**LC 1279 Traffic Light Controlled Intersection**：模拟交叉路口的红绿灯。两条 road 交叉，灯有状态。车辆请求过路 (carId, road, direction)：if road's light is green pass else wait then switch light.

设计题 + concurrency。

## 解法

用一个**互斥锁 + 共享 light state**。当车要过：
- 如果当前 road 灯绿，过；
- 否则：上锁 → 切换灯 → 过 → 解锁。

```python
import threading

class TrafficLight:
    def __init__(self):
        self.green_road = 1   # initially road 1 is green
        self.lock = threading.Lock()

    def carArrived(self, carId: int, roadId: int, direction: int,
                   turnGreen, crossCar) -> None:
        with self.lock:
            if self.green_road != roadId:
                turnGreen()
                self.green_road = roadId
            crossCar()
```

## 复杂度

- 每车 O(1) + 锁开销
- 空间 O(1)

## 关键技术点

### 1. 临界区

`green_road` 是共享状态，多 thread 并发会 race。`Lock` 保证一次只有一辆车过 + 切灯原子。

### 2. 不要在锁内 sleep

`turnGreen` 和 `crossCar` 通常是即时操作（LC 框架内部）。如果它们慢，要释放锁后再做，但这道题不要求。

### 3. Re-entrant lock 不需要

每个 carArrived 调用是独立的，不嵌套。

### 4. 公平性？

题目不要求 FIFO；Python `Lock` 也不保证 fair。如果要 fair，用 `queue.Queue` 序列化请求。

## 易错点

> [!pitfall]
> ❌ 不加锁 —— race condition，两车同时切灯；
> ❌ 用 RLock 没必要，性能略差；
> ❌ 把 `green_road` 当 atomic 改而不锁 —— check-then-set 不 atomic；
> ❌ 死锁：忘了 with 语句释放。

> [!key]
> 并发控制基础：临界区 + Lock。同模式：LC 1114 Print in Order、LC 1115 Print FooBar Alternately、各种 producer-consumer。

> [!followup]
> "公平调度？" → 等待队列；"多路口？" → 每路口独立 Lock；"超时机制？" → `lock.acquire(timeout=...)` 或 condition variable；"分布式（多服务器多车）？" → 中心 lock service (Redis) 或 distributed consensus。
