## 题目本质

**LC 588 Design In-Memory File System**：实现内存文件系统，支持：
- `ls(path)`：返回 path 下的子项 list（按字典序）
- `mkdir(path)`：创建多级目录
- `addContentToFile(path, content)`：追加文件内容（不存在则创建）
- `readContentFromFile(path)`：返回文件内容

经典**Trie / 树结构 + 路径解析**。

## 数据结构

每个节点是 dir 或 file：

```python
class Node:
    def __init__(self, is_file=False):
        self.is_file = is_file
        self.children: dict[str, 'Node'] = {}  # 仅 dir 用
        self.content: str = ''                  # 仅 file 用
```

文件系统就是一棵以 `Node(is_file=False)` 为根的 Trie。

## Python 实现

```python
class Node:
    def __init__(self, is_file=False):
        self.is_file = is_file
        self.children: dict[str, 'Node'] = {}
        self.content: str = ''

class FileSystem:
    def __init__(self):
        self.root = Node(is_file=False)

    def _walk(self, path: str, create: bool = False) -> tuple['Node', str | None]:
        """Walk to the node at path.
        Returns (node, leaf_name).
        - If path is "/", returns (root, None)
        - If create=True, missing dirs are created (mkdir behavior)
        """
        if path == "/":
            return self.root, None
        parts = path.strip("/").split("/")
        cur = self.root
        for p in parts:
            if p not in cur.children:
                if create:
                    cur.children[p] = Node(is_file=False)
                else:
                    raise FileNotFoundError(path)
            cur = cur.children[p]
        return cur, parts[-1]

    def ls(self, path: str) -> list[str]:
        node, _ = self._walk(path)
        if node.is_file:
            # ls on a file returns just the filename
            return [path.rsplit("/", 1)[-1]]
        return sorted(node.children.keys())

    def mkdir(self, path: str) -> None:
        self._walk(path, create=True)

    def addContentToFile(self, path: str, content: str) -> None:
        # Walk to parent dir, then file
        parts = path.strip("/").split("/")
        cur = self.root
        for p in parts[:-1]:
            if p not in cur.children:
                cur.children[p] = Node(is_file=False)
            cur = cur.children[p]
        fname = parts[-1]
        if fname not in cur.children:
            cur.children[fname] = Node(is_file=True)
        cur.children[fname].content += content

    def readContentFromFile(self, path: str) -> str:
        parts = path.strip("/").split("/")
        cur = self.root
        for p in parts:
            cur = cur.children[p]
        return cur.content
```

## 复杂度

| 操作 | 时间 |
|---|---|
| ls | O(P + K log K)，P = path 长度（分段数），K = 该目录子项数（sort） |
| mkdir | O(P) |
| addContentToFile | O(P + L)，L = content 长度 |
| readContentFromFile | O(P + L) |

## 关键设计点

### 1. dir vs file 统一抽象

用一个 `Node` 类，`is_file` 标记是文件还是目录。文件没 children，目录没 content。也可以分两个 class 用 base class，更 OOP 但更繁琐。

### 2. mkdir 多级路径

`mkdir("/a/b/c")` 应该一次创建三级。`_walk(path, create=True)` 路径上遇到不存在的就建。

### 3. ls 在 file 上返回什么

题目：`ls("/a/b/file.txt")` 返回 `["file.txt"]`（文件名）。这是反直觉的，必须读题。

### 4. addContent 自动创建文件

如果不存在直接 create。但如果中间路径不存在 dir，要不要 auto-mkdir？题目说会，所以 path 上 missing dirs 也 create。

### 5. content 追加

`+=` 追加，不是覆盖。注意这点。

## 边界 case

```python
fs = FileSystem()
assert fs.ls("/") == []
fs.mkdir("/a/b/c")
assert fs.ls("/") == ["a"]
assert fs.ls("/a") == ["b"]
assert fs.ls("/a/b") == ["c"]
fs.addContentToFile("/a/b/c/file.txt", "hello ")
fs.addContentToFile("/a/b/c/file.txt", "world")
assert fs.readContentFromFile("/a/b/c/file.txt") == "hello world"
assert sorted(fs.ls("/a/b/c")) == ["file.txt"]
assert fs.ls("/a/b/c/file.txt") == ["file.txt"]   # 文件 ls 返回自身
```

## 易错点

> [!pitfall]
> ❌ ls 一个文件 path 返回 `["file.txt"]` —— 容易写成空 list 或 raise；
> ❌ addContent 覆盖 content 而非追加 —— 文档明说是 append；
> ❌ path 解析没处理首尾 slash —— `/a/b/`、`/a//b`、`//` 等；用 `strip("/")` + `filter(None, ...)` 保险；
> ❌ root "/" 用 `split("/")` 得到 `[""]`，不是空 list —— 要特判；
> ❌ children dict 用 `Counter` 之类排序不对 —— ls 要求字典序。

> [!key]
> Trie 模式：dict[child_name -> Node]。路径解析就是 dict 链式查找。同模板可用于：URL routing、CLI 命令树、namespace 解析。

> [!followup]
> "delete file/dir？" → 父 dict del；递归 delete 整个子树；"rename？" → 父 dict del 旧 key + 加新 key；"hard / soft link？" → 加 `link_to_node` 引用 / target string + 自定义 walk；"如何持久化？" → DFS 序列化为 JSON / pickle。
