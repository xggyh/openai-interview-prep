## 题目本质

实现一个 KV 存储的 **serialize / deserialize** 函数：key 和 value 都是字符串，**可以包含任意字符**（包括分隔符、换行、null 字节、引号、反斜杠）。要求 round-trip：`deserialize(serialize(kv)) == kv`。

这题不考算法，考**协议设计 + 边界处理**。OpenAI 是 LLM 工厂，他们的检索/embedding/checkpoint 系统全都得有序列化能力，对字符串编码的鲁棒性要求极高。

## 解题切入点

任何"用分隔符切字符串"的方案都注定挂在分隔符冲突上。三种合理思路：

### A. 长度前缀（**最简单且正确**）

写入每条 entry 时先写 key 长度 + key + value 长度 + value，读取按长度截取，**不存在分隔符冲突**。

### B. 转义（escape）

约定一个分隔符（如 `\n`），key/value 中出现该字符时转成 `\\n`。复杂度低，但易出错。

### C. 二进制 framing（如 length-prefix int32 + payload）

工业级方案（gRPC、Redis RESP3 等用类似）。

面试推荐 **A** —— 实现 10 行，正确性显然。

## 主解法（长度前缀）

```python
class Codec:
    @staticmethod
    def serialize(kv: dict[str, str]) -> str:
        """
        编码格式：对每个 (k, v)：
            "<len(k)>:<k><len(v)>:<v>"
        例：{"a":"hello", "":""} →
            "1:a5:hello0:0:"
        """
        parts = []
        for k, v in kv.items():
            parts.append(f"{len(k)}:{k}{len(v)}:{v}")
        return "".join(parts)

    @staticmethod
    def deserialize(s: str) -> dict[str, str]:
        kv = {}
        i, n = 0, len(s)
        while i < n:
            # 读 key 长度
            j = s.index(":", i)        # 找到分隔冒号
            klen = int(s[i:j])
            i = j + 1
            k = s[i:i + klen]
            i += klen
            # 读 value 长度
            j = s.index(":", i)
            vlen = int(s[i:j])
            i = j + 1
            v = s[i:i + vlen]
            i += vlen
            kv[k] = v
        return kv
```

**为什么 ':' 不冲突？** `len(k)` 是非负整数的十进制，里面没有冒号；冒号只出现在分隔符位置。我们用第一个冒号定位长度结束 —— key 内容里即使有冒号也无所谓，因为我们按 `klen` 字节截取，不靠冒号切割。

## 复杂度

- **时间**：serialize O(n) where n = 总字符数；deserialize 同 O(n)
- **空间**：O(n)

## 边界 case 验证

```python
# 空 KV
assert Codec.deserialize(Codec.serialize({})) == {}
# 空 key 或空 value
assert Codec.deserialize(Codec.serialize({"": ""})) == {"": ""}
# 含特殊字符
data = {"a:b": "1:2:3", "x\n": "\\\"", "🎉": "héllo"}
assert Codec.deserialize(Codec.serialize(data)) == data
# 长字符串
big = "x" * 100000
assert Codec.deserialize(Codec.serialize({big: big})) == {big: big}
```

## 备选解法（转义版，更容易写错）

```python
ESC = "\\"
SEP_KV = "="    # 已转义
SEP_REC = "\n"  # 已转义

def _escape(s):
    return s.replace(ESC, ESC*2).replace(SEP_KV, ESC+SEP_KV).replace(SEP_REC, ESC+SEP_REC)

def _unescape(s):
    # 注意：必须从后往前替换或一次扫描，避免 \\\n 被错误展开
    ...
```

转义法写起来短，但一旦面试官追问"如果 escape char 自己出现怎么办"、"如何避免 O(n²) 替换"、"如何流式处理"，得绕一圈。长度前缀直接干净利落。

## 优化方向

| 优化点 | 做法 |
|---|---|
| 二进制更紧凑 | 长度用 varint 编码（protobuf 用法），减少长 string 的 ASCII 开销 |
| 流式 | yield 输出 / 用 generator 解析，避免一次性 load 全部到 memory |
| 多语言兼容 | 直接用 protobuf / msgpack / cbor 标准库，连协议都不用自己设计 |
| Checksum | 末尾加 CRC32，防止文件损坏 |

> [!key]
> **永远不要用"分隔符 + 期待 user data 里没出现"** —— 这是 codec 设计第一坑。长度前缀（length-prefixed framing）是工业界标准答案，写起来最干净。

> [!pitfall]
> ❌ 用 JSON：题面说 value 含任意字符，JSON 字符串里有引号需要 escape，自己实现 escape 又回到老问题；
> ❌ 用 base64：输出膨胀 4/3，面试官可能问"为什么不直接写"；
> ❌ 转义法没考虑 escape char 自己出现的递归；
> ❌ 用 `,` `;` `\n` 之类常见分隔符 —— 题面明说 value 可含任意字符。

> [!followup]
> "如果要支持 nested map / list 怎么办？" → 加一层 type tag（'M' = map, 'L' = list, 'S' = string），递归编码。"如何处理 4GB 大文件？" → length 用 8-byte int + 流式 read。"如果需要 partial update 不重写整个文件？" → 切换到 append-only log（每个 op 一条 record，定期 compact），就是个迷你 LSM。
