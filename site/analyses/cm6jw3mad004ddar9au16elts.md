## 题目本质

**Remove Bad Pairs from a String**：定义 "bad pair" = 相邻字符同字母不同大小写（e.g. `'xX'`, `'Aa'`）。反复消除 bad pair 直到没有为止。

类似 LC 1544 Make The String Great。

## 解法

**栈** 一次扫描。遇到与栈顶组成 bad pair 的字符就 pop；否则 push。

## Python 实现

```python
class Solution:
    def makeGood(self, s: str) -> str:
        stack: list[str] = []
        for ch in s:
            if stack and abs(ord(stack[-1]) - ord(ch)) == 32:
                # 同字母不同大小写：ord 差 32
                stack.pop()
            else:
                stack.append(ch)
        return "".join(stack)
```

## 复杂度

- 时间：**O(N)** 每字符 push/pop 各 ≤ 1 次
- 空间：O(N) 栈

## 关键点

### 1. ord 差 32

ASCII: 'A'=65, 'a'=97。同字母大小写差 32。**`abs(ord(a) - ord(b)) == 32`** 是检测方便的方法。

### 2. 链式消除

栈处理天然实现"消除后栈顶再与下一个比"。例 `"aAbB"`：
- a push
- A 和 a 配对 → pop
- b push
- B 和 b 配对 → pop
- 结果 ""

### 3. 反复 vs 单次

题面要求"反复消除"。栈一次扫描已经实现了反复（pop 后下个字符仍可与新栈顶比较）。

## 易错点

> [!pitfall]
> ❌ 双重 loop 反复扫描 —— O(N²)，浪费；
> ❌ 用 `ch.lower() == prev.lower() and ch != prev` —— 字符串方法多调用一次，可以但慢；
> ❌ 没用 `abs`：'aA' (97-65=32) 和 'Aa' (65-97=-32) 都要识别；
> ❌ 输出忘了 join。

> [!key]
> 栈消除模式：相邻匹配 + 删除。同模板：LC 20 Valid Parentheses、LC 1209 Remove All Adjacent Duplicates II、LC 1047 Remove All Adjacent Duplicates。

> [!followup]
> "Bad pair 定义更复杂（比如 ASCII 距离 = 1）？" → 同样栈，改判断；"K 个相同字符删除？" → 栈每元素带 count；"返回删除次数？" → 维护 counter while 消除。
