## 题目本质

**LC 157 Read N Characters Given Read4**：给一个 `read4(buf4) -> int` API，每次最多读 4 字符到 buf4 缓冲；返回实际读到的字符数（≤ 4）。实现 `read(buf, n)`：从文件读最多 n 字符到 buf，返回实际读到的字符数。

## 解法

每次 read4 拿 ≤ 4 个，复制到 buf 直到读够 n 或 read4 返回 < 4（EOF）。

## Python 实现

```python
class Solution:
    """假定 self.read4(buf4) 已被框架提供。"""
    def read(self, buf: list, n: int) -> int:
        total = 0
        buf4 = [''] * 4
        while total < n:
            got = self.read4(buf4)
            if got == 0:
                break  # EOF
            # 拷贝最多 min(got, n - total) 到 buf
            copy_len = min(got, n - total)
            for i in range(copy_len):
                buf[total + i] = buf4[i]
            total += copy_len
            if got < 4:
                break  # 文件读完
        return total
```

## 复杂度

- 时间：**O(n)** —— 最多 n/4 次 read4 调用，每次 O(1) 复制
- 空间：O(1) 不算 buf

## 关键点

### 1. 边界：read4 返回 < 4

返回 0 → EOF；返回 < 4（但 > 0）→ 文件最后一段，没满 4。这两种都该结束。

### 2. 不超过 n

最后一次 read4 可能多读了（got=4 但只需要 1 个）。`copy_len = min(got, n - total)`。

### 3. buf 不预分配长度

题目接受 buf 是 ≥ n 的预分配数组。我们直接索引写入即可。

## LC 158（连续调用）的区别

LC 158 是这题的 follow-up：**read 可被多次调用**。需要维护一个 4 字符的"剩余 buffer"在两次 read 之间。

```python
class Solution:
    def __init__(self):
        self.buf4 = [''] * 4
        self.head = 0
        self.tail = 0   # head..tail 是 buf4 里未消费的部分

    def read(self, buf, n):
        total = 0
        while total < n:
            if self.head == self.tail:
                self.tail = self.read4(self.buf4)
                self.head = 0
                if self.tail == 0:
                    break
            while total < n and self.head < self.tail:
                buf[total] = self.buf4[self.head]
                total += 1; self.head += 1
        return total
```

## 易错点

> [!pitfall]
> ❌ read4 返回 < 4 但 > 0 时直接 break，没复制 —— 漏数据；
> ❌ 没 min(got, n-total) —— 多复制；
> ❌ LC 158 调用间忘了维护状态 —— 每次 read 都从文件头读；
> ❌ buf 用 string 拼接而非 list —— 索引赋值出错（题目 buf 是 List[str]）。

> [!key]
> 工业级流式 reader 都是这套模式：底层 chunk API + 上层 byte-stream API + 中间 buffer。同思路适用于：网络 socket 读、tar/zip stream 解析、video chunk decoder。

> [!followup]
> "如果是 binary stream (bytes)？" → buf4 改为 bytearray；"多线程并发 read？" → 加锁保护 head/tail；"如果 read4 是 async？" → 用 asyncio + await；"如何处理 partial UTF-8 边界？" → 维护多字节字符 buffer，等收齐再返回。
