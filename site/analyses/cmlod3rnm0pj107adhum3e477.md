## 题目本质

实现一个 **token credit tracking service**：跟踪每个用户的 token 信用（充值、消费、退款），支持查询"用户在某个时间点的 token 余额"。

这是 OpenAI 自家计费系统的简化版 —— 每个 API 调用扣 token，账户余额需要按时刻可查（用于对账、客服争议、定价分析）。

虽然标的是 **Coding**，但本质是 **API 设计 + 数据结构（per-user 有序事件序列） + 二分查找**。

## 题目语义

需要支持：
- `add_credits(user_id, amount, ts)`：增加 token
- `consume(user_id, amount, ts)`：消费 token
- `get_balance(user_id, ts)`：返回 user_id 在 ts 时刻的余额
- 余额非负（消费超过余额时应拒绝或记 deficit）

## 解题思路

每个 user 维护一个**有序事件列表**：`[(ts, delta), ...]`。`delta` 正数为充值 / 负数为消费。

查询时：对事件列表二分找到 `ts` 之前的所有事件，前缀和就是余额。

**为什么不能直接 `balance += delta` 维护当前余额？** 因为题目要查"过去某时刻"的余额。需要保留全部历史。

**优化：前缀和数组**。每次插入事件时同步更新前缀和；查询变 O(log n)。

## Python 实现

```python
from bisect import bisect_right, insort
from collections import defaultdict
from dataclasses import dataclass

class TokenTracker:
    def __init__(self):
        # per-user: timestamps 升序数组 + cumulative balance 数组
        self._ts: dict[str, list[int]] = defaultdict(list)
        self._cum: dict[str, list[int]] = defaultdict(list)

    def _apply(self, user_id: str, ts: int, delta: int) -> int:
        """Insert one event. Returns the balance AT or AFTER this insertion."""
        ts_arr = self._ts[user_id]
        cum_arr = self._cum[user_id]
        # 找到 ts 应该插入的位置（按 ts 升序）
        i = bisect_right(ts_arr, ts)
        ts_arr.insert(i, ts)
        # 计算插入后的新前缀和
        prev = cum_arr[i - 1] if i > 0 else 0
        new_cum = prev + delta
        cum_arr.insert(i, new_cum)
        # 修正后面所有累计值
        for k in range(i + 1, len(cum_arr)):
            cum_arr[k] += delta
        return new_cum

    def add_credits(self, user_id: str, amount: int, ts: int):
        assert amount > 0
        self._apply(user_id, ts, +amount)

    def consume(self, user_id: str, amount: int, ts: int) -> bool:
        """Returns True if charged; False if insufficient balance at ts."""
        assert amount > 0
        bal = self.get_balance(user_id, ts)
        if bal < amount:
            return False
        self._apply(user_id, ts, -amount)
        return True

    def get_balance(self, user_id: str, ts: int) -> int:
        ts_arr = self._ts.get(user_id, [])
        cum_arr = self._cum.get(user_id, [])
        i = bisect_right(ts_arr, ts)  # 最大 idx s.t. ts_arr[idx] <= ts → i-1
        return cum_arr[i - 1] if i > 0 else 0
```

## 复杂度

- `get_balance`：**O(log n)** 二分
- `add_credits` / `consume`：**O(n)** 在最坏情况（插入位置之后所有 cum 都要更新）。如果事件**严格按时间顺序到达**（append-only），降为 **O(log n)**。
- 空间：O(n) per user

## 进阶优化（如果面试官追问）

如果支持任意时间点插入且 n 很大（百万级事件），**Fenwick Tree (Binary Indexed Tree)** / **Segment Tree** 可以把插入也降到 O(log n)。但需要先把所有可能的时间戳离散化（坐标压缩）。

```python
class TokenTrackerBIT:
    """Assumes timestamps come from a pre-known discrete set."""
    def __init__(self, all_ts: list[int]):
        self._idx = {t: i + 1 for i, t in enumerate(sorted(set(all_ts)))}  # 1-based
        self._tree = [0] * (len(self._idx) + 1)

    def _update(self, i: int, delta: int):
        while i < len(self._tree):
            self._tree[i] += delta
            i += i & -i

    def _query(self, i: int) -> int:
        s = 0
        while i > 0:
            s += self._tree[i]
            i -= i & -i
        return s

    def add(self, ts: int, delta: int):
        self._update(self._idx[ts], delta)

    def get_balance(self, ts: int) -> int:
        return self._query(self._idx[ts])
```

如果时间戳是连续递增（毫秒戳）需要先收集再离散化；或用动态开点的 segment tree。

## 边界 case

- 同一 ts 多个事件：`bisect_right` 把新事件放在已有等 ts 事件之后（合理：按到达顺序）；
- 查询 `ts` 小于第一个事件：返回 0；
- 用户从未出现：返回 0；
- 消费余额为 0：拒绝并返回 False；
- 负数 delta（退款）：在 `add_credits` 接口外，应该有独立的 `refund` 接口或允许 `add_credits` 接收负数（题面没明说，澄清）。

## 工业级延伸

如果是真生产系统：
- **持久化**：每个事件写入 append-only log（Kafka / ledger DB）
- **快照**：每天对每用户存一个"截止 EOD 的余额"快照，查询时找最近快照 + 增量重放
- **强一致**：相同用户的消费走单 partition，避免并发扣款超支
- **审计**：每条事件不可变（immutable），原始事件 + 修正事件 ≠ 修改原事件

> [!key]
> OpenAI 真的有这个系统！考点是**"按时刻查历史余额"** —— 不能用普通 KV 缓存当前余额了事。bisect / 前缀和是面试期望的解法；BIT 是 bonus。

> [!pitfall]
> ❌ 直接维护 `balance` 一个数字 —— 历史查不了；
> ❌ 用 list of (ts, balance_after) 但每次插入不修正后续累计值 —— 错位；
> ❌ 假设事件按时间到达 —— 题面没说；面试官最爱追"乱序到达怎么办"；
> ❌ 不澄清"负余额是否允许" —— 题面歧义点，先问。

> [!followup]
> "如何支持百万用户？" → 数据按 user_id sharding；每 shard 内仍是 per-user 列表。"如果要支持事务式 multi-user transfer？" → 引入两阶段提交 / Saga，确保 transfer 原子性。"如何防止 race condition？" → per-user 加锁（Redis SETNX）或用 DB 的 SERIALIZABLE 隔离级别。
