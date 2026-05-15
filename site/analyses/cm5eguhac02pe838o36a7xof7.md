## 题目本质

**LC 900 RLE Iterator**：实现 Run-Length Encoded 迭代器。输入 `encoding = [count1, value1, count2, value2, ...]` 表示 `count1 个 value1 后跟 count2 个 value2 ...`。支持 `next(n)`：返回**第 n 个未消费的值**，并把这 n 个消费掉；如果不够返回 -1。

经典**指针 + 计数维护**题。

## 解题思路

维护两个状态：
- `idx`：当前处理到 encoding 的哪个 (count, value) pair（指向 count 那一位）
- `remaining`：当前 pair 还剩多少未消费

`next(n)`：
1. 如果当前 pair `remaining < n` → 消耗掉这个 pair，n -= remaining，跳到下个 pair
2. 否则 → remaining -= n，返回 encoding[idx + 1]
3. 跨多个 pair 时 loop 直到 n 被吃光或耗尽全部

## Python 实现

```python
from typing import List

class RLEIterator:
    def __init__(self, encoding: List[int]):
        self.enc = encoding
        self.i = 0   # idx into enc, points at a count
        # remaining 在 enc[i] 里直接修改

    def next(self, n: int) -> int:
        while self.i < len(self.enc) and self.enc[self.i] < n:
            n -= self.enc[self.i]
            self.i += 2          # 跳到下一对
        if self.i >= len(self.enc):
            return -1
        self.enc[self.i] -= n
        return self.enc[self.i + 1]
```

**注意**：我们直接 in-place 修改 `enc[i]` 表示剩余 count。这样不需要额外 `remaining` 变量。

## 复杂度

- `next(n)`：摊销 O(1)？不完全。最坏单次 `next` 可能跨整个 encoding，所以最坏 O(K)，K = encoding 长度。但**总操作所有 next 的累加 < O(K + total_n)** —— 每个 pair 最多被 "consume" 一次（即 i += 2 一次）。所以**摊销 O(1) per next**。
- 空间：O(K) 输入存储

## 关键技术点

### 1. 跨多 pair 的 next

n 可能超过当前 pair 剩余。例：`encoding = [3, 8, 0, 9, 2, 5]`, `next(2)` → 当前 pair 是 `3 个 8`，够，返回 8 剩 1。`next(1)` → 返回 8 剩 0。`next(1)` → 当前 pair 用完，跳到 `0 个 9`，仍然不够（n=1），再跳到 `2 个 5`，够，返回 5 剩 1。

### 2. `enc[i] -= n` 而非用变量

直接改 encoding 数组省一个状态。如果题目要求保持 encoding 不变，要复制或额外用 `remaining` 变量。

### 3. 不够时返回 -1

完整消费 encoding 所有元素后还有剩余 n → return -1。

## 边界 case

```python
it = RLEIterator([3, 8, 0, 9, 2, 5])
assert it.next(2) == 8
assert it.next(1) == 8
assert it.next(1) == 5
assert it.next(2) == -1    # 只剩 1 个 5，要 2 个 → 失败
# LC 题目说不够时仍消耗完，再次 next 应该接着继续；视题面而定
```

## 易错点

> [!pitfall]
> ❌ `next(n)` 不够时不消耗（保留 n）—— 题目通常仍要消耗剩余；
> ❌ 把 i 指向 value 而非 count —— 索引错位；
> ❌ 跨 pair 用 `<=` 而非 `<` —— off-by-one；
> ❌ enc 直接 modify 导致重新调用结果异常 —— 工业级要做 deep copy；
> ❌ 没考虑 count=0 的 pair —— 0 个 value 应跳过。

> [!key]
> "压缩数据迭代" 模式：维护一个 chunk 指针 + chunk 内 offset。同模式适用于：流式 buffer reader、video chunk player、按 page 读 DB。摊销分析是这题的关键 —— 单次最坏 O(K) 但总 O(K + N)。

> [!followup]
> "如何 seek（跳到第 X 个位置）？" → 加 prefix sum 二分；"反向迭代？" → 维护反向指针 + 反向 consumed；"修改某段 encoding 后保持迭代器有效？" → 复杂，可能需要重置或 invalidate；"如何支持 multi-thread？" → 加锁，或用 immutable RLE + 每 thread 自己游标。
