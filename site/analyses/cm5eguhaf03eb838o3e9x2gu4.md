## 题目本质

**LC 1797 Design Authentication Manager**：实现一个 token 管理器，token 在创建/续期后 `timeToLive` 秒过期。需要支持：
- `generate(tokenId, currentTime)` 创建
- `renew(tokenId, currentTime)` 续期（仅在 token 未过期时）
- `countUnexpiredTokens(currentTime)` 当前未过期 token 数

**关键细节**：时刻 `t` 上的过期发生**先于**该时刻的其他操作（先清理过期再处理本时刻请求）。

## 解题切入点

每个 token 维护"过期时间 = 创建/续期时刻 + ttl"。需要快速：
- O(log n) 创建/续期（update 过期时间）
- O(1) 或 O(log n) 查"未过期数"

两个核心选择：

**A. dict + lazy expiration**：`expiry[tokenId] = expiry_time`。查询时扫描整 dict 过滤未过期。简单但 query O(N)。

**B. dict + min-heap / SortedDict**：dict 存最新过期；min-heap 按过期时间排序，查询时弹出过期。查询 O(log N) 摊销。

LC 数据规模小，A 写起来稳。生产推荐 B。

## Python 实现（推荐方案 B）

```python
import heapq

class AuthenticationManager:
    def __init__(self, timeToLive: int):
        self.ttl = timeToLive
        # tokenId -> latest expire time (renew 会覆盖)
        self.expire_at: dict[str, int] = {}
        # min-heap of (expire_time, tokenId)；可能有 stale entries
        self.heap: list[tuple[int, str]] = []

    def generate(self, tokenId: str, currentTime: int) -> None:
        exp = currentTime + self.ttl
        self.expire_at[tokenId] = exp
        heapq.heappush(self.heap, (exp, tokenId))

    def renew(self, tokenId: str, currentTime: int) -> None:
        # 仅当 token 当前未过期才续期
        if tokenId not in self.expire_at:
            return
        if self.expire_at[tokenId] <= currentTime:
            # 已过期；按题意先过期、再处理 → 续期无效
            del self.expire_at[tokenId]
            return
        new_exp = currentTime + self.ttl
        self.expire_at[tokenId] = new_exp
        # 旧的 (old_exp, tokenId) 仍在 heap 里，但后面 countUnexpired
        # 弹出时会发现 self.expire_at[tokenId] != old_exp，跳过
        heapq.heappush(self.heap, (new_exp, tokenId))

    def countUnexpiredTokens(self, currentTime: int) -> int:
        # 先 lazy delete：堆顶过期的弹出
        while self.heap and self.heap[0][0] <= currentTime:
            exp, tid = heapq.heappop(self.heap)
            # 这个 entry 是不是当前最新？若不是，是 stale，丢掉即可
            if self.expire_at.get(tid) == exp:
                # 是最新，确实过期了
                del self.expire_at[tid]
            # else: stale，丢
        return len(self.expire_at)
```

## 复杂度

| 操作 | 复杂度 |
|---|---|
| generate | O(log N) 推 heap |
| renew | O(log N) 推 heap |
| countUnexpiredTokens | 摊销 O(log N) per call |

总操作 M 次的总开销 O(M log N)。

## 关键技术点

### 1. 为什么需要 heap？

如果只用 dict，每次 `countUnexpiredTokens` 都要遍历整个 dict 检查过期，O(N) 每次。N 大时不行。

heap 提供"按过期时间排序"，每次只需弹掉 ≤ currentTime 的堆顶，剩下的还都未过期。

### 2. Stale heap entries

`renew` 时新 expire 入 heap，但旧的不删（heap 不支持删除任意元素）。`countUnexpiredTokens` 弹出时检测：

```python
if self.expire_at.get(tid) == exp:  # 当前最新
    # 真的过期了
else:
    # stale entry，跳过（更新的 entry 还在 heap 后面或已被处理）
```

这是 **lazy deletion** 技巧。

### 3. "过期发生在该时刻之前" 边界

题面 `if expiryTime <= currentTime then expired`。注意是 `<=` 不是 `<`：例 ttl=5, generate at t=2 → exp=7。currentTime=7 时 7 <= 7 → 已过期。

```python
while heap and heap[0][0] <= currentTime:  # 用 <=
```

## LC 简化解法（操作量小时）

```python
class AuthenticationManager:
    def __init__(self, ttl):
        self.ttl = ttl
        self.tokens = {}        # id -> expire_at

    def generate(self, tid, t):
        self.tokens[tid] = t + self.ttl

    def renew(self, tid, t):
        if self.tokens.get(tid, 0) > t:
            self.tokens[tid] = t + self.ttl

    def countUnexpiredTokens(self, t):
        # 顺便清理（不必要但有助 long-running）
        self.tokens = {k: v for k, v in self.tokens.items() if v > t}
        return len(self.tokens)
```

O(N) per countUnexpired，LC 测试能过。

## 易错点

> [!pitfall]
> ❌ Renew 不检查"是否过期"，直接续期 —— 违反语义；
> ❌ countUnexpired 用 `>=` / `<` 比较错过期边界；
> ❌ heap 不处理 stale entries 直接 pop 计数 —— 计数错误；
> ❌ 没考虑 long-running 情况 dict 越来越大（renewed 但不再访问的 token 没清理） —— 加 lazy cleanup。

> [!key]
> dict（权威状态）+ min-heap（按过期排序）+ lazy deletion（heap stale 不删）是这类 TTL 题的标准组合。`Authentication Manager`、`Logger Rate Limiter`、`Time-Based KV Store` 都共用此模式。

> [!followup]
> "如果生产环境怎么实现？" → Redis EXPIRE 自带 TTL，不用自己管 heap。"如何分布式？" → Redis 集群分片 by tokenId；countUnexpiredTokens 改为聚合（不实时一致）。"如果需要列出所有未过期 token？" → 返回 dict 的 keys，调用前先 lazy cleanup。
