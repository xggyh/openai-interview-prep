## 题目本质

LC 271 **Encode and Decode Strings**：把 `list[str]` 编码成单个 string，再解码回来。字符串可包含任意字符（含 NUL、换行、引号、反斜杠）。

经典 codec 设计题 —— **不能用任何"假设 user 数据里不会有的分隔符"**。

## 解题思路

**长度前缀法（length-prefixed framing）** 是工业界标准答案。每个字符串前写 `len + delimiter`，解码时按 len 截取，不依赖分隔符不出现在 user data。

格式：`"{len}#{string}{len}#{string}..."`，例：

```
["hello", "world"] → "5#hello5#world"
["", ""]           → "0#0#"
["#"]              → "1##"           ← 注意是 1#+#
```

## Python 实现

```python
class Codec:
    def encode(self, strs: list[str]) -> str:
        return ''.join(f"{len(s)}#{s}" for s in strs)

    def decode(self, s: str) -> list[str]:
        out = []
        i = 0
        while i < len(s):
            # 找下一个 '#'
            j = s.index('#', i)
            L = int(s[i:j])
            i = j + 1
            out.append(s[i:i + L])
            i += L
        return out

# 测试
c = Codec()
data = ["hello", "world", "", "a#b", "x\ny", "\\\"'"]
assert c.decode(c.encode(data)) == data
```

## 复杂度

- 时间：encode O(N)（N 是总字符数）；decode O(N)
- 空间：O(N) 输出

## 关键点

**为什么 `#` 不冲突？** `len(s)` 是数字，里面没有 `#`。我们用第一个 `#` 定位长度结束 —— string 里的 `#` 不会被误识别，因为我们按 `L` 字节截取，不靠 `#` 切割。

```
"1##" 解析：
  i=0: s.index('#', 0) = 1  → L = int("1") = 1
  i=2: s[2:3] = "#"   ← 这是 user 数据里的 #
  i=3: 结束
  → ["#"] ✓
```

## 替代解法（不推荐但可能被问）

### 转义法

约定 `\` 为转义；分隔符用 `\n`。string 里出现的 `\` → `\\`，`\n` → `\\n`。

```python
def encode(strs):
    parts = [s.replace('\\', '\\\\').replace('\n', '\\\n') for s in strs]
    return '\n'.join(parts)

def decode(s):
    # 必须 char-by-char 扫，不能用 .split('\n')
    out, cur, esc = [], [], False
    for ch in s + '\n':
        if esc:
            cur.append(ch); esc = False
        elif ch == '\\':
            esc = True
        elif ch == '\n':
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
    return out
```

写起来比长度前缀长 3 倍，且容易写错（escape char 自己出现的递归处理）。**面试不要用这个**。

### Base64

把每个 string base64 编码 → 用 `,` 分隔（base64 字符集不含逗号）。

```python
import base64
def encode(strs): return ','.join(base64.b64encode(s.encode()).decode() for s in strs)
def decode(s):    return [base64.b64decode(x).decode() for x in s.split(',')] if s else []
```

正确但输出膨胀 33%，面试官可能问"为什么不直接写"。

## 边界 case

```python
assert c.decode(c.encode([])) == []
assert c.decode(c.encode([""])) == [""]
assert c.decode(c.encode(["", ""])) == ["", ""]
assert c.decode(c.encode(["#", "##", "###"])) == ["#", "##", "###"]
assert c.decode(c.encode(["a" * 1000])) == ["a" * 1000]
```

## 易错点

> [!pitfall]
> ❌ 用 `s.split(",")` / `s.split(",")` —— user 数据里也可能有分隔符；
> ❌ 用普通字符做分隔符不预想到 user 可能写入 —— 必须用长度前缀；
> ❌ 写转义法没考虑递归 escape；
> ❌ 解析 length 用 `s[0]` 取一位 —— 多位 length（"100#abc..."）会错；用 `index('#')` 找完整 length。

> [!key]
> Codec 设计的金科玉律：**用长度前缀（length-prefixed framing），不用分隔符**。这种 framing 是 TCP、protobuf、Redis RESP 都用的工业标准。

> [!followup]
> "如何处理超大 string（>1GB）？" → 长度用 varint 或固定 8-byte 二进制 int，不用 ASCII。"如何流式 encode/decode？" → encode 用 generator yield；decode 用 state machine 边读边解，不要一次性读全。"如何 endian-safe？" → 二进制 length 用 network byte order（big-endian）。
