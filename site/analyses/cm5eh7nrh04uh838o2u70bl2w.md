## 题目本质

**LC 269 Alien Dictionary**：给一些**已按外星字典序排序**的单词。推断字母的顺序。如果有多个合法顺序返回任一；如果矛盾返回 ""。

经典**Topological Sort**。Hard 题，Google 高频。

## 解题思路

1. 比较相邻单词，找出**第一对不同字符** → 建有向边 `c1 → c2`（c1 在 c2 之前）
2. **拓扑排序**这张图 → 得字母顺序
3. 边界：如果 word1 是 word2 的前缀但 word1 比 word2 长（如 `["abc","ab"]`），矛盾，返回 ""

## Python 实现（Kahn 算法 BFS）

```python
from collections import defaultdict, deque
from typing import List

class Solution:
    def alienOrder(self, words: List[str]) -> str:
        # 1. 收集所有出现的字母
        in_deg = {c: 0 for w in words for c in w}
        adj = defaultdict(set)

        # 2. 比较相邻单词建边
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            # 找第一个不同字符
            min_len = min(len(w1), len(w2))
            found = False
            for k in range(min_len):
                if w1[k] != w2[k]:
                    if w2[k] not in adj[w1[k]]:
                        adj[w1[k]].add(w2[k])
                        in_deg[w2[k]] += 1
                    found = True
                    break
            if not found and len(w1) > len(w2):
                # w1 是 w2 + extra，违反字典序
                return ""

        # 3. Kahn BFS
        q = deque([c for c, d in in_deg.items() if d == 0])
        order = []
        while q:
            c = q.popleft()
            order.append(c)
            for nx in adj[c]:
                in_deg[nx] -= 1
                if in_deg[nx] == 0:
                    q.append(nx)

        if len(order) != len(in_deg):
            return ""   # 有环
        return "".join(order)
```

## 复杂度

- 时间：**O(C + N × L)**，C = 总字符数，N = 单词数，L = avg word length
- 空间：O(C + edges)

## 关键技术点

### 1. 只看相邻单词的第一个不同字符

字典序的定义就是这样：`abc < acd` ⟹ `b < c`，但**不能**推出 `a < c` 或 `c < d`。所以只取第一个不同。

### 2. 前缀冲突

`["abc", "ab"]` 中 ab 是 abc 的前缀但放后面，违反字典序 → 直接 ""。

### 3. 用 set 去重边

`adj[c1].add(c2)`：避免重复加边导致 in_degree 多算。如果用 list 加边，要先 `if c2 not in adj[c1]`。

### 4. 多解时随便返回一个

拓扑序不唯一。Kahn 算法的 BFS 顺序取决于初始 in_deg=0 队列的顺序。题目允许任一。

### 5. 环检测

最终 `order` 长度 != 总字符数 → 有未消解的依赖 → 环 → 返回 ""。

## 边界 case

```python
sol = Solution()
assert sol.alienOrder(["wrt","wrf","er","ett","rftt"]) == "wertf"
assert sol.alienOrder(["z","x"]) == "zx"
assert sol.alienOrder(["z","x","z"]) == ""   # 环 z->x->z
assert sol.alienOrder(["abc","ab"]) == ""    # 前缀违反
assert sol.alienOrder(["a"]) == "a"          # 单单词
```

## 易错点

> [!pitfall]
> ❌ 比较单词时找到第一个差异后没 break —— 推断更多没依据的关系；
> ❌ 没考虑前缀冲突 case；
> ❌ adj 用 list 重复 add edge —— in_deg 多算；
> ❌ in_deg 没初始化全部字母 —— 只在 words 里出现一次的字母漏掉；
> ❌ 拓扑排序时没检测环 —— 返回不完整 string；
> ❌ 直接对 `set(words)` 操作 —— 顺序丢失。

> [!key]
> 这是拓扑排序的经典应用。识别题型：**"给一组顺序约束推断全序"**。同模板：课程表 LC 207/210、任务调度 LC 1857。重点是**只从相邻对建第一个差异边**，不要过度推断。

> [!followup]
> "字母可包含数字 / 特殊符号？" → 把字符集泛化，逻辑不变；"返回所有合法序列？" → DFS 拓扑（回溯每个可选 root）；"动态增量加 word？" → 复杂；通常重新跑 topo；"如果 words 不一定按字典序？" → 给一组 partial-order 约束，回归普通 topo。
