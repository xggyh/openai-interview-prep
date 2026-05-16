## 题目本质

设计 **Distributed Cache System**（类 Redis Cluster / Memcached）：分布式 KV cache，支持 GET/PUT/DELETE，10M+ QPS，sub-millisecond 延迟，多 region。

Google 报告 12 次。考点：**consistent hashing + replication + eviction + multi-region propagation**。

## 需求拆解

- KV API：get(k) / set(k, v, ttl) / del(k)
- 1B+ keys，5 TB 数据，500B avg value
- 10M+ QPS，P99 < 1ms
- 99.99% availability
- Multi-region read/write

## 整体架构

```ascii
                   Client SDK
                       │ consistent hash routing
                       ▼
                ┌──────────────┐
                │ Coord svc    │  cluster topology (Zookeeper/etcd)
                │ (rebalance)  │
                └──────┬───────┘
                       │ (topology pull)
                       ▼
       ┌──────────┬──────────┬──────────┐
       │  Node 1  │  Node 2  │  Node N  │  per node: in-memory hash table
       │ (shard 0)│ (shard 1)│ (shard k)│  + replicas
       └──────────┘──────────┴──────────┘
                       │
                       │ async replication / CDC
                       ▼
                  multi-region async sync
```

## 核心组件

### 1. Consistent Hashing + Virtual Nodes

每物理节点对应 100-500 个 virtual node 散在 hash ring，避免 hot spot 当节点加入/离开时 minimize 数据 movement。

```python
def route(key: str) -> Node:
    h = hash(key)
    return ring.successor(h)  # binary search in sorted vnode list
```

### 2. Replication (N=3)

每 shard 3 副本：1 primary + 2 followers。Primary 接 write，async replicate to followers。

Quorum 选项：
- **eventual**: write 到 primary 即 ack（最快）
- **read-your-write**: 用 R+W > N
- **strong**: write 等多数副本确认（牺牲延迟）

Cache 通常用 **eventual** —— 短暂 stale 可接受。

### 3. In-memory data structure

每 node：
- Hash table：key → (value, expire_at, last_access)
- LRU list（doubly-linked list）for eviction
- Per-shard mutex 或 sharded lock 减锁竞争

### 4. Eviction

- LRU：access 时 move to head, evict from tail when memory > 80%
- TTL：lazy expire on read + background sweep（每秒扫一小 batch）
- LFU: 可选 for 频率敏感 cache（参考 LFU Cache 题）

### 5. Failover

- 心跳：每 node 每秒向 coord 报 health
- 30 秒无心跳 → mark dead，promote 一个 follower 为 primary
- Coordinator 推送新 topology to clients
- 旧 primary 恢复 → 重 join 作 follower

### 6. Rebalance

加 / 删 node 时，consistent hash ring 重排。只**少量 key** 迁移（virtual node 设计的好处）。
- Migration 后台 stream，不阻塞 read
- Client SDK 在 migrate window 内 retry on miss

### 7. Multi-region

```
Region A primary → CDC → Region B follower
读：always local region
写：可选 region-primary（单主）或 multi-master（CRDT for cache）
```

对 cache，**single-master per key** + per-region read replica 最简。

### 8. Client SDK

```python
class Client:
    def __init__(self, coord_url):
        self.topology = fetch_topology(coord_url)
        self.refresh_periodic()

    def get(self, key):
        node = self.topology.route(key)
        for attempt in range(3):
            try:
                return self._call(node, "GET", key)
            except (Timeout, NodeDown):
                self.topology.refresh()
                node = self.topology.route(key)
```

Retry + topology refresh 处理 node failure 透明。

## 关键技术决策

| 决策 | 选择 | 替代 |
|---|---|---|
| Sharding | Consistent hash + vnodes | Hash mod N：rebalance 全部移动 |
| Replication | Async, eventual | Sync, quorum：延迟高 |
| Eviction | LRU + TTL | LFU：复杂；FIFO：HIT rate 低 |
| Topology | 中心 coord + client pull | Gossip：复杂 |
| Multi-region | 单主 + async replica | Multi-master：write conflict |

## 容量估算

- 1B keys × 500B = 500 GB → 50 nodes × 10 GB RAM each
- 10M QPS / 50 nodes = 200k QPS per node → 单 node 64 GB RAM，64 core，能撑
- Network：10M × 500B = 5 GB/s ingress（分散到 50 node 每个 100 MB/s）

## 易错点

> [!pitfall]
> ❌ Hash mod N 分片 —— 加节点全部 rehash；
> ❌ 同步 replication —— P99 延迟爆；
> ❌ Cache 强一致 —— 牺牲延迟无必要；
> ❌ 不做 client-side topology refresh —— node 挂掉客户端不知；
> ❌ Eviction 用 random —— hit rate 低于 LRU 30%。

> [!key]
> 三大要点：(1) **Consistent hash + virtual nodes** 解决 sharding + rebalance；(2) **Async replication + eventual** 保证延迟；(3) **Client SDK 处理 topology + retry** 让 node failure 透明。

> [!followup]
> "如何 cache stampede？" → request coalescing 或 probabilistic early expiration；"Hot key 怎么办？" → client-side caching + read replica + key splitting；"Cache invalidation？" → publish-subscribe propagate invalidation events；"Persistence？" → optional AOF / RDB snapshots（Redis 风格）。
