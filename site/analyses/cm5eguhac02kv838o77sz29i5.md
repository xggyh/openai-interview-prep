## 题目本质

**LC 737 Sentence Similarity II**：给一组单词对 `pairs[i] = [w1, w2]` 表示 w1 ≈ w2。相似性**传递**（w1≈w2 且 w2≈w3 → w1≈w3）。判断两个 sentence (word list) 是否相似（等长 + 各位置 word 相似）。

经典 **Union-Find**。

## Python 实现

```python
from typing import List

class UF:
    def __init__(self):
        self.parent: dict[str, str] = {}
    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

class Solution:
    def areSentencesSimilarTwo(self, s1: List[str], s2: List[str],
                               pairs: List[List[str]]) -> bool:
        if len(s1) != len(s2): return False
        uf = UF()
        for a, b in pairs:
            uf.union(a, b)
        for a, b in zip(s1, s2):
            if a == b: continue
            if a not in uf.parent or b not in uf.parent: return False
            if uf.find(a) != uf.find(b): return False
        return True
```

## 复杂度

- 建 UF: O(P × α(P))，P = pairs 数
- 检查 sentence: O(N × α(P))
- 总: ≈ O((P + N) × α(P))

## 关键技术点

### 1. Union-Find 处理传递闭包

直接建无向图 + DFS/BFS 找连通分量也可，但 UF 更优雅且支持增量加边。

### 2. 路径压缩 + 按秩合并

`find` 中递归把链上所有节点直接指向 root，下次 O(α(N))。

### 3. 处理未见单词

如果 sentence 里某 word 不在任何 pair 里，它只能和自身相似（不在 UF 里）。代码里 `a == b` 早返回；否则两个都得在 UF 且同 root。

### 4. 与 LC 734 (Sentence Similarity I) 区别

LC 734 不传递（直接查 pair 是否包含 (a, b) 或 (b, a)）。LC 737 传递 → 必须 UF / 连通分量。

## 易错点

> [!pitfall]
> ❌ 不用 UF 直接对 pair 列表做 N×P loop —— O(N×P) 慢；
> ❌ 误以为 pair 是有向 —— 题目相似性是对称的；
> ❌ Self-similar (a, a) 忘了 —— 任何 word 和自身相似（代码 `a == b` 优先返回）；
> ❌ 不在 UF 里的 word 直接 union(a, b) —— UF 应允许 setdefault；
> ❌ Length 不等 sentence 直接 union —— 应 return False。

> [!key]
> Union-Find 是"传递性等价关系"的标准武器。同模板：Friend Circles (LC 547)、Number of Provinces、Accounts Merge (LC 721)。

> [!followup]
> "动态加 pair？" → UF 增量 union，O(α) per call；"动态减 pair？" → UF 不支持 delete，需 offline 反向处理或 link-cut tree；"返回所有相似 group？" → DFS UF 收集每 root 的所有元素；"sentence 含 punctuation？" → tokenize 时去除。
