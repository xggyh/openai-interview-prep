## 题目本质

实现 Unix `cd` 命令的路径解析：支持**相对路径**（`.`、`..`）、**绝对路径**（`/foo/bar`）、**符号链接（symlink）**，并检测循环（symlink loop）。

经典系统编程题。OpenAI Senior-Staff 级。考点：**栈 + DFS + 状态管理**。

## 题目语义

```python
fs = FileSystem({
    '/home/user': ['docs', 'projects'],
    '/home/user/docs': [],
    '/var/log': [],
})
fs.create_symlink('/home/user/projects/code', '/var/log')
fs.create_symlink('/a', '/b')
fs.create_symlink('/b', '/a')   # cycle

cd = CDCommand(fs)
print(cd.resolve('/home/user/'))                     # '/home/user'
print(cd.resolve('/home/user/./../user/docs/'))      # '/home/user/docs'
print(cd.resolve('/home/user/projects/code'))        # '/var/log' (symlink resolved)
cd.resolve('/a')   # raises CycleError
```

## 解题思路

1. **绝对 vs 相对**：以 `/` 开头是绝对（从 root 开始）；否则相对当前目录
2. **栈处理 `.` / `..`**：把路径按 `/` 切，逐段处理 —— `.` 跳过；`..` pop 栈顶；普通名 push
3. **Symlink**：解析过程中遇到 symlink 就递归 resolve 其 target
4. **循环检测**：每次 resolve 一个 symlink 时把它加入 `visited` set；resolve 完成移除（DFS 标准做法）

## Python 实现

```python
from dataclasses import dataclass, field

class CycleError(Exception):
    pass

@dataclass
class FileSystem:
    """简化 FS：dirs 是 (path -> children) ，symlinks 是 (path -> target)"""
    dirs: dict[str, list[str]] = field(default_factory=dict)
    symlinks: dict[str, str] = field(default_factory=dict)

    def create_dir(self, path: str):
        self.dirs[path] = self.dirs.get(path, [])
        # 也保证父目录里登记 child name
        parent, _, name = path.rpartition('/')
        parent = parent or '/'
        if parent in self.dirs and name not in self.dirs[parent]:
            self.dirs[parent].append(name)

    def create_symlink(self, link_path: str, target_path: str):
        self.symlinks[link_path] = target_path

    def is_dir(self, path: str) -> bool:
        return path in self.dirs

    def is_symlink(self, path: str) -> bool:
        return path in self.symlinks


class CDCommand:
    """实现 cd 路径解析，含 symlink + cycle detection"""

    MAX_SYMLINK_DEPTH = 40   # POSIX 标准

    def __init__(self, fs: FileSystem, cwd: str = '/'):
        self.fs = fs
        self.cwd = cwd

    def resolve(self, path: str) -> str:
        """返回解析后的绝对路径"""
        return self._resolve_path(path, depth=0, visited=set())

    def _resolve_path(self, path: str, depth: int, visited: set) -> str:
        if depth > self.MAX_SYMLINK_DEPTH:
            raise CycleError(f"too many levels of symbolic links: {path}")

        # 1. 转绝对路径
        if path.startswith('/'):
            abs_path = path
        else:
            abs_path = self.cwd.rstrip('/') + '/' + path

        # 2. 切段处理 . / ..
        parts = abs_path.split('/')
        stack: list[str] = []   # final path components
        for part in parts:
            if part == '' or part == '.':
                continue
            if part == '..':
                if stack:
                    stack.pop()
                continue
            # 普通名字
            stack.append(part)
            # 检查这一级是否是 symlink
            so_far = '/' + '/'.join(stack)
            if self.fs.is_symlink(so_far):
                if so_far in visited:
                    raise CycleError(f"symlink cycle at {so_far}")
                target = self.fs.symlinks[so_far]
                visited.add(so_far)
                resolved_target = self._resolve_path(target, depth + 1, visited)
                visited.discard(so_far)
                # 用 resolved target 替换栈
                stack = resolved_target.strip('/').split('/') if resolved_target != '/' else []

        result = '/' + '/'.join(stack) if stack else '/'
        return result

    def cd(self, path: str) -> None:
        new = self.resolve(path)
        if not self.fs.is_dir(new):
            raise FileNotFoundError(f"no such directory: {new}")
        self.cwd = new
```

## 复杂度

- 每段路径 O(1) push/pop 栈
- Symlink resolve 递归深度 ≤ MAX_SYMLINK_DEPTH
- 总时间 **O(P + L)**，P = 总路径段数，L = 总 symlink resolve 次数（深度不超 40）

## 关键技术点

### 1. 栈处理 `.` / `..`

`.` 跳过；`..` pop；普通 push。**注意 root 上 `..` 不要 pop 到负**（保持空栈，意味着仍在 `/`）。

### 2. Symlink 解析时机

每 push 一段后立即检查"当前累积路径是否 symlink"。这跟"路径最后再统一替换" 不同 —— 一个 symlink 在路径中间也要展开。

例：`/foo/bar/baz`，如果 `/foo` 是 symlink 指向 `/x/y`，那应该展开成 `/x/y/bar/baz` 再继续 resolve。

### 3. Cycle Detection

DFS 模式：进入一个 symlink 时加 visited，出来时移除。这跟"图 DFS 检环"完全一致。

**还有一种更宽松**：用 depth counter，超 40 抛错（POSIX 标准）。两者结合最稳。

### 4. Symlink target 也可以是相对路径

`ln -s ../foo bar` —— target 是 `../foo`。我代码里 `_resolve_path(target, ...)` 递归 resolve target，target 也走完整解析（含 .. 处理）。

### 5. Symlink 的当前目录

按 POSIX 语义，symlink target 的相对路径**基于 symlink 所在目录**，不是 cwd。例：`/x/link → ../foo`，等于 `/x/../foo` = `/foo`。

更精确实现：

```python
target = self.fs.symlinks[so_far]
if not target.startswith('/'):
    # 相对 symlink 所在目录
    parent = '/' + '/'.join(stack[:-1])
    target = parent + '/' + target
```

## 边界 case

```python
cd = CDCommand(fs)
assert cd.resolve('/') == '/'
assert cd.resolve('//foo//bar') == '/foo/bar'     # 多 slash
assert cd.resolve('/foo/.././bar/..') == '/'      # 全 cancel
assert cd.resolve('..') == '/'                    # 在 root cd ..
fs.create_symlink('/sl', '/foo/bar')
assert cd.resolve('/sl') == '/foo/bar'
fs.create_symlink('/sl2', '/sl/baz')
assert cd.resolve('/sl2') == '/foo/bar/baz'
fs.create_symlink('/loop1', '/loop2')
fs.create_symlink('/loop2', '/loop1')
try:
    cd.resolve('/loop1')
except CycleError:
    pass  # expected
```

## 易错点

> [!pitfall]
> ❌ 路径 split 不过滤空串 —— 多 slash 时出错；
> ❌ `..` 在 root pop 到负 —— 应保持空栈；
> ❌ 只在最后整路径完毕才查 symlink —— 中间段是 symlink 不展开；
> ❌ Symlink target 当绝对路径 —— 应判断 startswith('/')；
> ❌ Cycle detection 用全局 visited 不移除 —— 二次访问被误判 cycle；正确做法 DFS visited add/remove；
> ❌ 没 depth 上限 —— 复杂 chain 可能 stack overflow。

> [!key]
> 三个核心：(1) **栈处理 path normalization**；(2) **DFS visited add/remove 检测 cycle**；(3) **每段都查 symlink（不是只看末段）**。

> [!followup]
> "如何支持 `~`（home 目录）？" → 在 split 前 expand。"如何处理大小写不敏感？" → 比较时 lower()。"如何并发安全？" → fs 操作加 RWLock。"如何处理 hard link？" → 不需要特殊处理，hard link 在 inode 层；cd 层面看到的 path 各自独立。
