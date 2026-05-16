## 题目本质

设计 **file system for write-once media**（CD-R / DVD-R / tape）：数据写后**不可修改**。例 archival storage、blockchain log、compliance "WORM" media。

## 特殊约束

- **Append-only**：不能 in-place 修改
- **Delete = mark**: 物理删除不可能，只能 logical
- **Block-level**：写一旦完成 immutable

## 解决思路

### 1. Log-structured file system

整个 FS 是 append-only log。所有操作（create file, write block, rename）都 append events 到 log。

```
[time 0] Create file "a.txt" inode=42
[time 1] Write block 0 of inode 42: <data>
[time 2] Write block 1 of inode 42: <data>
[time 3] Rename inode 42 → "b.txt"
[time 4] Delete inode 42  ← logical
```

读：replay events from beginning to compute current state。Or use checkpoint (snapshot of state at time T)。

### 2. In-memory index

构建时扫 log → 在内存维护 (path → block pointers)。Query 时 O(1) lookup。

启动慢（扫 log），但 query 快。Checkpoint 减少 replay cost。

### 3. Block addressing

- 物理 block address = sequential offset on media
- Logical block = via inode table → points to physical
- Allocation pointer：next free block。Monotonic increment。

### 4. Versioning

天然 versioned —— 同 file 多次 write 不覆盖，只 append 新 version。每 version 一个 timestamp。

读历史 version：scan log to that timestamp。

### 5. Space efficiency

Append-only 浪费空间（删除不 reclaim）。**Compaction**: 定期把 active state 写到新 media，老 media archive。

或者**generational**: 每 N 天滚动新 media，老 media 只读。

### 6. Crash consistency

每写完一个 block sync flush。Replay log 重建状态。Atomicity 用 checksum + sequence number。

### 7. Compliance use cases

- Audit log
- 金融交易 record
- Healthcare records
- Legal hold

WORM 满足"不可篡改"合规要求（SEC Rule 17a-4 等）。

## 数据结构

```python
class WORMFileSystem:
    def __init__(self, media):
        self.media = media          # append-only block device
        self.write_pointer = 0
        self.inode_table: dict[int, list[int]] = {}    # inode -> block list
        self.path_to_inode: dict[str, int] = {}
        self.next_inode = 1

    def create(self, path):
        inode = self.next_inode
        self.next_inode += 1
        self._append_event({"op": "create", "path": path, "inode": inode})
        self.path_to_inode[path] = inode
        self.inode_table[inode] = []

    def write(self, path, data):
        inode = self.path_to_inode[path]
        block_addr = self.write_pointer
        self.media.write(block_addr, data)
        self.write_pointer += len(data)
        self.inode_table[inode].append(block_addr)
        self._append_event({"op": "write", "inode": inode, "block": block_addr})

    def read(self, path):
        inode = self.path_to_inode[path]
        return b''.join(self.media.read(addr) for addr in self.inode_table[inode])
```

## 易错点

> [!pitfall]
> ❌ 把 LSM Tree 直接搬过来 —— LSM 假设可 mutate；WORM 不行；
> ❌ Delete 真删 —— media 不支持；
> ❌ 不 checkpoint → replay 长 log 启动慢；
> ❌ 不版本化 → 覆盖时丢历史；
> ❌ 不 atomic write → crash 时部分 block fail。

> [!key]
> WORM FS = **append-only log + in-memory state + checkpoint**。整体接近 event sourcing 或 git。

> [!followup]
> "如何 search by content？" → 同时 build search index (也 WORM)；"如何 compress？" → compress 写入前；"读 archived media？" → multi-volume support，需 mount old media；"如何 verify integrity？" → SHA256 per block + Merkle tree on logs。
