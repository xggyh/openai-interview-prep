## 题目本质

**Advent of Code Day 7 Variation** —— Advent of Code 2022 Day 7 是一个"模拟 Unix 文件系统"的经典题：给一组 shell 输出（`cd`、`ls`），重建目录树，然后求满足条件的目录大小。

OpenAI 报告 Senior 级，1 人。考点：**输入解析 + 树构建 + DFS 聚合**。

## 题目语义（标准版）

输入是终端 session log：

```
$ cd /
$ ls
dir a
14848514 b.txt
8504156 c.dat
dir d
$ cd a
$ ls
dir e
29116 f
...
$ cd ..
$ cd d
$ ls
4060174 j
...
```

任务：
1. **part 1**：找所有目录大小（递归含子目录）≤ 100000 的目录，求总和
2. **part 2**：根目录总用量 70_000_000 - X = available。需要至少 30_000_000 available。找最小那个删了就能腾出空间的目录的大小

变种可能是：求 max depth、求某 file 的完整路径、按大小排序、找重复 file 等。

## 解题思路

1. 解析 log：状态机 —— 当前位置 + 当前命令
2. 构建树：每个 dir 是节点，含 `files: list[(name, size)]` 和 `dirs: list[Dir]`
3. 计算 dir size：递归 DFS，每个节点 size = own files size + sum(child dirs size)
4. 用 size 排序 / 过滤完成 part 1 + part 2

## Python 实现

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Dir:
    name: str
    parent: Optional['Dir'] = None
    children: dict[str, 'Dir'] = field(default_factory=dict)
    files: dict[str, int] = field(default_factory=dict)

    def total_size(self) -> int:
        return sum(self.files.values()) + sum(c.total_size() for c in self.children.values())

    def walk(self):
        yield self
        for c in self.children.values():
            yield from c.walk()


def parse(log: str) -> Dir:
    root = Dir(name='/')
    cur = root
    for line in log.strip().splitlines():
        line = line.strip()
        if line.startswith('$ cd '):
            target = line[5:]
            if target == '/':
                cur = root
            elif target == '..':
                if cur.parent:
                    cur = cur.parent
                # else: already at root, ignore
            else:
                if target not in cur.children:
                    # 没见过的 dir，先建
                    cur.children[target] = Dir(name=target, parent=cur)
                cur = cur.children[target]
        elif line == '$ ls':
            pass  # 下面的非 $ 行都是 ls 输出
        elif line.startswith('dir '):
            name = line[4:]
            if name not in cur.children:
                cur.children[name] = Dir(name=name, parent=cur)
        else:
            # 形如 "12345 filename.ext"
            size_str, name = line.split(' ', 1)
            cur.files[name] = int(size_str)
    return root


# ----- Part 1 -----
def part1(root: Dir, threshold: int = 100_000) -> int:
    total = 0
    for d in root.walk():
        sz = d.total_size()
        if sz <= threshold:
            total += sz
    return total


# ----- Part 2 -----
def part2(root: Dir, disk: int = 70_000_000, needed: int = 30_000_000) -> int:
    used = root.total_size()
    free = disk - used
    must_free = needed - free
    candidates = [d.total_size() for d in root.walk() if d.total_size() >= must_free]
    return min(candidates)


# Demo
log = """\
$ cd /
$ ls
dir a
14848514 b.txt
8504156 c.dat
dir d
$ cd a
$ ls
dir e
29116 f
2557 g
62596 h.lst
$ cd e
$ ls
584 i
$ cd ..
$ cd ..
$ cd d
$ ls
4060174 j
8033020 d.log
5626152 d.ext
7214296 k
"""
root = parse(log)
print('part1:', part1(root))   # 95437
print('part2:', part2(root))   # 24933642
```

## 复杂度

- 解析 log: O(L)，L = log 行数
- DFS 求 size：当前实现每次 `total_size()` 都重算 O(N²)；可以**缓存（memoization）** 到 O(N)：

```python
def total_size_cached(self) -> int:
    if hasattr(self, '_cached_size'):
        return self._cached_size
    self._cached_size = sum(self.files.values()) + sum(c.total_size_cached() for c in self.children.values())
    return self._cached_size
```

或者**自下而上 post-order DFS** 一次遍历填好所有 size：

```python
def compute_sizes(d: Dir, sizes: dict):
    own = sum(d.files.values())
    sub = sum(compute_sizes(c, sizes) for c in d.children.values())
    sizes[id(d)] = own + sub
    return sizes[id(d)]
```

## 关键技术点

### 1. 状态机解析

`$ cd X` / `$ ls` / `dir X` / `<size> <name>` 四种行类型。`cur` 指针随 cd 移动。

### 2. cd .. 边界

如果 `cur` 已经是 root，再 `cd ..` 应该不动（或报错，按题意）。我代码里检查 `if cur.parent`。

### 3. 重复 ls

同一目录 ls 多次可能输出相同 entry。代码里 `if name not in cur.children` 避免重复建。

### 4. 文件 / 目录命名冲突

如果一个目录里既有文件 `foo` 又有 dir `foo` —— Advent of Code 数据集里没有，但要在 review 时确认。

## 易错点

> [!pitfall]
> ❌ 用 `dict[path_string, Dir]` 全局 flat 存目录 —— path 计算麻烦，重名 dir 在不同 path 下处理乱；用树形 + parent pointer 简洁；
> ❌ 解析 `cd ..` 没处理 root 边界 —— stack underflow；
> ❌ Part 1 重复算 size（递归内每个 child 又递归到 root）—— 复杂度 O(N²)；用 memoization 或 post-order；
> ❌ 把 size 算成 own files only —— part 1 part 2 都错。

> [!key]
> 三个工程练习点：(1) 输入解析做成 state machine 模式；(2) 树结构用 parent pointer 便于 cd ..；(3) 子树大小用 post-order DFS 一次算完。这种 "log → tree → aggregate" 模式很常见（log analyzer、build dependency 计算）。

> [!followup]
> "如果 log 是流式的（边读边解析）？" → state machine 不变，逐行处理；
> "如果文件可以 hard link 到多个 dir？" → 不再是树，是 DAG；size 用 visited set 避免重复算；
> "如何支持 symlink？" → 类似 `Unix Cd with Symbolic Link Resolution` 那题，加 symlink resolution + cycle detection；
> "如何找重复文件（同 hash 但不同 path）？" → 加 file hash 字段，按 hash group by。
