## 题目本质

**LC 733 Flood Fill**：网格的某像素 `(sr, sc)` 当前颜色 = X。把所有与之 **4 方向相连且也是颜色 X 的像素**改为 `newColor`。返回修改后网格。Easy 题但 Google 入门常考。

## 解题思路

DFS 或 BFS，从起点扩散，同色才继续。

## Python 实现（DFS）

```python
from typing import List

class Solution:
    def floodFill(self, image: List[List[int]], sr: int, sc: int, newColor: int) -> List[List[int]]:
        original = image[sr][sc]
        if original == newColor:
            return image   # 防死循环
        R, C = len(image), len(image[0])
        def dfs(r, c):
            if not (0 <= r < R and 0 <= c < C) or image[r][c] != original:
                return
            image[r][c] = newColor
            dfs(r-1, c); dfs(r+1, c); dfs(r, c-1); dfs(r, c+1)
        dfs(sr, sc)
        return image
```

## 复杂度

- 时间：**O(R × C)**，最坏整张图同色
- 空间：O(R × C) 递归栈

## 关键点

### 1. 防死循环

如果 `newColor == original`，DFS 永远见到"同色"继续递归 → 栈溢出。**第一行就返回**。

### 2. In-place vs new image

题目要求修改原图。代码直接改。如果要保留原图，先 `image = [row[:] for row in image]`。

### 3. 4 方向 vs 8 方向

题目是 4 方向。8 方向就加对角。

## 易错点

> [!pitfall]
> ❌ 没防死循环 newColor == original → 栈溢出；
> ❌ 边界 check 顺序错（先访问 image[r][c] 再 check 边界 → IndexError）；
> ❌ 用 BFS 但 visited 没标 — 重复入队；
> ❌ 把 image[sr][sc] 改了再读 original —— 读到 newColor。

> [!key]
> Flood fill 是连通分量染色的最简形式。同模板适用于：油漆桶工具、岛屿染色、地图染色游戏。

> [!followup]
> "返回受影响的 cell 数？" → DFS 累加；"如果只染色边界 cell？" → 先 DFS 标内部，再扫边界；"分多线程？" → 把图按区域切，跨区域时同步队列（实际收益低）；"GPU 加速？" → 用 union-find / paint algorithm；shader 像素并行染色。
