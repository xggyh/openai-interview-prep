## 题目本质

**LC 1825 Finding MK Average**：实时数据流。`addElement(num)`：append。`calculateMKAverage()`：取最近 m 个数，移除最小 k 个和最大 k 个，剩 m - 2k 个数的平均（向下取整）；若 stream 未到 m，返回 -1。

经典 **三个 SortedList**（low / mid / high）维护。Hard。

## 解法

把最近 m 个数分三段：
- low: 最小 k 个
- mid: 中间 m - 2k 个
- high: 最大 k 个

`mk_sum` = mid 的和。`calculateMKAverage()` 返回 `mk_sum // (m - 2k)`。

添加新数 / 移除最旧数时调整三个 set 的 boundary 元素。用 **SortedList** (from `sortedcontainers`) 或 **TreeMap-like** 数据结构。

## Python 实现

```python
from sortedcontainers import SortedList
from collections import deque

class MKAverage:
    def __init__(self, m: int, k: int):
        self.m = m
        self.k = k
        self.mid_size = m - 2 * k
        self.low = SortedList()
        self.mid = SortedList()
        self.high = SortedList()
        self.mid_sum = 0
        self.queue: deque[int] = deque()

    def _add_to_buckets(self, x: int):
        # Insert x into proper bucket (low/mid/high)
        if not self.low or x <= self.low[-1]:
            self.low.add(x)
        elif not self.high or x < self.high[0]:
            self.mid.add(x)
            self.mid_sum += x
        else:
            self.high.add(x)
        # Rebalance: low must have exactly k (when full)
        # high must have exactly k
        self._rebalance()

    def _remove_from_buckets(self, x: int):
        if x in self.low:
            self.low.remove(x)
        elif x in self.mid:
            self.mid.remove(x)
            self.mid_sum -= x
        else:
            self.high.remove(x)
        self._rebalance()

    def _rebalance(self):
        if len(self.queue) < self.m:
            return
        # low overflow → 给 mid
        while len(self.low) > self.k:
            v = self.low.pop()
            self.mid.add(v)
            self.mid_sum += v
        while len(self.low) < self.k:
            v = self.mid.pop(0)
            self.low.add(v)
            self.mid_sum -= v
        # high overflow → mid
        while len(self.high) > self.k:
            v = self.high.pop(0)
            self.mid.add(v)
            self.mid_sum += v
        while len(self.high) < self.k:
            v = self.mid.pop()
            self.high.add(v)
            self.mid_sum -= v

    def addElement(self, num: int) -> None:
        self.queue.append(num)
        self._add_to_buckets(num)
        if len(self.queue) > self.m:
            old = self.queue.popleft()
            self._remove_from_buckets(old)

    def calculateMKAverage(self) -> int:
        if len(self.queue) < self.m:
            return -1
        return self.mid_sum // self.mid_size
```

## 复杂度

- `addElement`：**O(log m)** SortedList 操作
- `calculateMKAverage`：**O(1)**
- 空间：O(m)

## 关键技术点

### 1. 三段分治

low / mid / high 各自有 size 限制：low 和 high 各 k 个，mid 是 m - 2k 个。Rebalance 保持。

### 2. mid_sum 增量维护

不要每次重算 mid 总和。每次元素进出 mid 时 += / -= 。

### 3. SortedList O(log)

`sortedcontainers.SortedList` 提供 O(log n) 插入/删除/索引。Python 自带 `bisect` + list 是 O(n) 插入。

### 4. Edge: 还没到 m 个

`len(queue) < m` 时 calculate 返回 -1。

## 易错点

> [!pitfall]
> ❌ 每次 calculate 重新排序 m 个元素 —— O(m log m) per call，慢；
> ❌ 没维护 mid_sum 增量；
> ❌ Rebalance 漏了某种 case（low 不足，high 不足，mid overflow）；
> ❌ 删除元素时找不到 bucket —— 必须遍历或预先知道在哪个 bucket。

> [!key]
> 流式 top-K + sliding window 的复合：用三个有序结构维护"min k / mid / max k"。同思想：LC 480 Sliding Window Median (two heaps)、LC 295 Find Median from Data Stream。

> [!followup]
> "如果 m 很大（百万）？" → SortedList 仍 OK，但内存大；可用 BIT + 值域离散化；"动态调 m, k？" → 重建 buckets；"中位数代替 mean？" → 两 heap 即可。
