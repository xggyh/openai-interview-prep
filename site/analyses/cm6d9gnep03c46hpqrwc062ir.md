## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Cache** | 数据的"快速复印件"，放在内存里 | 桌上随手放的便签 vs 抽屉里的档案 |
| **Distributed Cache** | 不是单机内存，是一堆机器组成的内存池 | 整间办公室共用的便签墙 |
| **Redis / Memcached** | 业界两大开源 distributed cache 实现 | 便签墙的品牌 |
| **Cache hit / miss** | 查到了 / 没查到 | 在便签墙找到答案 / 还得翻档案 |
| **TTL (time-to-live)** | 缓存有效期，过期自动失效 | 便签上写"明天 5pm 后撕掉" |
| **Eviction** | 内存满了，按规则赶走旧数据 | 便签墙贴满了，撕掉最旧的 |
| **LRU / LFU** | 两种 eviction 策略：最久没用 / 最少用 | 撕"上次贴是上周的" / 撕"全月就看过两次的" |
| **Sharding (分片)** | 把数据按某个 key 切到不同机器 | 按姓氏首字母分发到不同前台 |
| **Consistent Hashing** | 一种特别的分片方式，加 / 减机器时只需挪一小部分数据 | 圆桌轮转，多个人来不用全员换座 |
| **Replication (复制)** | 同一份数据存到多台机器防丢 | 重要便签贴墙 + 抽屉各一份 |
| **Cache-aside** | 应用先查缓存，没有就查 DB 然后塞缓存 | 先翻便签，没有就翻档案再贴一张 |
| **Write-through** | 写入同时写缓存 + DB | 改了就同时贴便签和改档案 |
| **Write-back / write-behind** | 先只写缓存，异步刷 DB | 先贴便签，下班前再统一去改档案 |
| **Hot key** | 某个 key 被大量请求（比如明星 ID） | 一张便签被全办公室狂看 |
| **Thundering herd** | 缓存失效瞬间，所有请求挤向 DB | 突然撕了关键便签，所有人挤过来找档案 |
| **Cache stampede** | thundering herd 的另一个叫法 | 同上 |
| **Multi-region** | 数据中心分布全球，每个地区有本地缓存 | 公司在北京 / 纽约 / 伦敦各开分部 |
| **Strong consistency** | 写完立即可见，所有副本一致 | 改完文件，全办公室同步看到 |
| **Eventual consistency** | 最终一致，中间可能有 lag | 改完文件，过几秒/分钟才传到分部 |

---

## 1. 题目本质 — 这是什么问题

**Distributed Cache System** = 设计一个**分布式的内存键值数据库**，作为数据库前面的高速缓存层，让用户读写延迟从 ms 级降到 μs 级。

**典型产品**：
- **Redis Cluster** —— 业界最常用，Twitter / Snap / Discord 用它做 session store + feed cache
- **Memcached** —— Facebook 早期靠它扛 10× 流量
- **Amazon ElastiCache** —— 云上的 managed Redis/Memcached
- **DynamoDB DAX** —— Amazon 给 DynamoDB 加速的缓存层
- 任何"用户量很大、读多写少、容忍轻微不一致"的系统都用它

**为什么这是高频题（8 ppl 报告，Google STAFF 高频中的高频）**：

这道题把**所有分布式系统核心技能塞在一道**：
1. **Sharding** —— 数据怎么切到不同机器
2. **Replication** —— 怎么避免单点
3. **Consistency vs availability** —— CAP 怎么选
4. **Eviction** —— 内存满了怎么办
5. **Hot key + Thundering herd** —— 流量倾斜怎么处理
6. **Multi-region** —— 全球部署的一致性 trade-off
7. **Cache invalidation** —— "计算机科学最难的两件事之一"

考的就是你**对分布式核心 trade-off 的理解**，不是 Redis API 怎么调。

---

## 2. 题目重述 — 需求拆解

### 2.1 Functional requirements

5 个核心 API，**别多别少**：

| API | 含义 | 注意 |
|---|---|---|
| `GET(key) -> value` | 拿一个值 | 主要操作，占 80%+ |
| `SET(key, value, ttl?)` | 写一个值，可选过期 | TTL 必须支持 |
| `DELETE(key)` | 删除一个值 | 不删就靠 eviction |
| `EXPIRE(key, ttl)` | 改某个 key 的 TTL | optional |
| `INVALIDATE(pattern)` | 批量失效（按前缀 / tag） | 跟 DB 写操作配合 |

**面试时主动澄清的点**：
- 是 key-value 还是 sorted set / list / hash？（默认 key-value 就够，扩展再加）
- value 大小？(几 KB 还是几 MB？决定网络模型)
- 是否要 transaction / MULTI？(一般不需要，引入太复杂)
- 是否要 pub/sub？(一般另设计)

### 2.2 Non-functional requirements

| 维度 | 目标 | 为什么 |
|---|---|---|
| **延迟** | p99 < 5 ms (single region), p99 < 50 ms (cross region) | 这是缓存存在的全部意义 |
| **吞吐** | 100k QPS / node, 1M+ QPS / cluster | Redis 单核能跑 ~100k QPS |
| **可用性** | 99.99% | 缓存挂了 → 后端 DB 瞬间被压垮 |
| **一致性** | eventual consistency 可接受 | 缓存是 best-effort，不是真理 |
| **持久性** | 通常 **不** 需要 | 缓存丢了能从 DB 重建 |
| **scale** | 100B records, 10 TB 内存 | Google / Meta 级别 |

> [!key] **持久性是 trick 题**。STAFF 面试官常追问"Redis 也可以 persist 啊"。**回答**：可以但通常不开（fsync 影响延迟）。缓存的 source of truth 永远是 DB，缓存的角色是"加速"不是"存储"。

---

## 3. 容量估算 — back-of-envelope

假设：
- **DAU** = 1B
- 平均每用户每天 100 次缓存 read → 100 B reads/day
- 平均每用户每天 10 次缓存 write → 10 B writes/day
- 数据集 = 100 B distinct keys，每个 value 平均 1 KB

### Read / Write QPS

```
reads:  100B / 86400s ≈ 1.16 M QPS
writes: 10B / 86400s ≈ 116 k QPS
peak (3×): reads ≈ 3.5 M QPS, writes ≈ 350 k QPS
```

### 内存

```
100 B keys × (50 B key + 1 KB value + 100 B overhead)
≈ 100 B × 1.15 KB ≈ 115 TB total memory
```

实际中**不可能全部 cache** —— 通常 cache 命中率 ~80% 意味着只缓存"热数据"。

```
热数据 = top 20% keys → 23 TB 内存
单机内存 ≈ 256 GB DDR5 → 需要 90 台机器（带 replication 后 270 台）
```

### 网络

```
peak read 3.5M QPS × 1 KB = 3.5 GB/s aggregate ingress
→ 单机 100 Gbps NIC 能扛 12 GB/s，所以网络不瓶颈，瓶颈在 CPU + 内存带宽
```

### 一句话总结

> "为了 1B DAU，需要约 **270 台 256GB-RAM 机器（含 3x replication）**，扛 **3.5M reads/sec + 350k writes/sec**，**p99 < 5 ms**。"

---

## 4. API 设计

### 4.1 Client API

```
GET /cache/{key}
  Response: { value, ttl_remaining, source: "primary"|"replica" }

SET /cache/{key}
  Body: { value, ttl?: int }
  Response: { ok: true, version: int }

DELETE /cache/{key}
  Response: { ok: true, deleted: bool }

INVALIDATE /cache/by-tag/{tag}
  Response: { ok: true, count: int }
```

### 4.2 Internal protocol

**主流选择**：Redis RESP（plain text，简单）vs gRPC（结构化，多语言）。

**STAFF 答**：RESP for compatibility（无数客户端库），加 gRPC for internal admin。Server 同时监听两个端口。

---

## 5. 高层架构（step-by-step 推演）

### Step 1：单机 Redis（baseline）

```
Client → Redis (single node, 256 GB RAM)
```

**问题**：
1. 单点故障：机器挂了缓存全没
2. 内存上限：单机 256GB 装不下 23TB
3. CPU 上限：单机 ~100k QPS，扛不住 3.5M

**Next**: 必须水平扩展。

### Step 2：加 Sharding（解决容量 + 吞吐）

把 keys 按某种规则切到 N 台机器上。

**Naive sharding**：`shard_id = hash(key) % N`

```
                   ┌────────┐
Client ──hash──→   │ Router │  ───→ Shard 1, Shard 2, ..., Shard N
                   └────────┘
```

**问题**：加 / 减一台机器，`hash(key) % N` 全变 → 几乎所有数据要重新分配（rebalance 灾难）。

**Next**: 用 consistent hashing。

### Step 3：Consistent Hashing

把所有 shards 映射到一个**虚拟的环**（0 ~ 2^32）上，每个 key 顺时针找最近的 shard。

```
            shard A (hash=10)
           /
   key1 →
           \
            shard B (hash=80)
           /
   key2 →
           \
            shard C (hash=200)
```

**好处**：加一台 shard D（hash=150），只有 hash 落在 (80, 150] 的 key 受影响，其他 ~3/4 数据不变。

**进阶**：**virtual nodes**（每个物理 shard 在环上有 200 个虚拟点），让数据分布更均匀。

### Step 4：加 Replication（解决单点故障）

每个 shard 配 **1 primary + 2 replicas**。

```
              Shard A
         ┌────────┬─────────┬─────────┐
         │primary │replica 1│replica 2│
         └────────┴─────────┴─────────┘
```

**写**：只写 primary，primary 异步复制到 replicas。
**读**：可以 primary 或 replica（看一致性要求）。

**Failover**：primary 挂了，replica 通过 Raft / Sentinel 提升为新 primary。

### Step 5：Cache-aside pattern（与 DB 协作）

```
   1. GET key from cache
   2a. HIT → return
   2b. MISS →
        3. GET key from DB
        4. SET key in cache (with TTL)
        5. return
```

**Write**:
```
   1. UPDATE row in DB
   2. INVALIDATE key in cache (不更新，等下次 read miss 重建)
```

> [!key] **为什么写时 invalidate 而不是 update**？避免 **race condition**：两个并发 write，update 顺序可能跟 DB 顺序不一致，导致缓存里是旧值。Invalidate 让缓存"暂时空着"，下次 read 重建最新值。

### Step 6：加 multi-region

每个 region 一个 cache cluster，cross-region 通过**异步复制**串起来。

```
   us-east cluster   ←──async──→   eu-west cluster
                     ←──async──→   ap-south cluster
```

**问题**：写哪个 region？

- **Single-writer per shard**: 每个 key 有一个主 region，其他 region 是 follower
- **Multi-writer (last-write-wins)**: 任何 region 都能写，按 timestamp 解冲突
- **Multi-writer (CRDT)**: 用 CRDT 数据结构自动 merge

STAFF 推荐：**single-writer**，简单可控，配合 DNS routing 把同一 key 的写流量都路由到主 region。

---

## 6. 组件深挖 — 真正考验你深度

### Deep Dive 1: Hot Key（最高频追问）

**问题**：1 个 key（如明星 ID）瞬间 100k QPS，单 shard 单 primary 挤爆。

**4 种解法（从简单到深）**：

1. **本地客户端缓存**：客户端进程内存里再 cache 一层，TTL 设短（如 500ms）。简单，但脏数据风险。
2. **Hot key replication**：对识别出的 hot keys，自动复制到所有 replica。读流量随机打到任一 replica。
3. **Sharding by request, not by key**：把 hot key 拆成 `key_v1`, `key_v2`, ..., `key_v10`，每个 shard 一个，客户端随机选。写时全更新。**最 STAFF**。
4. **拒绝服务（rate limit）**：超过阈值的请求直接限流或排队（保护后端）。

**怎么 detect hot key**：
- 监控端按 key 的 QPS 排序，top-K 即 hot key
- 用 Count-Min Sketch 在网关层近似计数（省内存）
- 拐点检测：某个 key 1 分钟内 QPS 突涨 10×

### Deep Dive 2: Thundering Herd（缓存击穿）

**场景**：热门 key 的 TTL 同时过期，瞬间 100k requests 都 miss，全打到 DB。

**解法（多管齐下）**：

| 方案 | 怎么做 | trade-off |
|---|---|---|
| **Probabilistic refresh** | TTL 还剩 10% 时，**有概率**主动刷新（不等到 0） | 削峰，少量额外 DB 读 |
| **Singleflight / mutex** | 同一 key 的 N 个并发 miss，只让**第一个**去查 DB，其他等结果 | Go 标准库 `singleflight` 直接用 |
| **Stale-while-revalidate** | TTL 过期后**仍返回旧值**几秒，后台异步刷新 | 容忍轻微脏数据 |
| **Jitter TTL** | TTL 设 `60s ± 10%`，避免大批 key 同时过期 | 简单，强制实践 |

**STAFF 推荐组合**：jitter TTL + singleflight + probabilistic refresh，三层保护。

### Deep Dive 3: Eviction Policy

内存满了删谁？

| 策略 | 含义 | 何时用 |
|---|---|---|
| **LRU** | 最久没访问的删 | 通用默认。访问局部性高时好 |
| **LFU** | 最少访问次数的删 | 长尾访问场景（防 LRU 被一次性扫描污染） |
| **TTL-only** | 只删过期的，不主动删（如果空间用完拒写） | 不可控，少用 |
| **TinyLFU** | LFU 改进版，带"门票"机制防新数据污染 | Caffeine（Java）默认 |
| **Random** | 随机删一个 | Memcached 的简化版，O(1) |
| **W-TinyLFU** | TinyLFU + window LRU，业界最强 | 高端场景 |

**实现 LRU**：双向链表 + HashMap。访问时移到头部，淘汰从尾部。O(1)。

> [!key] **STAFF 加分**：知道 Redis 的 **approximate LRU**（采样 5 个 key，淘汰最旧的）—— 内存节省，准确性略降。

### Deep Dive 4: Consistency — Cache 与 DB 同步

**问题**：写完 DB 后，缓存什么时候更新？

**4 种 pattern**：

1. **Cache-aside (默认推荐)**：先写 DB，再 invalidate cache。下次 read 自然重建。✅ 简单
2. **Write-through**：同时写 DB + cache。强一致，但写延迟 = max(DB, cache) ❌ 慢
3. **Write-back / write-behind**：先只写 cache，异步刷 DB。⚠️ 数据丢失风险
4. **Read-through**：cache miss 时 cache 自己去查 DB。客户端代码简化。需要 cache 知道 DB schema。

**实战 race condition**：
- T1: app 读 cache miss → 查 DB 得旧值 v1
- T2: app 写 DB v2 → invalidate cache
- T1: 把 v1 塞进 cache  ← **脏数据！**

**解法**：写 DB 时附带 version，read-rebuild 用 CAS（compare-and-swap）：
```python
def rebuild_cache(key):
    val, ver = db.read(key)
    cache.set_if_version(key, val, ver)  # 只在 ver 是最新时才 set
```

### Deep Dive 5: Multi-region Consistency

**单 region**：一致性好控制。
**多 region**：必然有 lag，要选 trade-off。

**3 种 multi-region 模型**：

1. **Active-passive (single writer)**：所有 writes 都路由到主 region，其他 region 是 read-only follower。简单，读延迟低，写延迟高（跨洋）。
2. **Active-active (multi-writer LWW)**：任何 region 都能写，按 wall-clock timestamp 解冲突（last-write-wins）。⚠️ 时钟漂移会丢数据。
3. **Active-active (multi-writer CRDT)**：用 G-Counter / OR-Set 等数据结构，**任何写入顺序都能 merge 到一致结果**。复杂但严格正确。

**Google Spanner 风格**：TrueTime API 给跨 region 时钟边界，配合 Paxos 做强一致。**少见**。

**STAFF 答**：active-passive 是 default；遇到全球读写均衡时考虑 active-active LWW；强一致需求才上 CRDT / Spanner。

### Deep Dive 6: Memory Layout

**TLB-friendly 设计**：

- **小 object 用 jemalloc pool**：减少碎片
- **大 value（>4KB）外存**：放 SSD，cache 只存 pointer
- **Hash table 设计**：Robin Hood hashing 减少探测次数

**LRU 链表的优化**：用 **segmented LRU**（hot / cold 两段），减少 mutex 争抢。

### Deep Dive 7: Failover

Primary 挂了怎么自动切？

**Redis Sentinel 模式**：
- 3+ Sentinel 进程监控所有 primary
- Sentinel 互相 gossip 检测心跳
- 多数 Sentinel 认为 primary 挂 → 选出一个 replica 提升为 primary
- 更新所有 client 的 routing 表

**问题**：split-brain（脑裂）—— 网络分区时两边都选自己当 primary，写入冲突。

**解法**：要求至少 **majority (N/2+1)** 同意才能 promote。Raft 的标准。

---

## 7. 45 分钟面试节奏

| 时间 | 阶段 | 你要做 |
|---|---|---|
| 0-5min | 澄清 + 需求 | 5 个 API，5 个 NFR 全列出 |
| 5-10min | 容量估算 | QPS / 内存 / 网络 全算 |
| 10-15min | API 设计 | 5 个 endpoint，注意 idempotent |
| 15-25min | 高层架构 | step 1→6 一步步演 |
| 25-40min | Deep Dives | hot key + thundering herd + eviction + consistency 至少 3 个 |
| 40-45min | Follow-up | failover / multi-region / monitoring |

**节奏 tips**：
- 容量估算别超 5 分钟，别在数字上纠结，**说出"100 台、3x replication、p99 5ms"就够**
- 高层架构要 incremental：先 single node → 暴露问题 → sharding → 暴露问题 → consistent hashing → ...
- 不要一上来就画 Redis Cluster 全图，**给面试官追问的空间**

---

## 8. 样板讲解稿（可背 60%）

> 这是一道经典的分布式系统题。我会按"先确认需求 → 估容量 → 单机原型 → 逐步扩展 → deep dive trade-offs"的顺序来讲。
>
> **需求**：核心 5 个 API：`GET/SET/DELETE/EXPIRE/INVALIDATE`。非功能上，**low latency** 是缓存存在的全部意义，所以 p99 我会按 5 ms (single region) / 50 ms (cross region) 来设计。我们的 source of truth 是 DB，所以**持久性放最低**，能容忍 cache 数据丢失。
>
> **容量**：假设 1B DAU、每用户每天 100 read + 10 write，peak 3.5M reads/s 和 350k writes/s。100B distinct keys × 1KB value，热数据 (top 20%) 约 23 TB → 90 台 256 GB 机器 × 3 replication = 270 台。
>
> **演进**：从单机 Redis 开始 → 内存不够要 sharding → 用 `hash % N` 会 rebalance 灾难 → 上 **consistent hashing** with virtual nodes → 单点故障 → 每 shard 加 2 replicas + Sentinel failover → 缓存怎么跟 DB 配合 → **cache-aside pattern**：写时 invalidate（不是 update），读时 miss 重建。
>
> **Deep dive 1 - Hot key**：识别用 Count-Min Sketch + 阈值。解法用 sharded hot key（拆成 `key_v1..key_v10`）+ replica 全 copy。
>
> **Deep dive 2 - Thundering herd**：jitter TTL + singleflight + probabilistic refresh，三层。
>
> **Deep dive 3 - Eviction**：默认 approximate LRU（Redis 采样 5 个），高端场景上 W-TinyLFU。
>
> **Multi-region**：默认 active-passive（写主 region），如果需要全球写均衡再上 active-active LWW。
>
> 不知道时间到了没，我准备好回答任何 deep dive。

---

## 9. Follow-up Q&A 预演

### Q1: "如果 Redis 进程崩了，缓存数据全丢，会发生什么？"

**A**：典型的 **cache cold start**。所有请求 miss → 全打到 DB → DB 瞬间过载（thundering herd 的极端形态）。

**保护方案**：
1. **Cache warming**：从 backup 或 replica 提前预热
2. **Connection pool 限流**：app 端限制单机到 DB 的并发，超过的 fail-fast
3. **Circuit breaker**：DB 压力大时直接 fail，让上游 fallback 到静态数据
4. **Replicas 永远不要全挂**：跨 AZ / region 部署

### Q2: "怎么知道你的 cache hit rate 是多少？"

**A**：
- 每个 cache node 自带 metric：`hits / (hits + misses)`
- 上报到 Prometheus → Grafana 画图
- alert 阈值：cache hit rate < 80% 报警（每个业务不同）
- 长期分析：哪些 key prefix hit rate 低？要不要 pre-warm / 改 TTL？

### Q3: "你说 invalidate 而不是 update，那如果 invalidate 失败了呢？"

**A**：经典的"双写问题"。

**两段式提交也不能完全避免**。实战中：
1. **Cache 写失败**：直接返回 5xx，让客户端 retry（最简单）
2. **DB 写成功 + cache invalidate 失败**：靠 TTL 兜底（设短一点，e.g. 5 分钟）
3. **强一致需求**：上 **Change Data Capture (CDC)**，监听 DB binlog，由专门 worker invalidate cache。Debezium / Maxwell。

### Q4: "Memcached vs Redis，怎么选？"

**A**：
- **Memcached**：极简，纯 key-value，多线程（单进程多核），无持久化，无 replication（要靠 client 端 sharding）。**适合：纯加速 layer，对 feature 没要求**
- **Redis**：丰富数据结构（list / set / sorted set / hash / stream），单线程（v6+ 部分多线程），有持久化、replication、Cluster。**适合：要 sorted set 排行榜 / pub-sub / 复杂结构**

实战：90% 选 Redis，因为运维生态成熟、官方支持 Cluster。**Memcached 现在主要是历史包袱**。

### Q5: "Consistent hashing 加机器只挪 1/N 数据，但具体怎么挪？运行期间业务怎么办？"

**A**：分 3 步：
1. **新机器接入环**，但**不接受流量**
2. **后台 migration**：扫描旧机器上属于新机器的 key，复制过去
3. **migration 完成后**：原子切换 routing，老机器删数据

**关键**：双写期间，写要**同时写到新 + 旧**，避免 migration 期间数据丢。Redis Cluster 的 `MIGRATE` 命令做这个。

### Q6: "如果一个 key 的 value 是 100 MB，会有什么问题？"

**A**：**Big value problem**。
- **网络阻塞**：100 MB / 1 Gbps NIC = 800 ms 传输，期间 socket 阻塞
- **内存压力**：单条占用过大，挤压其他 key
- **eviction 异常**：删一个就空出巨大空洞

**解法**：
- **chunking**：客户端分块，每个 chunk < 1MB
- **external blob storage**：value 存 S3，cache 只存 URL
- **限制 value 大小**：server 端拒绝 > 1MB 的写入

### Q7: "怎么测试你的 cache 系统？"

**A**：
1. **Unit**：每个组件（LRU / consistent hash）单测
2. **Chaos**：用 Chaos Monkey 随机杀 primary，看 failover 时间 + 数据正确性
3. **Load test**：用 `redis-benchmark` 或 `memtier_benchmark` 跑 1M QPS，看 p99 是否达标
4. **Soak test**：连跑 24h，看内存 leak / latency drift
5. **Jepsen**：分布式一致性测试黄金标准，注入网络分区检查不变量

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **一上来就画 Redis Cluster 全图** —— 没有演进过程，面试官觉得你只会 copy 现成方案
2. **忽略 hot key** —— 这是 STAFF 必追问的，没准备直接挂
3. **Cache update 而不是 invalidate** —— 暴露你不懂 race condition
4. **持久性说成必要** —— 缓存的定义就是"可丢"，搞混 cache 和 DB
5. **忘记 multi-region** —— Google 是全球公司，必问
6. **Memcached vs Redis 答不出区别** —— 暴露你只用过其中一个
7. **Eviction 只会说 LRU** —— 没说 LFU / W-TinyLFU 显得肤浅

### ✅ 加分项

1. **量化所有 trade-off**：说"sharding 加机器要挪 1/N 数据"比"会挪一些"高 10 倍
2. **主动提 Count-Min Sketch detect hot key**：展示你懂近似算法
3. **CDC + cache invalidation**：展示你跨过简单 cache-aside 看 industry pattern
4. **TrueTime / Spanner 提一嘴**：Google 内部技术，加分
5. **W-TinyLFU**：现代 cache 算法，比 LRU 强很多
6. **CRDT for multi-region**：展示你懂分布式数学
7. **画图时主动标 latency**：每个箭头标 1ms / 5ms / 50ms，体现你**思考过性能**

> [!key] **STAFF 跟 SENIOR 的差别**：
> SENIOR 答"how" —— 我会用 consistent hashing + replication。
> STAFF 答"why + when + alternatives" —— consistent hashing 解决 rebalance 问题，付出 virtual nodes 的额外内存代价；如果数据量小（< 1TB），直接用 hash mod N + 定期 manual rebalance 更简单。

---

## 11. 最后 5 分钟 cheat sheet

如果只剩 5 分钟看一遍，记住这些：

```
核心 trade-off:
  - sharding: consistent hashing + virtual nodes
  - replication: 3 replicas, single primary, Sentinel failover
  - cache pattern: cache-aside + invalidate (not update)
  - eviction: approximate LRU (Redis) / W-TinyLFU (Caffeine)
  - hot key: sharded key + replica replication
  - thundering herd: jitter TTL + singleflight
  - multi-region: active-passive default
  - consistency: eventual, source of truth = DB

数字:
  - p99 latency: 5 ms (single), 50 ms (cross)
  - QPS / node: 100k (Redis单核)
  - 1B DAU → 23TB hot data → 270 台 256GB

关键概念:
  - cache-aside pattern
  - consistent hashing
  - Count-Min Sketch (detect hot)
  - W-TinyLFU
  - CDC for invalidation
```
