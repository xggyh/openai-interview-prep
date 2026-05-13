## 题目本质

实现一个 **IPv4 Address Iterator**，从给定的起始地址开始按下列三种模式遍历：**forward**（递增）、**reverse**（递减）、**CIDR block**（在指定 CIDR 块内遍历）。

不是算法题，是 **OOP + 位运算 + 字符串解析** 题。考点：把 IP 当作 32-bit 整数处理 + 迭代器协议。

## 题目语义

```python
# Forward
it = IPv4Iterator("192.168.1.0")
next(it)  # "192.168.1.0"
next(it)  # "192.168.1.1"
...

# Reverse
it = IPv4Iterator("192.168.1.0", direction="reverse")
next(it)  # "192.168.1.0"
next(it)  # "192.168.0.255"
...

# CIDR
it = IPv4Iterator.from_cidr("192.168.1.0/29")
list(it)  # ["192.168.1.0", ..., "192.168.1.7"]
```

## 解题切入点

**IPv4 = 32-bit 无符号整数**。把字符串 `"a.b.c.d"` 解析成 `int`，迭代就是 +1 / -1。

转换函数：

```python
def ip_to_int(ip: str) -> int:
    a, b, c, d = map(int, ip.split('.'))
    return (a << 24) | (b << 16) | (c << 8) | d

def int_to_ip(n: int) -> str:
    return f"{(n >> 24) & 255}.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"
```

边界：`0.0.0.0` (= 0) 和 `255.255.255.255` (= 0xFFFFFFFF) 之间环绕。

## Python 实现

```python
from typing import Iterator, Literal

class IPv4Iterator:
    """支持 forward/reverse 单向迭代 + CIDR 块迭代的 IPv4 地址生成器。"""

    MIN_IP = 0
    MAX_IP = 0xFFFFFFFF

    def __init__(self, start: str | int,
                 direction: Literal['forward', 'reverse'] = 'forward',
                 end: str | int | None = None):
        self._current = self._to_int(start)
        self._direction = direction
        self._step = 1 if direction == 'forward' else -1
        if end is None:
            self._end = self.MAX_IP if direction == 'forward' else self.MIN_IP
        else:
            self._end = self._to_int(end)
        self._done = False

    @staticmethod
    def _to_int(v) -> int:
        if isinstance(v, int): return v
        a, b, c, d = (int(x) for x in v.split('.'))
        if not all(0 <= x < 256 for x in (a, b, c, d)):
            raise ValueError(f"invalid IPv4: {v}")
        return (a << 24) | (b << 16) | (c << 8) | d

    @staticmethod
    def _to_str(n: int) -> str:
        return f"{(n >> 24) & 255}.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"

    @classmethod
    def from_cidr(cls, cidr: str) -> 'IPv4Iterator':
        """e.g. "192.168.1.0/29" → 起 192.168.1.0 终 192.168.1.7"""
        addr, mask = cidr.split('/')
        prefix = int(mask)
        if not (0 <= prefix <= 32):
            raise ValueError(f"invalid mask {mask}")
        base = cls._to_int(addr)
        host_bits = 32 - prefix
        # network 地址：高 prefix 位
        net = base & ((cls.MAX_IP << host_bits) & cls.MAX_IP)
        end = net | ((1 << host_bits) - 1) if host_bits > 0 else net
        return cls(net, direction='forward', end=end)

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        if self._done:
            raise StopIteration
        cur = self._current
        # 当前值已超出范围？
        if self._direction == 'forward' and cur > self._end:
            raise StopIteration
        if self._direction == 'reverse' and cur < self._end:
            raise StopIteration
        result = self._to_str(cur)
        # 推进
        nxt = cur + self._step
        # 防止越界
        if nxt < self.MIN_IP or nxt > self.MAX_IP:
            self._done = True
        else:
            self._current = nxt
            # 若推进后越过 end，下次 __next__ 会判断
        if cur == self._end:
            self._done = True
        return result
```

使用：

```python
# Forward 列 5 个
it = IPv4Iterator("10.0.0.254")
for _ in range(5): print(next(it))
# 10.0.0.254 / 10.0.0.255 / 10.0.1.0 / 10.0.1.1 / 10.0.1.2

# Reverse 列 3 个
it = IPv4Iterator("10.0.1.0", direction="reverse")
for _ in range(3): print(next(it))
# 10.0.1.0 / 10.0.0.255 / 10.0.0.254

# CIDR /30 → 4 个地址
list(IPv4Iterator.from_cidr("192.168.1.0/30"))
# ['192.168.1.0', '192.168.1.1', '192.168.1.2', '192.168.1.3']
```

## 复杂度

- 解析 IP / 转换：O(1)
- 单次 next：O(1)
- CIDR 列出全部：O(2^(32-prefix))

## 关键点

1. **IPv4 当 32-bit int 处理**：转换成本 O(1)，加减就是步进
2. **8.8.8.255 + 1 = 8.8.9.0** 自然 carry：因为是单一 int + 1，bit 自动进位
3. **CIDR 计算**：mask 算 network 地址（高 N 位）、host 范围（低 32-N 位）
4. **边界 0.0.0.0 / 255.255.255.255** 不要越界 wrap

## CIDR 详解

`192.168.1.0/29` 意思：32 位中前 29 位是 network 标识，剩 3 位是 host。
- mask = `1...10000...0`（前 29 个 1，后 3 个 0）= `0xFFFFFFF8`
- network = `192.168.1.0 & mask` = `192.168.1.0`
- 第一个地址 = network；最后地址 = network | (~mask) = `192.168.1.7`
- 总共 `2^3 = 8` 个地址

## 边界 case

```python
# 0.0.0.0 forward 不应越界回环
list(IPv4Iterator("255.255.255.254"))[:3]
# ['255.255.255.254', '255.255.255.255', StopIteration]

# 0.0.0.0 reverse 不应越界
list(IPv4Iterator("0.0.0.1", direction="reverse"))[:3]
# ['0.0.0.1', '0.0.0.0', StopIteration]

# /32 = 单个地址
list(IPv4Iterator.from_cidr("1.2.3.4/32"))
# ['1.2.3.4']

# /0 = 全部 (慎用)
# 4,294,967,296 个
```

## 易错点

> [!pitfall]
> ❌ 解析 IP 用 string split + 不校验范围（256+） —— 接受非法 IP；
> ❌ CIDR mask 计算时 `prefix == 0` 或 `prefix == 32` 边界 —— `1 << 32` 在 Python 是 4G 但 mask 应该是 0；
> ❌ Reverse iterator 从 `0.0.0.0` 还想再 -1 —— 应当 StopIteration；
> ❌ next 推进时已经越过 end 才发现 —— 在 next 开头检查。

> [!key]
> 把 IPv4 转成 int 是这道题的关键 idea。剩下都是迭代器协议 + 边界处理。从 `from_cidr` 创建出来是普通的 `IPv4Iterator(start, end='...')`，所有模式共用 next 逻辑。

> [!followup]
> "IPv6 怎么扩展？" → 用 128-bit int 替换；Python 大整数原生支持。"如何并行迭代 1 亿 IP？" → 不要列出，按 chunk + multiprocessing。"如何检查某 IP 是否在 CIDR？" → `(target & mask) == network`，O(1)。
