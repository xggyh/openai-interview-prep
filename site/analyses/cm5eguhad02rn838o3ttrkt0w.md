## 题目本质

**LC 981 Time Based Key-Value Store**：实现一个 KV store，每个 key 可以多次 set（带 timestamp），`get(key, ts)` 返回 `timestamp ≤ ts` 中**最大的那次** set 对应的值；不存在返回 ""。

题目保证：**同一 key 的 set 严格按时间戳递增**（这是关键约束）。

## 解题切入点

每个 key 维护一个 (ts, value) 列表。由于同 key set 是递增 ts，**列表天然有序**。

`get(key, t)`：在有序 ts 列表里二分找 `floor(t)` —— 最大的 `ts_i ≤ t`。

## Python 实现

```python
from bisect import bisect_right
from collections import defaultdict

class TimeMap:
    def __init__(self):
        # key -> list of (ts, value)，ts 升序
        self._store: dict[str, list[tuple[int, str]]] = defaultdict(list)

    def set(self, key: str, value: str, timestamp: int) -> None:
        # 题目保证 timestamp 严格递增，直接 append
        self._store[key].append((timestamp, value))

    def get(self, key: str, timestamp: int) -> str:
        arr = self._store.get(key)
        if not arr:
            return ""
        # bisect by ts；我们需要 max idx s.t. arr[idx].ts <= timestamp
        # bisect_right((timestamp, +inf)) - 1
        # Trick：构造 (timestamp, chr(255)) 让 bisect_right 把所有 ts==timestamp 的都视作 < target
        idx = bisect_right(arr, (timestamp, chr(255))) - 1
        if idx < 0:
            return ""
        return arr[idx][1]
```

**关键技巧**：`bisect_right` 在 tuple 上按字典序比较。`(timestamp, chr(255))` 让 bisect 把所有 (timestamp, anything) 都视为小于此 target（除非有更大 ts），减一就是 floor。

更清晰的写法是手写二分只比较 ts：

```python
def get(self, key, timestamp):
    arr = self._store.get(key, [])
    lo, hi = 0, len(arr) - 1
    res = ""
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid][0] <= timestamp:
            res = arr[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return res
```

## 复杂度

- `set`：**O(1)** 摊销（append）
- `get`：**O(log N)** 二分
- 空间：O(M)，M = 总 set 调用数

## 关键点

### 1. 为什么不用 dict + 直接查？

`{key: {ts: value}}` 嵌套 dict 直查 O(1)，但 `get(key, t)` 要找"≤ t 的最大 ts" → 必须排序 ts 集合或扫描，O(N) 每次 get。二分是必要的。

### 2. 为什么 set 严格递增不需要 insort？

如果 set 是乱序，每次 set 要 `bisect.insort_left(arr, (ts, val))`，O(N) 插入。题目保证递增 → 直接 append O(1)。

如果题目变成乱序 set：

```python
from bisect import insort
def set(self, key, value, timestamp):
    insort(self._store[key], (timestamp, value))
```

整体仍 O(log N) get + O(N) set。

### 3. 同时间戳多次 set？

题目"严格递增" → 每个 ts 只有一次 set。如果允许 same ts，按"后到的覆盖"或"全部记录" 处理需澄清。

### 4. 大规模优化

如果 N 极大（亿级），可以用：
- **跳表 (Skip List)** —— O(log N) 插入 + 查找
- **B+ Tree** —— 磁盘友好
- **LSM Tree** —— 高写场景

LC 用普通数组够了。

## 边界 case

```python
tm = TimeMap()
tm.set("foo", "bar", 1)
assert tm.get("foo", 1) == "bar"
assert tm.get("foo", 3) == "bar"      # 没 ts > 1 的，返回最近的 1
tm.set("foo", "bar2", 4)
assert tm.get("foo", 4) == "bar2"
assert tm.get("foo", 5) == "bar2"
assert tm.get("foo", 3) == "bar"      # ts=3 < 4，返回 ts=1 那次
assert tm.get("foo", 0) == ""         # 没有 ≤ 0 的
assert tm.get("bar", 100) == ""       # key 不存在
```

## 易错点

> [!pitfall]
> ❌ 用 `bisect.bisect_left` 返回的 idx 不调整 —— 算的是 "≥ target" 而不是 "≤ target"；
> ❌ `bisect_right((ts, val))` 之后忘了 `-1` —— 错位；
> ❌ 没处理 `key 不存在` 返回 ""；
> ❌ 假设 set 乱序时直接 append —— 列表无序，二分失效。

> [!key]
> Time-based KV 的核心：**有序 ts 数组 + 二分找 floor**。当题目保证 ts 递增可以直接 append；否则要 insort。这套模式还能解 LC 1146 Snapshot Array、Authentication Manager 等"按时间快照"题。

> [!followup]
> "如何分布式？" → 按 key hash 分 shard；同 key 仍在单 shard 内有序数组；"如何持久化？" → append-only log 顺序写 disk，启动时回放重建内存索引；"如何支持范围查询 (get all keys whose latest ts ≥ X)？" → 加一个 global ts 索引或秒级倒排索引。
