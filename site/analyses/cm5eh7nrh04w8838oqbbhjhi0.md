## 题目本质

**LC 332 Reconstruct Itinerary**：给一组航班 `[from, to]`，重建从 "JFK" 出发能用完所有 ticket 的行程。**字典序最小**的合法行程。

经典 **Euler Path** 题。

## 解题思路

把 ticket 看作有向边，找 Eulerian path（每边遍历一次）从 "JFK" 出发。

**Hierholzer 算法**：DFS，每次取字典序最小的下一站；DFS 完后回栈时记录。

## Python 实现

```python
import heapq
from collections import defaultdict
from typing import List

class Solution:
    def findItinerary(self, tickets: List[List[str]]) -> List[str]:
        # adj[u] = min-heap of destinations
        adj: dict[str, list[str]] = defaultdict(list)
        for u, v in tickets:
            heapq.heappush(adj[u], v)

        route: list[str] = []
        def dfs(u: str):
            while adj[u]:
                v = heapq.heappop(adj[u])
                dfs(v)
            route.append(u)

        dfs("JFK")
        return route[::-1]
```

## 复杂度

- 时间：**O(E log E)**，E = ticket 数（每边 push/pop heap）
- 空间：O(E + V)

## 关键技术点

### 1. 为什么后序 append + reverse

Hierholzer 算法核心：DFS 走完一条 cycle 后回退；后续走另一 cycle 时把节点 prepend 进当前 path。

实现 trick：用**后序 visit**（DFS 完所有出边后 append），最终 reverse 就是正序 Euler path。

### 2. 字典序最小

每个节点的 outgoing edges 按字典序排序（用 min-heap 自动维护）。DFS 时先走字典序小的。

### 3. 为什么会终止

Eulerian path 存在条件：起点 out_degree - in_degree = 1（或 0），终点 in - out = 1，其他相等。题目保证存在。

### 4. DFS 死路 vs 真正终点

Hierholzer 妙处：即使 DFS 走到死路（无出边），那个节点也是 valid path 的**终点**。它会先被 append 到 route。然后回退到上层继续走其他 cycle，新 cycle 的节点会被 append 在它之后（但因为最后 reverse，会出现在它之前 → 正确顺序）。

## 边界 case

```python
sol = Solution()
assert sol.findItinerary([["MUC","LHR"],["JFK","MUC"],["SFO","SJC"],["LHR","SFO"]]) == \
    ["JFK","MUC","LHR","SFO","SJC"]
assert sol.findItinerary([["JFK","SFO"],["JFK","ATL"],["SFO","ATL"],["ATL","JFK"],["ATL","SFO"]]) == \
    ["JFK","ATL","JFK","SFO","ATL","SFO"]
```

## 易错点

> [!pitfall]
> ❌ 直接 DFS 字典序贪心 → 可能走死路漏边；
> ❌ 用 list 而非 heap → 排序成本 O(E log E) 多次；
> ❌ Recursion depth：E 大时 Python 默认栈 1000 不够，需要 `sys.setrecursionlimit`；
> ❌ 写成 BFS —— Eulerian path 必须 DFS；
> ❌ 起点不是 "JFK" —— 题目固定 JFK。

> [!key]
> Euler path / Hierholzer 算法是图论经典。**核心 trick：后序 append + reverse**。这套思路也用于：DAG topo sort 的某些变种、画线游戏（不重复走边）、邮路问题。

> [!followup]
> "找 Euler circuit (起点 = 终点)？" → in_deg == out_deg for all nodes；同 Hierholzer；"DAG topological sort？" → 改成入度归零的 BFS (Kahn)；"如果 ticket 可能重复？" → adj 用 multiset / heap 自然支持；"无解情况？" → 检查 in/out degree 条件。
