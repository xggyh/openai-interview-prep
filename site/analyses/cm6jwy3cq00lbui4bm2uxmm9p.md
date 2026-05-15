## 题目本质

**Knapsack Problem Variations**：两个变种：
1. **小数 weights** (最多 2 位小数)，item 不能拆分
2. **二元 profits** (每 item profit ∈ {1, 2})

## 解法

### 变种 1：小数 weights

把 weight × 100 转整数，capacity × 100 转整数。然后标准 0/1 knapsack。

```python
def knapsack_fractional_weights(items: list[tuple[float, int]], capacity: float):
    """items = [(weight, profit)], weight 是 0.01 精度"""
    items_int = [(int(w * 100 + 0.5), p) for w, p in items]
    cap_int = int(capacity * 100 + 0.5)
    n = len(items_int)
    dp = [0] * (cap_int + 1)
    for w, p in items_int:
        for j in range(cap_int, w - 1, -1):
            dp[j] = max(dp[j], dp[j - w] + p)
    return dp[cap_int]
```

复杂度 O(N × capacity × 100)。当 capacity 大时 (×100 放大) 可能 TLE。

### 变种 2：profit ∈ {1, 2}

经典 0/1 knapsack：

```python
def knapsack_binary_profit(items: list[tuple[int, int]], capacity: int):
    """items = [(weight, profit)], profit 是 1 或 2"""
    dp = [0] * (capacity + 1)
    for w, p in items:
        for j in range(capacity, w - 1, -1):
            dp[j] = max(dp[j], dp[j - w] + p)
    return dp[capacity]
```

**或者**：因为 profit 只有 1 或 2，可分组：先把 profit=2 的全部排序按 weight 升序贪心装，再用剩余 capacity 装 profit=1 的。

```python
def knapsack_optimized(items, capacity):
    p2 = sorted([w for w, p in items if p == 2])
    p1 = sorted([w for w, p in items if p == 1])
    total = 0
    cap = capacity
    # 先装 profit=2 的最轻几个
    for w in p2:
        if cap >= w:
            cap -= w
            total += 2
        else:
            break
    # 剩余装 profit=1 的
    for w in p1:
        if cap >= w:
            cap -= w
            total += 1
        else:
            break
    return total
```

**但贪心不一定最优**！考虑：profit=2 weight=10 vs profit=1 weight=2，capacity=10 时贪心选 profit=2 得 2，但选 5 个 profit=1 weight=2 也是 5 分。所以**简单贪心错**。

正确做法仍是 DP。

## 复杂度

- 变种 1：O(N × cap × 100)
- 变种 2：O(N × cap)

## 关键技术点

### 1. 小数 weights 必须 ×100 整数化

DP 索引必须整数。0.01 精度的 weight 用 *100 转 int。

### 2. profit 二元也不能贪心

直觉：profit=2 优先 = 错的（如上面 counterexample）。**必须 DP**。

### 3. 一维 DP 倒序

`for j in range(cap, w-1, -1)`：每 item 用一次。

## 易错点

> [!pitfall]
> ❌ 直接用浮点 weight 做 DP —— 索引非整数；
> ❌ 浮点转 int 不加 0.5 四舍五入 —— `int(0.299)` = 0 而非 0.3 → 29 而非 30；
> ❌ profit=2 全装贪心 —— 错（上面反例）；
> ❌ 一维 DP 正序 → 完全背包（不限制 1 次）。

> [!key]
> Knapsack 变种的核心永远是 0/1 DP。"浮点变整" 和 "profit 二元贪心" 都是迷惑性 distractor。除非有强单调性证明，否则不要尝试贪心。

> [!followup]
> "每 item 可重复（无限）？" → 完全背包（一维 DP 正序）；"分组 knapsack？" → 每组选最多 1 个；"K 维约束（weight + volume）？" → 多维 DP O(N × cap_w × cap_v)。
