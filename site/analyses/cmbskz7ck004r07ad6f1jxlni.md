## 题目本质

**Resumable Iterator**：实现一个可暂停/恢复的迭代器，支持 `get_state` / `set_state` 序列化状态。扩展：支持**多文件**和**异步操作**；用 **coroutine** 实现并发迭代多数据源。

OpenAI 报告 Mid-Senior，2 人。考点：**迭代器协议 + 状态持久化 + asyncio**。

## 题目语义

```python
# Basic
it = ResumableIterator([1, 2, 3, 4, 5])
print(next(it))                 # 1
print(next(it))                 # 2
state = it.get_state()          # {'pos': 2} 或类似
# 进程退出，重启
it2 = ResumableIterator([1, 2, 3, 4, 5])
it2.set_state(state)
print(next(it2))                # 3

# Multi-file
it = ResumableIterator.from_files(['a.txt', 'b.txt', 'c.txt'])
# 顺序读 a.txt 全部行 → b.txt → c.txt；可 pause/resume

# Async
async for line in async_resumable(['a.txt', 'b.txt'], concurrency=2):
    ...
```

## 基础同步实现

```python
from typing import Iterable, Iterator, Any
import json, pickle

class ResumableIterator:
    """支持 get_state / set_state 的可恢复迭代器。"""

    def __init__(self, items: list):
        self._items = items
        self._pos = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._pos >= len(self._items):
            raise StopIteration
        item = self._items[self._pos]
        self._pos += 1
        return item

    def get_state(self) -> dict:
        return {'pos': self._pos}

    def set_state(self, state: dict):
        self._pos = state.get('pos', 0)
```

## 多文件版本

```python
import os

class FileResumableIterator:
    """顺序遍历多个文件的行；状态含当前 file index + byte offset"""

    def __init__(self, paths: list[str]):
        self._paths = paths
        self._file_idx = 0
        self._byte_offset = 0
        self._fh = None
        self._open_current()

    def _open_current(self):
        if self._fh:
            self._fh.close()
            self._fh = None
        if self._file_idx >= len(self._paths):
            return
        self._fh = open(self._paths[self._file_idx], 'rb')
        self._fh.seek(self._byte_offset)

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        while self._file_idx < len(self._paths):
            line = self._fh.readline()
            if line:
                self._byte_offset = self._fh.tell()
                return line.rstrip(b'\n')
            # EOF of current file, advance
            self._fh.close()
            self._fh = None
            self._file_idx += 1
            self._byte_offset = 0
            if self._file_idx < len(self._paths):
                self._open_current()
        raise StopIteration

    def get_state(self) -> dict:
        return {
            'file_idx': self._file_idx,
            'byte_offset': self._byte_offset,
        }

    def set_state(self, state: dict):
        self._file_idx = state['file_idx']
        self._byte_offset = state['byte_offset']
        self._open_current()

    def __del__(self):
        if self._fh:
            self._fh.close()
```

**关键设计**：用 byte offset 而非 line number 表示位置 —— 这样 set_state 后 `f.seek(offset)` O(1)，不必重数行数。

## Async 多源并发版本

```python
import asyncio
from typing import AsyncIterator
import aiofiles

class AsyncResumableIterator:
    """并发读多文件，按文件顺序产出行。
    Coroutine 让 IO 等待时切换到别的 file。"""

    def __init__(self, paths: list[str], concurrency: int = 4):
        self._paths = paths
        self._concurrency = concurrency
        self._states: dict[str, int] = {p: 0 for p in paths}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=concurrency * 10)
        self._tasks: list[asyncio.Task] = []
        self._done = False

    async def _worker(self, path: str, sem: asyncio.Semaphore):
        async with sem:
            async with aiofiles.open(path, 'rb') as fh:
                await fh.seek(self._states[path])
                while True:
                    line = await fh.readline()
                    if not line:
                        break
                    await self._queue.put((path, line.rstrip(b'\n')))
                    self._states[path] = await fh.tell()

    async def __aenter__(self):
        sem = asyncio.Semaphore(self._concurrency)
        self._tasks = [asyncio.create_task(self._worker(p, sem)) for p in self._paths]
        # 等所有 workers 完成后 mark done
        asyncio.create_task(self._mark_done_when_all_finish())
        return self

    async def _mark_done_when_all_finish(self):
        await asyncio.gather(*self._tasks)
        self._done = True
        # sentinel
        await self._queue.put(None)

    async def __aexit__(self, *args):
        for t in self._tasks:
            t.cancel()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._done and self._queue.empty():
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item   # (path, line)

    def get_state(self) -> dict:
        return dict(self._states)

    def set_state(self, state: dict):
        self._states.update(state)


# Usage
async def main():
    async with AsyncResumableIterator(['a.txt', 'b.txt', 'c.txt'], concurrency=2) as it:
        async for path, line in it:
            print(path, line)
        state = it.get_state()   # 保存
        # 重启后
        async with AsyncResumableIterator(['a.txt', 'b.txt', 'c.txt']) as it2:
            it2.set_state(state)
            async for path, line in it2:
                ...
```

## 关键设计点

### 1. State 包含什么？

最小化：能让"重启后接着读"的所有信息。对文件来说就是 `(file_index, byte_offset)`；对内存 list 是 `index`。

**不能**简单存"已读 N 条" + 重新打开 + skip N 条 —— skip 是 O(N) 而非 O(1)。

### 2. State 可序列化

JSON / pickle 都行。优先 JSON（人类可读 + 跨语言）。

```python
def save_state(it, path):
    with open(path, 'w') as f:
        json.dump(it.get_state(), f)

def load_state(it, path):
    with open(path) as f:
        it.set_state(json.load(f))
```

### 3. Multi-source 并发的细节

asyncio + aiofiles：每个 file 一个 coroutine，IO 等待时让出。Semaphore 限制并发 file 数。**所有 worker 把行塞进同一个 queue**，main 消费 queue。

`get_state` 返回每个 file 当前 offset（dict）→ resume 时分别 seek。

**注意**：order 不保证 —— 多文件并发读，行交错出现。如果题面要求保持文件顺序，每个 file 单独 finish 完再下一个（退化为同步）。

### 4. 容错

- 文件读 EOF → 自然结束
- 文件不存在 → `set_state` 时检查并 raise / skip
- 文件大小改了（resume 之后被外部追加）→ offset 仍可用，会读到新内容

## 易错点

> [!pitfall]
> ❌ State 用"已读行数"而非 byte offset —— resume 时要重数 N 行；
> ❌ Multi-file 共用一个 file handle —— 不能并发；每个 file 独立 fh；
> ❌ Async 实现忘了 await readline() —— 阻塞 event loop；
> ❌ Worker exception 不捕获 —— gather 抛出 cancels 所有 worker；
> ❌ Resume 时不重新打开 file —— file handle 失效。

> [!key]
> 设计原则：**状态最小化 + O(1) 恢复**。文件用 byte offset；DB cursor 用 last_id；网络 stream 用 sequence number。Coroutine + queue 模式是多源并发标准结构。

> [!followup]
> "如果 source 是 Kafka topic？" → state 是 `(topic, partition, offset)`，resume 时 `consumer.seek(...)`；"如何在 source 改变时 invalidate state？" → state 加 source hash，set_state 时检查；"如果要保持 order across sources？" → 主从模式，主 source 完才下一个，不并发。
