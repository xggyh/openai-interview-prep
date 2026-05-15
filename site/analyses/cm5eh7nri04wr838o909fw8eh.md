## 题目本质

**LC 351 Android Unlock Patterns**：3×3 unlock pattern。求长度在 [m, n] 之间的合法 pattern 数。规则：
- 经过格子不能重复
- 两格之间如果有中间格子，必须**已访问过**（如 1→3 必须经过 2；除非 2 已访问，否则违反）

## 解法

DFS 回溯。利用对称性减少计算（4 角点等价、4 边等价、中心独特）。

## Python 实现

```python
class Solution:
    def numberOfPatterns(self, m: int, n: int) -> int:
        # Skip table：从 a 到 b 必经的中间点（如果不需经过则为 0）
        skip = [[0]*10 for _ in range(10)]
        skip[1][3] = skip[3][1] = 2
        skip[4][6] = skip[6][4] = 5
        skip[7][9] = skip[9][7] = 8
        skip[1][7] = skip[7][1] = 4
        skip[2][8] = skip[8][2] = 5
        skip[3][9] = skip[9][3] = 6
        skip[1][9] = skip[9][1] = 5
        skip[3][7] = skip[7][3] = 5

        visited = [False] * 10

        def dfs(cur: int, remaining: int) -> int:
            if remaining == 0:
                return 1
            count = 0
            visited[cur] = True
            for nxt in range(1, 10):
                if visited[nxt]: continue
                mid = skip[cur][nxt]
                if mid == 0 or visited[mid]:
                    count += dfs(nxt, remaining - 1)
            visited[cur] = False
            return count

        total = 0
        for length in range(m, n + 1):
            # 起点对称：1, 3, 7, 9 等价（×4）；2, 4, 6, 8 等价（×4）；5 独立
            total += dfs(1, length - 1) * 4
            total += dfs(2, length - 1) * 4
            total += dfs(5, length - 1)
        return total
```

## 复杂度

- 时间：**O(3 × 9!)**（3 个 anchor × 最长 9 长度回溯，但实际剪枝多）
- 空间：O(9) visited + 递归栈

## 关键技术点

### 1. Skip Table

某些点对之间有中间点 mandatory：直线 1-3 经过 2、对角 1-9 经过 5 等。预计算。

### 2. 对称性减少 5x 计算

3×3 格子里：
- 4 个角点（1, 3, 7, 9）等价 → 算 1 的结果 × 4
- 4 个边点（2, 4, 6, 8）等价 → 算 2 的结果 × 4
- 中心 5 独立 → 算 1 次

总 9 个起点 → 只算 3 次。

### 3. visited 回溯

进入 dfs(nxt) 前 mark cur；递归返回后 unmark（不是 nxt）。

### 4. mid 检查

`mid == 0`：直接相邻或无 mandatory；`visited[mid]`：中间点已访问，可跨过。

## 易错点

> [!pitfall]
> ❌ 没 skip table —— 把 1→3 这种"过 2"的 pattern 误算合法；
> ❌ DFS 标 nxt 但忘 unmark cur —— 错位；
> ❌ 对称性算错倍数 —— 4 角 4 边各自 ×4，5 是 ×1；
> ❌ DFS 累加但 remaining 计算错 —— 进入 dfs 时已访问 1 个点，所以 remaining 应是 "还需要选几个"。

> [!key]
> "对称性优化 + 回溯" 经典题。每次遇到对称 3x3 / 4x4 grid 都可以用 anchor 等价类减算。

> [!followup]
> "4x4 grid？" → skip table 扩展；对称性 8 个角 + 8 个边 + 4 个中心；"返回所有 pattern？" → DFS 记 path 而非 count；"两端可不连续？" → 改规则后 skip table 重算。
