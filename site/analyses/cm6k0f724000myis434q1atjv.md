## 题目本质

**File System Size Analysis and Reporting**：实现文件系统分析工具，支持：
1. 给一个 entity ID（文件/文件夹），返回其大小（文件夹=递归求和）
2. 给一个 folder URI，返回**该 folder 内（递归）**最大的 10 个文件
3. 返回 top-10 最大文件夹（按"该 folder 下**直接子文件**总大小"，**不递归**）

不是纯算法，是 **OOP 设计 + 树遍历 + heap top-k**。Google L4-L5 高频。

## 数据模型

```python
from dataclasses import dataclass, field

@dataclass
class Entity:
    id: str
    name: str
    parent_id: str | None
    is_folder: bool
    size_bytes: int = 0          # 文件用；文件夹忽略
    children_ids: list[str] = field(default_factory=list)   # 文件夹用

class FileSystem:
    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.root_id: str | None = None
```

## Python 实现

```python
import heapq
from typing import Callable

class FileAnalyzer:
    def __init__(self, fs: 'FileSystem'):
        self.fs = fs

    # ----- Task 1: entity size -----
    def size_of(self, entity_id: str) -> int:
        """文件夹递归求和；文件直接返回 size."""
        e = self.fs.entities[entity_id]
        if not e.is_folder:
            return e.size_bytes
        total = 0
        for cid in e.children_ids:
            total += self.size_of(cid)
        return total

    # ----- Task 2: top-10 largest files in folder (recursive) -----
    def top_n_files(self, folder_id: str, n: int = 10) -> list[Entity]:
        """min-heap size n 维护 top n files."""
        heap: list[tuple[int, str]] = []   # (size, file_id)
        def walk(eid: str):
            e = self.fs.entities[eid]
            if e.is_folder:
                for c in e.children_ids:
                    walk(c)
            else:
                if len(heap) < n:
                    heapq.heappush(heap, (e.size_bytes, eid))
                elif e.size_bytes > heap[0][0]:
                    heapq.heapreplace(heap, (e.size_bytes, eid))
        walk(folder_id)
        # 输出按大小降序
        return [self.fs.entities[fid] for _, fid in
                sorted(heap, key=lambda t: -t[0])]

    # ----- Task 3: top-10 largest folders by IMMEDIATE children size -----
    def top_n_folders_immediate(self, n: int = 10) -> list[Entity]:
        """对每个 folder：求其直接子 file 大小之和（不递归子文件夹）。"""
        heap: list[tuple[int, str]] = []
        for eid, e in self.fs.entities.items():
            if not e.is_folder:
                continue
            immediate_size = sum(
                self.fs.entities[c].size_bytes
                for c in e.children_ids
                if not self.fs.entities[c].is_folder
            )
            if len(heap) < n:
                heapq.heappush(heap, (immediate_size, eid))
            elif immediate_size > heap[0][0]:
                heapq.heapreplace(heap, (immediate_size, eid))
        return [self.fs.entities[fid] for _, fid in sorted(heap, key=lambda t: -t[0])]
```

## 关键设计点

### 1. Size 计算：递归 vs 缓存

每次重新算 `size_of` 是 O(子树 size)。如果频繁查询，缓存：

```python
class FileAnalyzer:
    def __init__(self, fs):
        self.fs = fs
        self._size_cache: dict[str, int] = {}
    def size_of(self, eid):
        if eid in self._size_cache:
            return self._size_cache[eid]
        # compute and cache
        ...
```

**缓存失效**：文件变化时（add/delete/update size），失效该节点 + 所有祖先。

### 2. Top-K vs Sort

用 **size-K min-heap** 而不是 sort-all-then-take-K：
- N 个文件 → sort O(N log N)
- heap → O(N log K)

K = 10, N = 1M → heap 比 sort 快 ~5x。

### 3. Task 3 的"immediate" 语义

题面强调"based on their **immediate** file contents" —— 不递归子文件夹。这是个考察点：是否仔细读题。

如果误以为递归，就和 Task 2 重复。

## 复杂度

| 操作 | 时间 |
|---|---|
| size_of (no cache) | O(子树 size) |
| size_of (cached) | O(1) 摊销 |
| top_n_files | O(N log K) |
| top_n_folders_immediate | O(F + total_files)（每文件夹遍历直接子文件 1 次） |

## 易错点

> [!pitfall]
> ❌ Task 3 误算成递归子树 size —— 题面 immediate；
> ❌ 没用 heap 而用 sort —— K 小时 5-10x 慢；
> ❌ 递归 size 没考虑文件夹空 —— 返回 0 OK 但要写清；
> ❌ Top-K 用 max-heap of size N 取 K —— 浪费空间；用 min-heap of size K；
> ❌ Cache 不在更新时失效 —— 后续查询数据陈旧。

> [!key]
> 文件系统遍历 + top-K 是 Google L4-L5 必问。重点是 OOP 数据模型（entity dict + parent/children pointers）+ heap 用法 + 缓存策略。读题时区分 "recursive" vs "immediate"。

> [!followup]
> "分布式文件系统怎么做？" → 用 path → node 路由，每 shard 维护自己文件夹元数据 + size 周期 rollup；"如何处理 100B 文件？" → 不放内存，用 mmap + 流式 walk；"如何并发更新 size？" → 读写锁 + 更新所有祖先。
