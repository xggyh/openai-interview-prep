## 题目本质

**LC 2162 Minimum Cost to Set Cooking Time**：微波炉只接受 4 位数字。要设定一个时间（秒数 targetSeconds）。**输入方式**：分别按数字键，最多 4 位组成 `mmss` 或更短。`mm × 60 + ss = targetSeconds`。每按一次键有成本：
- 移动到新数字成本 `moveCost`
- 按下数字成本 `pushCost`

从初始位置（startAt 数字）开始。求最小总成本。

## 解法

枚举两种合法的 (mm, ss) 组合：
- (target // 60, target % 60)
- (target // 60 - 1, target % 60 + 60)（当 ss < 100 且 mm > 0 时也是合法表示，可能更便宜）

`mm` 必须 ≤ 99，`ss` 必须 ≤ 99。对每组合法 (mm, ss)，构造 4 位字符串（去前导 0）算成本。

## Python 实现

```python
class Solution:
    def minCostSetTime(self, startAt: int, moveCost: int, pushCost: int,
                       targetSeconds: int) -> int:
        def cost_of(mm: int, ss: int) -> int:
            if not (0 <= mm <= 99 and 0 <= ss <= 99):
                return float('inf')
            digits = []
            if mm > 0:
                digits.extend([mm // 10, mm % 10])
            digits.extend([ss // 10, ss % 10])
            # 去掉前导 0
            while digits and digits[0] == 0:
                digits.pop(0)
            cost = 0
            cur = startAt
            for d in digits:
                if d != cur:
                    cost += moveCost
                    cur = d
                cost += pushCost
            return cost

        mm, ss = divmod(targetSeconds, 60)
        cost1 = cost_of(mm, ss)
        cost2 = cost_of(mm - 1, ss + 60)
        return min(cost1, cost2)
```

## 复杂度

- 时间：**O(1)**（最多 4 位数字两组合）
- 空间：O(1)

## 关键技术点

### 1. 两种合法表示

`70 秒` = `0:70` (但 ss=70 合法吗？仍 ≤ 99，OK) = `1:10`。两个都可能，比较成本。

### 2. 前导 0 跳过

`mm = 0, ss = 5` → 输入 "5"（1 位），不是 "0005"。规则：mm == 0 时不输入 mm 那两位，且 ss 的高位 0 也可以省。

我代码先 push mm 两位（如果 mm>0），再 push ss 两位，最后剥掉前导 0。

### 3. 起点 startAt

第一个数字也需要算"是否需要 move"。如果第一位 != startAt，加 moveCost；按下加 pushCost。

### 4. 边界 mm = -1 或 ss > 99

`cost_of` 用 inf 排除非法。

## 易错点

> [!pitfall]
> ❌ 只考虑 (mm = target//60, ss = target%60) 一种 → 漏掉 (mm-1, ss+60) 可能更便宜；
> ❌ 不去前导 0 —— 输入 4 位永远，浪费 push；
> ❌ 没算起点 startAt 的初始 move 成本；
> ❌ mm > 99 时仍计算 → 输入超过 4 位非法。

> [!key]
> "枚举所有合法表示" + 模拟成本。同思路：表盘 / 按键代码生成、字典序最小输入序列。

> [!followup]
> "微波炉支持 ":99" 之外的 ss？" → 改约束；"5 位时间显示？" → 加 (hh, mm, ss) 维度；"成本与按键的物理距离相关？" → 改 moveCost 为函数 cost(from, to)。
