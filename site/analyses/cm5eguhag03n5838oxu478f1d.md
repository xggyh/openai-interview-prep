## 题目本质

**LC 2115 Find All Possible Recipes from Given Supplies**：给一组 recipes（每个 recipe 有 name + ingredients list）+ supplies 初始拥有的原料。Recipe 可作为其他 recipe 的原料。返回**最终能做出的所有 recipe**。

经典**拓扑排序**。

## 解题思路

把每个 ingredient → recipe 当作"依赖关系"。Recipe 是"能否做"取决于所有 ingredients 都满足（要么在 supplies，要么是已能做的 recipe）。

**Kahn 拓扑**：
1. 每 recipe 的 in_degree = ingredients 数（不算已在 supplies 的）
2. 构建反向图：ingredient → recipes that need it
3. 把 in_degree=0 的 recipe 入队
4. 出队时把它当做新 supply，更新 dependent recipes 的 in_degree
5. 收集所有出队的 recipe

## Python 实现

```python
from collections import defaultdict, deque
from typing import List

class Solution:
    def findAllRecipes(self, recipes: List[str], ingredients: List[List[str]],
                       supplies: List[str]) -> List[str]:
        # supplies set，O(1) 查
        have = set(supplies)
        # in_deg[recipe] = 还差多少 ingredient
        in_deg: dict[str, int] = {}
        # graph[ingredient] = list of recipes needing it
        graph: dict[str, list[str]] = defaultdict(list)
        for r, ings in zip(recipes, ingredients):
            need = 0
            for ing in ings:
                if ing in have:
                    continue   # 已有，不计入 in_deg
                graph[ing].append(r)
                need += 1
            in_deg[r] = need

        q = deque(r for r in recipes if in_deg[r] == 0)
        result = []
        while q:
            r = q.popleft()
            result.append(r)
            # r 现在也是 supply
            for next_r in graph[r]:
                in_deg[next_r] -= 1
                if in_deg[next_r] == 0:
                    q.append(next_r)
        return result
```

## 复杂度

- 时间：**O(R + E)**，R = recipes 数，E = 总 ingredient 引用次数
- 空间：O(R + E)

## 关键技术点

### 1. supplies 当初始

提前把 ingredients 中 already-in-supplies 的去掉，让 in_deg 只数"还差的"。

### 2. 反向图 ingredient → recipes

为了快速找"哪些 recipe 依赖此 ingredient"。

### 3. Recipe 完成后视为新 supply

`r` 出队后，所有 `graph[r]` 里的 recipe 的 in_deg 减 1。

### 4. 拓扑确保无循环

如果有 recipe 互相依赖（A 需 B，B 需 A），它们的 in_deg 永远 > 0，不被加入 result。这符合题意（这种 recipe 不能做出）。

### 5. 不要 import graphlib

stdlib `graphlib.TopologicalSorter` 适合通用拓扑但语义略不同（不允许循环 vs 这里允许"做不出来"）。Kahn 手写更清晰。

## 边界 case

```python
sol = Solution()
assert sorted(sol.findAllRecipes(
    ["bread"], [["yeast","flour"]], ["yeast","flour","corn"])) == ["bread"]

# 嵌套 recipe
assert sorted(sol.findAllRecipes(
    ["bread","sandwich"], [["yeast","flour"],["bread","meat"]],
    ["yeast","flour","meat"])) == ["bread","sandwich"]

# 循环依赖 → 都做不出
assert sol.findAllRecipes(
    ["a","b"], [["b"],["a"]], []) == []
```

## 易错点

> [!pitfall]
> ❌ 不预先排除 supplies 中已有 ingredient → in_deg 偏大永远到不了 0；
> ❌ 反向图建错（recipe→ingredient 而非 ingredient→recipe）；
> ❌ 循环依赖 case 没处理 —— Kahn 自然处理（不出队即可）；
> ❌ 同名 recipe 出现多次 —— 题目通常保证 unique；
> ❌ 用 DFS + memoization 也可以，但 Kahn 更简洁。

> [!key]
> 拓扑排序处理"依赖完成 → 解锁后续" 的标准模式。同模板：课程表 (LC 207/210)、Alien Dictionary (LC 269)、Task Scheduling (LC 1857)。

> [!followup]
> "返回每 recipe 的 ingredient 树？" → DFS 展开；"找所有需要 ingredient X 的 recipe？" → 反向 BFS；"如果 ingredient 有数量？" → 改为流量问题或 multiset；"如果 recipe 有优先级（先做某个）？" → 拓扑后按优先级排序输出。
