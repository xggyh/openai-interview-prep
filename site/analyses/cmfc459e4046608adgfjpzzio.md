## 题目本质

**N-ary tree 节点通信 → count cluster machines**：树的每个节点代表集群中的一台机器。每台机器只能通过 `sendAsyncRequest(toNodeId, message)` 和 `receiveRequest(fromNodeId, message)` 与**父节点和子节点**通信。Root 节点要统计整个集群有多少台机器。

题目隐含约束：
- 节点 id 互通（已知 parent / children id）
- 通信是异步的（不是直接函数调用）
- 不存在共享状态

考点：**分布式聚合 / 树形 reduce / 异步消息处理**。

## 解题切入点

经典**分布式 reduce-on-tree** 模式：

1. Root 向所有 child 发 `"COUNT_REQUEST"`
2. 每个内部节点收到后向自己的所有 child 发 `"COUNT_REQUEST"`，并记下"在等几个 child 回复"
3. 叶子节点收到后立即向 parent 回复 `"COUNT_RESPONSE: 1"`（自己 1 台）
4. 内部节点收到全部 child 的 `COUNT_RESPONSE` 后，sum + 1（自己）→ 回复给 parent
5. Root 集齐所有 child 的回复 → sum + 1 → 这就是总数

这是 **fan-out + fan-in** 模式。

## Python 实现

```python
from collections import defaultdict
from typing import Callable

class Node:
    """集群中的一台机器。仅与父和子通过 sendAsyncRequest 通信。"""

    def __init__(self, node_id: int, parent_id: int | None, children_ids: list[int]):
        self.node_id = node_id
        self.parent_id = parent_id
        self.children_ids = children_ids
        # 当前正在等待的 count 请求状态
        # request_id -> {pending: set of child ids, sum: int, origin: 'self' or parent_id}
        self._pending: dict[str, dict] = {}
        # 当 root 收到完整 count 时的回调
        self._on_count_complete: Callable[[int], None] | None = None

    # ----- 框架提供的 API -----
    def sendAsyncRequest(self, to_node_id: int, message: dict):
        """框架提供：把 message 异步发到 to_node_id"""
        raise NotImplementedError  # framework will inject

    # ----- 公共 API -----
    def count_cluster(self, callback: Callable[[int], None]) -> None:
        """Root 调用此 API 启动计数"""
        if self.parent_id is not None:
            raise RuntimeError("count_cluster must be called on root")
        request_id = self._new_request_id()
        self._on_count_complete = callback
        self._pending[request_id] = {
            'pending': set(self.children_ids),
            'sum': 0,
            'origin': 'self',
        }
        if not self.children_ids:
            # 单节点集群
            callback(1)
            return
        for cid in self.children_ids:
            self.sendAsyncRequest(cid, {
                'type': 'COUNT_REQUEST',
                'request_id': request_id,
                'sender': self.node_id,
            })

    def receiveRequest(self, from_node_id: int, message: dict) -> None:
        """由框架在收到消息时自动调用"""
        mtype = message['type']
        rid = message['request_id']

        if mtype == 'COUNT_REQUEST':
            # 我是内部节点或叶子，记录是哪个 parent 问的
            if not self.children_ids:
                # 叶子，直接回复 1
                self.sendAsyncRequest(from_node_id, {
                    'type': 'COUNT_RESPONSE',
                    'request_id': rid,
                    'count': 1,
                })
                return
            # 内部节点：转发给 children，等回复
            self._pending[rid] = {
                'pending': set(self.children_ids),
                'sum': 0,
                'origin': from_node_id,
            }
            for cid in self.children_ids:
                self.sendAsyncRequest(cid, {
                    'type': 'COUNT_REQUEST',
                    'request_id': rid,
                    'sender': self.node_id,
                })

        elif mtype == 'COUNT_RESPONSE':
            state = self._pending.get(rid)
            if not state:
                return  # 重复 / 过期
            state['sum'] += message['count']
            state['pending'].discard(from_node_id)
            if not state['pending']:
                total = state['sum'] + 1  # +1 算自己
                origin = state['origin']
                del self._pending[rid]
                if origin == 'self':
                    # 我是 root，完成
                    if self._on_count_complete:
                        self._on_count_complete(total)
                else:
                    # 转发给 parent
                    self.sendAsyncRequest(origin, {
                        'type': 'COUNT_RESPONSE',
                        'request_id': rid,
                        'count': total,
                    })

    def _new_request_id(self) -> str:
        import uuid
        return uuid.uuid4().hex
```

## 复杂度

- 消息数：每个节点收到 1 个 REQUEST + 1 个 RESPONSE，**O(N)** 总消息
- 时间（wall-clock）：树高 H 的 round trip → **O(H)** 时间，H = O(log N) for balanced tree

## 关键设计点

### 1. 用 request_id 区分并发请求

可能有多个 count 操作同时跑（监控系统每秒一次）。每次 root 启动用唯一 `request_id`，节点用 `_pending[rid]` 隔离状态。

### 2. 叶子早回复

`if not children_ids:` → 直接 send response。否则会陷入"我等 child / 没 child 等" 的悖论。

### 3. 内部节点先等齐再上报

`state['pending']` 集合维护"还在等的 child"。每个 RESPONSE 到达就 discard 一个。集合空了表示齐了，sum + 1 转发给 parent。

### 4. Origin 记录

每个内部节点要记住"这次 count 是哪个 parent 发起的"，因为多 count 并发时不能搞混向哪个 parent 回复。

### 5. 容错（如果面试官追问）

- **超时**：每个节点对每个 request 设 timeout（如 5s）。超时未集齐 → 向 parent 发 partial / fail 报告
- **节点故障**：parent 等不到某 child 的回复 → 标记该 child unreachable，sum 不包括其子树（或者 retry）
- **消息丢失**：基础设计假设可靠传输（TCP）；如果是 UDP 需要 application-level ack + retry

## 替代方案

### 同步递归 RPC（如果框架支持）

```python
def count(self) -> int:
    if not self.children_ids:
        return 1
    return 1 + sum(self.send_sync(c, 'COUNT') for c in self.children_ids)
```

简单很多，但同步阻塞 → root 等待时间 = tree depth × RTT，期间不能做别的事。

异步版本可以**root 同时向所有 child 发送**，每个 child 又同时向自己 child 发送 —— **总时间是 O(H)，不是 O(N)**。

## 易错点

> [!pitfall]
> ❌ 内部节点没区分 "是 root 还是中转" —— 上报对象搞错；
> ❌ 没用 request_id —— 多 count 并发时状态串了；
> ❌ Sum 时忘了 +1（自己）；
> ❌ 同步阻塞每个 child（一个一个等）—— O(H × children_per_node)，应当并发；
> ❌ 不处理重复消息 —— 网络重传导致计数翻倍。

> [!key]
> 树形分布式聚合的核心：**fan-out 请求 + 等齐 child 回复 + reduce 上报**。模式同 MapReduce 的 shuffle、Spark 的 reduceByKey-on-tree、Gossip 协议。

> [!followup]
> "如何扩展到 sum/min/max 任意聚合？" → 用 monoid 抽象（identity + associative op），框架不变只换 op。"如何处理节点动态加入/离开？" → 加入时 parent 注册，再 count 时自动包括；离开则 parent 检测 stale 后剔除。"如何避免节点频繁 count 浪费？" → 增量更新：节点状态变化时主动向上 propagate delta。
