## 题目本质

**Implement Restaurant Waitlist API** (LLD)：餐厅排队 API。客户加 waitlist → 系统 notify 何时 ready → 客户 confirm / no-show。

## 核心 API

```python
class WaitlistService:
    def join(restaurant_id, party_size, customer_phone) -> 'WaitlistEntry'
    def cancel(entry_id)
    def get_position(entry_id) -> int   # 我在第几位
    def get_eta(entry_id) -> int        # 预估分钟
    def notify_ready(entry_id)          # 餐厅告知 ready
    def confirm_seated(entry_id)        # 客户到达
    def mark_no_show(entry_id)
```

## 数据模型

```python
from dataclasses import dataclass
from enum import Enum

class EntryStatus(Enum):
    WAITING = 'waiting'
    READY_NOTIFIED = 'ready_notified'
    SEATED = 'seated'
    CANCELLED = 'cancelled'
    NO_SHOW = 'no_show'

@dataclass
class WaitlistEntry:
    id: UUID
    restaurant_id: UUID
    customer_phone: str
    party_size: int
    joined_at: datetime
    status: EntryStatus
    notified_at: datetime | None
    seated_at: datetime | None

@dataclass
class Restaurant:
    id: UUID
    name: str
    avg_table_time_min: int      # 平均 turn-over
    table_sizes: list[int]        # [2, 4, 6, 8] 不同 capacity
    available_tables: dict[int, int]   # size -> count available
```

## 核心实现

### 1. Join

```python
def join(self, restaurant_id, party_size, phone):
    entry = WaitlistEntry(
        id=uuid4(), restaurant_id=restaurant_id,
        party_size=party_size, customer_phone=phone,
        joined_at=now(), status=EntryStatus.WAITING,
        notified_at=None, seated_at=None
    )
    self.waitlist[restaurant_id].append(entry)
    self._save(entry)
    return entry
```

### 2. Position

```python
def get_position(self, entry_id):
    entry = self.entries[entry_id]
    queue = self.waitlist[entry.restaurant_id]
    # 同 party_size 或更小的（也能用同 table）算前面
    pos = 0
    for e in queue:
        if e.status != EntryStatus.WAITING:
            continue
        if e.id == entry_id:
            return pos
        if e.party_size <= entry.party_size:
            pos += 1
    return -1
```

### 3. ETA

ETA = position × avg_table_time_min × fudge_factor

简单。More accurate：历史 table turn-over by party_size。

### 4. Notify ready (餐厅 → 系统 → 客户)

```python
def notify_ready(self, entry_id):
    entry = self.entries[entry_id]
    if entry.status != EntryStatus.WAITING:
        raise StateError
    entry.status = EntryStatus.READY_NOTIFIED
    entry.notified_at = now()
    self._send_sms(entry.customer_phone,
                   f"Your table at {entry.restaurant.name} is ready!")
```

### 5. Confirm seated

```python
def confirm_seated(self, entry_id):
    entry = self.entries[entry_id]
    entry.status = EntryStatus.SEATED
    entry.seated_at = now()
    # remove from queue
    self.waitlist[entry.restaurant_id].remove(entry)
```

### 6. No-show timeout

If notify_ready 后 10 分钟没 seat → 自动 no_show + 通知下一位。

```python
def _check_no_shows(self):
    """周期 background job"""
    for entry in self.entries.values():
        if entry.status == EntryStatus.READY_NOTIFIED:
            if (now() - entry.notified_at).minutes > 10:
                entry.status = EntryStatus.NO_SHOW
                self._notify_next(entry.restaurant_id)
```

### 7. Table matching

不同 party_size 用不同 table。Restaurant 有 2/4/6/8-人桌。客户 4 人不一定要 6 人桌。算法：
- 先 try exact match (table_size == party_size)
- 否则 round up (smallest >= party_size)
- 大桌 capacity 浪费要考虑（4 人占 8 人桌不好）

## 优化 / 扩展

### Cross-restaurant

某 chain 多分店，客户可 join multiple → first ready wins。Cancel 其他。

### Notification channel

SMS / app push / 电话。Customer config preference。

### Reorder / priority

VIP 客户 priority skip queue（小心 fairness）。

### Re-estimate

每当 table seated / cancelled / no_show → recompute ETA for all waiting → optionally re-notify if ETA 大变。

## 并发 / 一致性

多餐厅 host 同时 confirm seated 同一 entry —— 用 row lock 或 optimistic concurrency check。

## 易错点

> [!pitfall]
> ❌ Position 不考虑 party_size mismatch → 错估；
> ❌ No-show 不 timeout → 占位永久；
> ❌ Notify 通知发了 immediate seat 假设 → user 在外面不知道；要 ETA 通知；
> ❌ Cancel 不 cleanup → queue 含 cancelled entries；
> ❌ 不 handle race（两 host 同时 seat 同 entry）。

> [!key]
> Restaurant waitlist 看起来简单实有细节：(1) party_size + table size 匹配；(2) no-show timeout；(3) concurrent race；(4) ETA estimation。**OOP + state machine** 是关键。

> [!followup]
> "如何分析 average wait time per restaurant？" → audit log + dashboard；"加 walk-in priority over reservation？" → reservation 单独 table pool；"客户离开自动 cancel？" → geo-fence detect 客户离餐厅 > 1km；"如何 prevent fake join (no-show repeat)？" → 黑名单 / 押金。
