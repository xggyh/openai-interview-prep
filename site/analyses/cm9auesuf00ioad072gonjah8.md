## 0. 在开始之前 — 你需要知道的概念

如果你是 System Design 新手，先理解下面几个名词，后面就好懂了。

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Denylist / Blocklist** | 黑名单 —— 一个列表，记录哪些 IP / user / URL 不能访问 | 门卫的"禁止入内"名单 |
| **API Gateway / Edge** | 用户请求进入系统的"前门"。所有流量先到它，它再决定转给后面哪个服务 | 大楼前台 |
| **Cache** | 临时存"热"数据的快速存储。读起来比真 DB 快 100x | 你桌上的便条 vs 档案室 |
| **Redis** | 一个流行的内存 cache，常用作"分布式 cache" | 整层楼共用的白板 |
| **Bloom filter** | 一个超省内存的"集合"数据结构。能快速判断"X **可能**在集合里" 还是 "X **绝对**不在集合里" | 邮筒口的网格 —— 大物件肯定塞不进 |
| **CDN** | Content Delivery Network。把数据**复制到全球多个机房**，用户从最近的取 | 麦当劳全球开店 |
| **DB (Database)** | 永久存储数据的地方。慢，但靠谱 | 档案室 |
| **CDC** | Change Data Capture —— DB 变化了自动通知其他系统 | "档案改了打电话给我" |
| **Kafka** | 一个超快的消息队列。生产者 push 进去，消费者从里面 pull | 流水线传送带 |
| **Audit Log** | 审计日志，记录"谁做了什么"，不可修改 | 银行的录像监控 |

读到具体段落时遇到不懂的名词，回来这里查。

---

## 1. 题目本质 — 这是什么问题

**Distributed Blocking / Denylist System** = 一个**反作弊 / 安全防护服务**。

**最简单的场景**：用户登录时，你的服务问"这个 IP 在黑名单里吗？"。如果是 → 拒绝；不是 → 放行。

**为什么需要分布式**：

- 你的产品有 **10 亿用户**，分布**全球**
- 每秒可能有 **100 万**这种 "is_blocked?" 查询
- 黑名单本身有 **1 亿条** 记录（被检测的恶意 IP / 被封禁的 user / 钓鱼 URL）
- 黑名单需要**秒级更新**（admin 加了一个新 IP，全球所有 server 1 分钟内都得知道）

**核心矛盾**：
- 黑名单太大放不进一台机器
- 查询太多走单点 DB 会死
- 数据要全球同步又要尽快

这道题在 Google 报告 5 次，是这次数据里 **System Design 最热的题之一**。它是反作弊 / safety / abuse prevention 类系统的简化版。

---

## 2. 需求拆解 — 面试第一步要问什么

**新手最大的错误**：听到题目立刻开始画架构图。**正确做法**：先问 5 分钟问题，把题目边界搞清楚。

下面是"面试官说题"后你应该问的问题（带样板回答，方便记）：

### 2.1 功能性问题（What does the system do?）

**你问**：黑名单条目都有什么类型？只 IP？还是 user_id / device / URL 都有？  
**典型答**：多种 type（IP, user_id, device_id, URL, phone, email）。每个 entry 有 `(type, value)`。

**你问**：是只查询（is_blocked），还是也支持增删（block / unblock）？  
**典型答**：都支持。Admin 后台 + ML auto-block + API 都可能写。

**你问**：黑名单条目要不要 TTL（自动过期）？  
**典型答**：要。有些 block 是临时的（24h ban），有些永久。

**你问**：要不要 audit log？比如"谁什么时候 block 了 X，为什么"？  
**典型答**：必须有。合规要求。

### 2.2 非功能性问题（How big? How fast?）

**你问**：QPS 量级？  
**典型答**：read（is_blocked）1M+ QPS；write（block / unblock）几 k QPS。  
👉 **观察**：read 远超 write —— 这告诉我们要做 **read-heavy optimization**（缓存为主）。

**你问**：延迟要求？  
**典型答**：is_blocked **P99 < 5ms**。原因：这个 check 在每个用户请求的关键路径上，慢了所有 API 都慢。

**你问**：黑名单总量？  
**典型答**：当前 100M entries，3 年内可能 1B。

**你问**：block 操作多久要全球生效？  
**典型答**：< 1 分钟。Admin 不能容忍 "我封了一个 IP 5 分钟后它还能登录"。

**你问**：有多少 region？  
**典型答**：全球 5+ region (US-East / US-West / EU / APAC / SA)。

### 2.3 整理需求清单

最后总结给面试官看（让 ta 知道你听对了）：

```
功能：
- is_blocked(key, type) → bool       【主接口，read-heavy】
- block / unblock(key, type, reason, ttl?)
- list / search / audit query
- 多 type、TTL、audit log

非功能：
- 100M-1B entries
- 1M QPS read (P99 < 5ms)
- 几 k QPS write
- 全球 5 region，block 1 min 内生效
- 99.99% availability
```

> [!key]
> 这一步是新手最容易跳过的，但**面试官会主动看你问什么问题**。一个好的 SD 候选人 5 分钟内问出关键约束，比一个 30 分钟堆架构的候选人评价高。

---

## 3. 容量估算 — 学会算 numbers

这一步**新手容易紧张**，但其实就是一道乘除法应用题。建议**当面口算 + 写白板**，过程比结果重要。

### 3.1 read QPS

```
1M QPS = 10^6 个 / 秒
每个 check 涉及一次 lookup
```

→ 1M ops/sec 是 hot path。**Redis 单实例约能撑 50k-100k QPS**，所以需要 **10-20 个 Redis 实例** 才能撑（或者用 Bloom filter 先过滤一部分，下面会讲）。

### 3.2 write QPS

```
几 k QPS = ~1000-5000 ops/sec
```

→ 一台 Postgres 单机能撑 10k+ writes，所以单 DB 写够用。**不是 bottleneck**。

### 3.3 存储

```
100M entries × 平均 200 字节/entry (key + metadata + reason + timestamps)
= 20 GB
```

→ 单台 server 内存 64 GB 装得下！这是个**重要观察** —— 全量黑名单可以全 cache 在内存里。

未来扩到 1B entries → 200 GB → 需要分片到 4-8 台机器。

### 3.4 网络

```
1M QPS × 平均 100B response 
= 100 MB/sec = 800 Mbps
```

→ 单台 10Gbps 网卡足够。多 region 各自 serve 本地流量更好。

### 3.5 Bloom filter 大小（你后面会理解为什么算这个）

```
100M entries，false positive rate 0.1%
→ ~14 bits/entry × 100M = 1.4 Gbit = 175 MB
```

→ Bloom filter **175 MB 能装到每个 service instance 内存里**！这是 design 关键。

### 3.6 整理估算清单

```
read: 1M QPS, P99 < 5ms       → 需要分层 cache
write: 几 k QPS                → 单 DB OK
存储: 20 GB → 1 TB             → 全量可装一两台机器
Bloom filter: 175 MB           → 每个 service instance 都装得下
```

---

## 4. 整体架构 step by step

**新手常犯的错**：一上来画一个 10 个 box 的复杂图。**正确做法**：从最简单的开始，每加一层都解释"为什么"。

### 4.1 第 0 步：最朴素的方案

```ascii
    User request
         │
         ▼
    ┌──────────┐
    │ Service  │ ─── SELECT 1 FROM denylist WHERE key=? AND type=?
    └──────────┘     ↓
                ┌──────────┐
                │   DB     │
                └──────────┘
```

**问题**：
- 1M QPS 每个查询都打 DB → DB 死。
- 全球用户跨洋查美国 DB → 200ms 延迟，远超 5ms 要求。

### 4.2 第 1 步：加一层 Redis cache

```ascii
    User
     │
     ▼
   Service ──→ Redis ──→ (miss) ──→ DB
            ↑
            热数据命中后不必再查 DB
```

**为什么 Redis**：内存存储，read 50-100k QPS per instance，延迟 0.5ms。

**新问题**：
- 1M QPS / 100k per Redis = 至少 10 个 Redis instance（Redis Cluster）
- 还是要先 hit Redis，每次都查 Redis 比直接判断慢

### 4.3 第 2 步：加 Bloom filter（神器！）

**新手问**：Bloom filter 是什么？

**直观理解**：Bloom filter 是一个**超省内存**的"集合"。它能回答两类问题：
- "X **可能**在集合里" → 不确定，得继续查 Redis 确认
- "X **绝对不**在集合里" → 100% 确定，直接判通过

**它怎么做到的**：用 N 个哈希函数把每个 entry 散到 bit array 的 N 个位置上。查询时如果**所有** N 个位置都是 1 → 可能在；任一是 0 → 绝对不在。

**对这道题的妙用**：99% 的请求是"is_blocked(普通 user)" → 答案是 **No**。

```
没有 Bloom filter：99% 请求都要查 Redis 一次
有 Bloom filter：99% 请求 Bloom 直接说 "不在"，0.5μs 解决
```

**Bloom filter 在哪里**：直接放在每个 service instance 的**进程内存**里。175 MB / instance，完全可以。

```ascii
    User → Service ─→ Bloom filter check (in-process, 0.5μs)
                          │
                  ┌───────┴────────┐
                  ▼                 ▼
              "绝对不在"        "可能在"
              (99% 流量)         (0.5% 流量 +
              直接 return False  少量 false positive)
                                    │
                                    ▼
                                  Redis ──→ (miss) ──→ DB
```

> [!key]
> 这是这道题最巧的地方！Bloom filter 把 1M QPS 中 99% 在 service 进程内 0.5μs 就解决了。Redis 只需处理 1% = 10k QPS，远低于它的能力。这就是**多层缓存**的思想。

### 4.4 第 3 步：处理 write + 全球同步

我们还没解决：**admin block 一个 IP 后，怎么让所有 region 的 service 都知道？**

```ascii
    Admin → API → DB (Spanner)
                       │
                       │ CDC (change data capture)
                       ▼
                   Kafka topic: denylist.events
                       │
                  ┌────┼─────┬─────┬─────┐
                  ▼    ▼     ▼     ▼     ▼
               每 region 的 updater  (US-E US-W EU APAC SA)
                  │
                  ▼
               Regional Redis update + 通知 service instance
               更新 Bloom filter 加入新 entry
```

**为什么这条链路**：

1. **DB 是 source of truth**：永远以它为准
2. **CDC** 让 DB 写完自动 emit 一个 event 到 Kafka
3. **Kafka** 分发到每个 region 的 updater
4. Updater 更新 region 内的 Redis + 通知 service instance 更新本地 Bloom

**延迟分析**：
- API write → DB ~10ms
- DB → CDC → Kafka ~1s
- Kafka → region updater → Redis ~500ms
- Service instance Bloom 刷新 ~3-5 分钟（用 TTL，不必实时）

→ **总：1 分钟内全球生效**（满足需求）

### 4.5 完整架构

```ascii
    ┌──────────────────────────────────────────────────┐
    │  Apps / Services (全球)                          │
    │  ┌────────────────────────────────────────────┐  │
    │  │ Bloom filter (175MB in-memory) + LRU cache │  │
    │  └────────────────┬───────────────────────────┘  │
    └───────────────────┼──────────────────────────────┘
                        │ Bloom miss / "maybe" 才往下查
                        ▼
                ┌────────────────────┐
                │ Regional Redis     │  ← 全量黑名单缓存（按 region）
                │ Cluster            │
                └─────────┬──────────┘
                          │ Redis miss 才查 DB（少见）
                          ▼
                ┌────────────────────┐
                │ Denylist API +     │  ← write 入口
                │ Spanner (source    │
                │ of truth)          │
                └─┬────────────────┬─┘
                  │                │
                  │ CDC            ▼
                  ▼          ┌─────────────────┐
              ┌────────┐    │ Audit Log       │
              │ Kafka  │    │ (Append-only)   │
              │ topic  │    └─────────────────┘
              └───┬────┘
                  │
        ┌─────────┼──────────┬─────────┐
        ▼         ▼          ▼         ▼
     Per-region updater → Redis + service Bloom refresh
```

---

## 5. 每个组件深挖

### 5.1 Data model（DB schema）

```sql
CREATE TABLE denylist_entries (
  id           UUID PRIMARY KEY,
  entity_key   TEXT NOT NULL,           -- e.g. "1.2.3.4" 或 "user_abc"
  entity_type  TEXT NOT NULL,           -- 'ip' / 'user' / 'device' / 'url' / 'phone' / 'email'
  reason       TEXT,                    -- 人类可读的封禁原因
  source       TEXT,                    -- 'admin' / 'ml' / 'user_report'
  created_at   TIMESTAMPTZ DEFAULT now(),
  expires_at   TIMESTAMPTZ,             -- NULL = 永久封禁
  status       TEXT NOT NULL,           -- 'active' / 'revoked'
  created_by   TEXT,
  metadata     JSONB
);

-- 关键索引：按 (type, key) 查最快
CREATE UNIQUE INDEX idx_entity ON denylist_entries(entity_type, entity_key) 
WHERE status = 'active';

-- TTL 过期清理需要这个索引
CREATE INDEX idx_expires ON denylist_entries(expires_at) 
WHERE expires_at IS NOT NULL;
```

**新手 question**：

❓ **为什么用 UUID 而不是 auto-increment？**  
分布式系统多 region 写 → auto-increment 容易冲突。UUID 全球唯一。

❓ **为什么有 `status='revoked'` 而不是直接 DELETE？**  
**Soft delete**。审计要求 —— 谁封了谁、什么时候、为什么、什么时候解封了，全部历史保留。物理删除不可逆。

❓ **为什么 `(type, key)` 一起作 UNIQUE 索引？**  
因为 `"1.2.3.4"` 可以同时是某 IP 和某用户的 ID（极端情况）。`(type, key)` 一起才唯一。

### 5.2 API 设计

```http
# 查询
GET /v1/denylist/check?type=ip&key=1.2.3.4
→ 200 { "blocked": false }
→ 200 { "blocked": true, "reason": "spam", "expires_at": "..." }

# 添加
POST /v1/denylist
{ "type":"ip", "key":"1.2.3.4", "reason":"spam", "ttl_seconds":86400 }
→ 201 { "id": "...", "created_at": "..." }

# 解封
DELETE /v1/denylist/{id}
→ 204

# 列表（admin 用）
GET /v1/denylist?type=ip&active=true&limit=100&cursor=...
→ 200 { "entries": [...], "next_cursor": "..." }
```

> [!key]
> 注意：查询接口**返回 reason 和 expires**，不是只返回 true/false。这样客户端能给用户看友好提示（"你被临时封禁到 X 时间，原因 Y"）而非冷冰冰 "Access Denied"。

### 5.3 Bloom filter 深讲

这部分新手最容易混淆，所以详细讲。

**Bloom filter 是什么**：一个 **bit array**（很长的二进制位串） + **N 个哈希函数**。

**插入元素 X**：
1. 算 N 个哈希值 `h1(X), h2(X), ..., hN(X)`
2. 每个哈希值对 bit array 长度取模 → 得到 N 个位置
3. 把这 N 个位置都 set 为 1

**查询元素 X**：
1. 算 N 个哈希值，得到 N 个位置
2. 看这 N 位是不是**都**是 1
3. 都是 1 → "可能在"。任一是 0 → "绝对不在"。

**为什么是"可能"而不是"确定"**：因为不同元素可能哈希到同样的位置（碰撞）。Y 没插入过，但 Y 的 N 个位置可能被其他元素都"撞"成了 1。

**计算大小**：

```
N entries, false positive rate p
bit array size m = -N × ln(p) / (ln 2)^2
hash count k = (m/N) × ln 2

例：100M entries, p=0.1% (0.001)
m = -100M × ln(0.001) / 0.48 = 1.44 Gbit ≈ 175 MB
k = 14.4 / 0.69 ≈ 7 hash functions
```

→ **175 MB 装下 100M entries 的 Bloom filter，错判率 0.1%。**

**对我们这道题的好处**：

```
1M QPS check
99% 请求 "不在黑名单" (good users)
  → Bloom filter 直接返回 "不在" 99% × 1M = 990k QPS 0.5μs 解决
0.1% Bloom false positive
  → Bloom 说"可能在"，往下查 Redis 确认 (~0.1% × 1M = 1k QPS)
0.9% 真的在黑名单
  → Bloom 说"可能在"，往下查 Redis (~9k QPS)

Redis 实际负载 = 10k QPS（远低于 1M！）
```

**Bloom filter 怎么更新**：

- 启动时从 Redis 加载完整 Bloom（5 分钟一次重建是 OK 的）
- 新 block 来时 Kafka 通知，每个 instance 增量 add 到 Bloom
- 解封：Bloom 不支持 delete！但没关系 —— 解封后 false positive 会让请求多查一次 Redis，Redis 说"不在"。**Bloom 每 6 小时全量重建**清除已解封 entry。

> [!key]
> Bloom filter 设计是**只允许"宁可错怪"，不能"漏抓"**。误判"可能在"会被 Redis 兜底，损失只是多一次查询。但如果"漏抓"就会让被 block 的 IP 通过，违反业务。所以 Bloom 单向 OK。

### 5.4 Cache strategy

```
Layer 1: Service in-process Bloom + LRU cache
  - Bloom: 175 MB, 全量黑名单近似集合
  - LRU: 最近 10k key 的完整结果（key, blocked? reason）
  - 命中率：99.5%+

Layer 2: Regional Redis cluster
  - 完整黑名单 (sharded across 10 nodes)
  - 命中率：~99% of L1 miss
  - 延迟：~1ms

Layer 3: Spanner (source of truth)
  - 所有 cache miss 都 fallback 到这里
  - 延迟：10-50ms (跨 region 可能更高)
```

### 5.5 为什么 Spanner 做 source of truth

可能的选择：Postgres, MySQL, Cassandra, DynamoDB, Spanner.

| 选项 | 强一致 | 全球分布 | 写吞吐 | 取舍 |
|---|---|---|---|---|
| Postgres | ✓ | ✗ | 中 | 单 region 强，跨 region 弱 |
| MySQL + 读副本 | 主写强一致 | 副本弱 | 中 | 读副本读 stale 数据 |
| Cassandra | ✗（最终一致） | ✓ | 高 | admin block 后 dashboard 短期看不到 |
| DynamoDB | ✓ | 单 region 强；多 region 异步 | 高 | AWS 锁定 |
| **Spanner** | **✓（全球强一致）** | **✓** | **高** | 贵但符合需求 |

**关键考量**：admin block 一个 IP，立即在 dashboard 看到 status 变化。这要求**强一致**。Cassandra 这种 eventual consistency 会让 admin 困惑（"我刚 block 了，怎么 UI 还显示 active？"）。

Spanner 适合：全球强一致 + transaction（block + audit log 同 transaction）。

### 5.6 全球同步路径详细

```ascii
admin clicks "Block" in dashboard
   │
   ▼
   POST /v1/denylist
   │
   ▼ ┌────────────────────────────────────────────────┐
     │ Inside Spanner transaction：                    │
     │  1. INSERT denylist_entries (type, key, ...)   │
     │  2. INSERT audit_log (action='block', ...)     │
     │ Both commit atomically                          │
     └────────────────────────────────────────────────┘
   │
   ▼ T+10ms: API returns success
   ▼
   Spanner CDC stream emits event
   │
   ▼ T+1s: arrives at Kafka topic denylist.events
   ▼
   Each region's "Updater" service subscribes
   │
   ▼ T+1.5s: writes to regional Redis
   ▼
   Region's service instances eventually pick up
   (next Bloom refresh cycle, max 5 min)
   │
   ▼ T+max 1 min: 全球生效
```

> [!key]
> 这就是面试官常问的 "eventual consistency" 的实际表现 —— 局部强一致 (Spanner write + read 立刻看到)，全球最终一致 (1 分钟内传播完)。

---

## 6. 面试节奏 — 45 分钟怎么讲

这是新手最缺的能力。下面是一份**节奏指南**。

```
0:00 - 0:05  Clarifying Questions
  - 问 4-6 个关键问题（参考第 2 节）
  - 写下需求清单
  - 关键：让面试官知道你在听 + 在思考

0:05 - 0:10  Capacity Estimation
  - 算 QPS, storage, network 三个数
  - 一边说一边在白板/note 上写
  - 关键：把"假设"写出来（"假设每条 entry 200 B"）

0:10 - 0:15  High-Level Architecture
  - 画一个简单 box+arrow 图（4-6 个 box）
  - 不要立刻深入细节
  - 关键：让面试官跟上整体流程

0:15 - 0:30  Deep Dive
  - 选 2-3 个关键组件深挖
  - 对这题：Bloom filter / Cache strategy / 全球同步
  - 关键：展示 trade-off 思维（"我选 X 因为 Y，但代价是 Z"）

0:30 - 0:38  Follow-ups
  - 面试官会主动追问（参考第 8 节）
  - 关键：reasoned answer，不要 hand-wave

0:38 - 0:45  Wrap-up
  - 总结：3 大设计决策 + 改进 ideas
```

**新手注意**：很多人 0:05 时就开始画架构图。**坚持先问 5 分钟问题**。面试官扣你时间的可能性 < 你乱画错方向的损失。

---

## 7. 面试样板讲解（你可以直接背一段）

下面是一段"如果我是候选人，我会怎么讲"。**注意我做的两件事**：(a) 不断 check-in 问面试官（"这样设计合理吗？"）；(b) 主动 verbal 提到 trade-off。

> "好的，让我先确认一下需求。这是个 denylist 服务，主要是 is_blocked 这种 read-heavy lookup，对吧？... 那 read 比 write 多多少？... 1M vs 几 k QPS，那确实是 read-heavy 99%+。OK。
> 
> 我做几个估算：1M QPS read，每个 entry 大概 200 字节，100M entries 是 20GB —— 单机内存装得下，这点很有用。延迟 P99 < 5ms 是关键，意味着不能每次都打 DB。
> 
> 整体思路是**三层缓存**：service 内部 Bloom filter + 本地 LRU；regional Redis；中心 Spanner。让我画一下...
> 
> 关键在 Bloom filter。99% 的请求是好用户，Bloom 能在 0.5 微秒说'绝对不在'，根本不打 Redis。这把 1M QPS 削减到 10k QPS 到 Redis。Bloom 175MB 装进每个 service instance 完全没问题。
> 
> 当然 trade-off 是 Bloom 不支持 delete。所以 unblock 后 Bloom 还会偶尔 false positive，但那只是多查一次 Redis 而已，不会出错。每 6 小时重建一次 Bloom。
> 
> 接下来全球同步。我用 Spanner 做 source of truth，因为 admin 需要写完立刻在 UI 看到，最终一致性会让 admin 困惑。Spanner write → CDC → Kafka → 每 region 的 updater 同步 Redis。整个链路 < 1 分钟。
> 
> 这样 OK 吗？还有什么想深入挖的？"

---

## 8. Follow-up 演练（必背！）

面试官常追问，准备好这些。

### Q1: 如果某个 region 的 Redis 全挂了？

**答**：Service instance 的 Bloom filter 仍然能 serve 99% 请求（绝对不在黑名单的）。剩下 1% Bloom 说"可能在"的，fallback 到 Spanner（虽然慢，但可用）。这是**graceful degradation**。

### Q2: Bloom filter 怎么 detect 一个新 block？

**答**：每个 Kafka event 到 service instance，instance add 到本地 Bloom（Bloom add 是 O(k)，毫秒级）。同时 LRU 缓存也 invalidate 这个 key。

### Q3: 怎么防止有人恶意大量 block 好用户（denial of service via blocking）？

**答**：(a) Admin block 需要 dual approval；(b) ML auto-block 设 confidence threshold，低 confidence 进 review queue；(c) 每个 source（admin / ML / user report）有 quota；(d) Block 后 5 分钟有"自动 sanity check" —— 如果该 entity 突然完全没流量了（被错杀），可疑，alert。

### Q4: 怎么处理 prefix-based blocking（如某域名 + 子域名都封）？

**答**：denylist_entries 增加 `is_prefix` 标志。Service check 时除了精确查 key，还要查所有可能 prefix。Trie 数据结构 + Bloom filter 一起用：Bloom 仍 dedup 大部分非黑用户，Trie 帮助匹配 prefix。

### Q5: 怎么处理 GDPR 删除请求（user 要求删除所有他被记录的数据）？

**答**：denylist 不存 PII（只存 hash 后的 user_id）；如果 user 要求被遗忘，逻辑删除 + 加密下沉（永远 unblocked）。Audit log 保留但匿名化。

### Q6: 如果 Spanner 跨 region 写延迟太高怎么办？

**答**：write API 可以**异步化** —— admin 提交 block，API 立刻返回 "accepted"，后台 Spanner write + 同步。代价：admin 1-2 秒后才能在 UI 看到。trade-off：是要 admin click 后立刻可见（同步），还是要更高 write 吞吐（异步）？根据 product priority 选。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **只用一层 Redis cache**，没 Bloom filter —— 1M QPS / 100k 每 instance = 10+ Redis instance 同时跑，还是受限 + 网络往返延迟无法 < 5ms；  
> ❌ **用 Cassandra / DynamoDB eventual consistency** 做 source of truth —— admin block 后 UI 等几秒才更新，体验差且让 admin 怀疑系统坏了；  
> ❌ **Bloom filter 加完不重建** —— unblock 后 Bloom 留下"幽灵 entry"，false positive 率会慢慢爬高；6 小时重建是工业实践；  
> ❌ **不做 audit log** —— 合规失败，无法追溯"谁封了谁"；  
> ❌ **delete entry 直接物理删** —— 失去历史，无法回溯；  
> ❌ **Block propagation 用 DB polling 而非 CDC + Kafka** —— DB 被周期扫描打挂；  
> ❌ **不区分 hot / cold storage** —— 把 5 年前老 audit 数据也放 Spanner，成本爆炸；  
> ❌ **不限制 admin 单次操作 scope** —— 一个 admin 误操作 block 一个大用户群（如 /16 IP 段），1 分钟内全球用户被打挂。

---

## 10. 加分项（如果面试官问 "What else?"）

- **ML auto-block**：连入 fraud detection model 自动 block 高 confidence 的恶意 entity
- **Rate limit on block API itself**：防止 buggy code 触发批量误 block
- **Multi-tenant**：SaaS 客户各自的 denylist，per-tenant isolation
- **Geo-aware**：某 IP 段只对 EU 用户封禁（compliance / regional difference）
- **Self-service unblock**：用户被错封后可申诉，触发 manual review
- **Cost optimization**：Hot Spanner 存最近 90 天，旧 entries 归档到 BigQuery 便宜存

---

## 11. 总结：你应该记住的 3 件事

1. **Read-heavy 系统的核心 = 多层缓存** (Bloom → in-process LRU → Redis → DB)。这道题 Bloom 是关键，把 99% 流量在 service 进程内 0.5μs 解决。

2. **写路径的 trade-off = 一致性 vs 延迟**。Spanner 强一致但贵；Cassandra 便宜但 eventual。Admin-facing 系统要强一致，end-user-facing 系统经常可以接受 eventual。

3. **全球同步 = source of truth + CDC + Kafka + per-region cache**。这是 Google / Meta / FAANG 内部几乎所有"全球一致数据"问题的标准答案，要熟练画出。

> [!followup]
> **学习推荐**：(a) 自己用 Python 实现一个简单 Bloom filter（30 行代码，understanding > using）；(b) 读一下 Redis 的 sharding doc 理解 cluster mode；(c) 读 Spanner paper section 3-4，理解全球强一致是怎么用 TrueTime API 做到的；(d) 准备 3 个不同公司的 denylist / safety 实例（Google Safe Browsing, Cloudflare WAF, Stripe Radar），对比设计差异。
