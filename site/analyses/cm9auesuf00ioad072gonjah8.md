## 题目本质

设计 **Distributed Blocking / Denylist System**：百万用户级 anti-abuse / safety service。给一个 entity（IP / user_id / device_id / URL），快速判断是否在 denylist。同时支持**全球低延迟 read** + **管理员实时增删 entries**。

Google 报告 45 人，是这次最热的 SD 题。考点：**hot read path + globally distributed cache + audit trail**。

## 需求拆解

**功能性：**
- `is_blocked(entity_key, type) → bool`
- `block(entity_key, type, reason, ttl?)`
- `unblock(entity_key, type)`
- `list_blocked(type, paginated)`
- 多类型 denylist（IP / user / device / URL / phone / email）
- TTL 自动过期 + 持久 block 区分
- Audit log（who blocked, why, when）

**非功能性：**
- 100M+ entries 全球
- `is_blocked` QPS 1M+，P99 < 5ms（read 是 hot path）
- Block / unblock < 1 minute 全球生效
- 99.99% availability
- 强 audit / compliance

## 整体架构

```ascii
     Apps / Services (全球)
              │  is_blocked? (every request)
              ▼
        ┌──────────────┐
        │ Edge Cache   │  in-process LRU + Bloom filter
        │ (per service)│  3-5 min TTL, 数据库 fallback
        └──────┬───────┘
               │ miss
               ▼
        ┌──────────────┐
        │ Regional     │  Redis cluster per region
        │ Cache (Redis)│  完整 denylist 拷贝
        └──────┬───────┘
               │ miss / write
               ▼
        ┌──────────────┐
        │ Denylist API │  CRUD + auth
        │ Service      │
        └──┬──────┬────┘
           │      │
           ▼      ▼
    ┌────────┐  ┌──────────────┐
    │ Source │  │ Audit Log    │  immutable append-only
    │ of     │  │ (Spanner)    │
    │ Truth  │  └──────────────┘
    │ (DB)   │
    └────────┘
           │
           ▼ CDC
    ┌──────────────┐
    │ Kafka topic: │  denylist.events
    │ block/unblock│
    └──────┬───────┘
           │
    ┌──────┴──────┬────────────┬──────────┐
    ▼             ▼            ▼          ▼
   per-region Redis updaters consumer
```

## 核心组件设计

### 1. 数据模型

```sql
CREATE TABLE denylist_entries (
  id           UUID PRIMARY KEY,
  entity_key   TEXT NOT NULL,        -- "ip:1.2.3.4" / "user:abc"
  entity_type  TEXT NOT NULL,        -- 'ip'/'user'/'device'/...
  reason       TEXT,
  source       TEXT,                 -- 'auto'/'admin'/'ml'
  created_at   TIMESTAMPTZ,
  expires_at   TIMESTAMPTZ,          -- NULL = permanent
  status       TEXT,                 -- 'active'/'revoked'
  metadata     JSONB
);
CREATE UNIQUE INDEX idx_entity ON denylist_entries(entity_type, entity_key) WHERE status = 'active';
CREATE INDEX idx_expires ON denylist_entries(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE audit_log (
  id           BIGSERIAL,
  entry_id     UUID,
  action       TEXT,                 -- 'create'/'extend'/'revoke'
  actor        TEXT,
  reason       TEXT,
  ts           TIMESTAMPTZ
);
```

### 2. Source of truth: Spanner / 强一致 DB

为什么 Spanner 而非 Cassandra：
- 强一致：admin block 后立即可在 dashboard 看到
- Transaction：block + audit log 同一 transaction
- 全球分布 + 强一致 = Spanner sweet spot

### 3. Hot read path: 三层缓存

**Layer 1: In-process LRU + Bloom filter**（每个 service instance）
- Bloom filter 处理 99% "not blocked" case（false positive < 0.1%）
- 命中 Bloom → 查本地 LRU（最近 10k 热 key）→ 仍 miss 才下沉

**Layer 2: Regional Redis cluster**
- 全 denylist 拷贝（cluster mode 分片）
- Read latency < 1ms（local region）

**Layer 3: Spanner**
- Cold read only。Application 不直接查 Spanner（除非 Redis 全挂）

### 4. Block propagation

```
Admin → API → Spanner (write + audit) → CDC → Kafka
Kafka → per-region updater → Regional Redis update
Regional Redis → in-process cache TTL 自然刷新
```

延迟：
- API → Spanner ~10ms
- Spanner → Kafka via CDC ~1s
- Kafka → Redis update ~500ms
- In-process cache TTL ~3-5 min

**总：blocking 全球生效 ≈ 1 分钟 worst case**

### 5. Bloom filter 设计

```python
# 每 service instance 启动时从 regional Redis 加载完整 bloom
bloom = BloomFilter(capacity=100_000_000, error_rate=0.001)
# size ≈ 170 MB（100M items, 0.1% false positive）
# 每个 instance 装得下
```

- 优势：99% case 不查 cache，O(1) 时间确定"not blocked"
- 0.1% false positive → 多查一次 Redis，OK
- 实时更新：Kafka consumer 把新 blocked entries add 到 bloom

### 6. Expiry handling

- TTL entries：用 Spanner 的 TTL feature 或后台 cron job 每分钟 scan `expires_at < now`
- Soft delete：set status='revoked'，保留行用于 audit
- Bloom filter 不支持 delete → 每 6 小时全量重建（OK，bloom 是 forgiving 的 false positive 多查 Redis 即可）

### 7. Admin workflow

```
Admin UI → API
  POST /block {entity_key, type, reason, ttl}
    → Spanner write (in transaction with audit log)
    → return success
    → 1 分钟后全球生效
```

### 8. ML auto-block 集成

ML model（fraud / abuse detection）→ 调用 block API。`source='ml'` 区分。
- High-confidence 直接 block
- Low-confidence → 进 review queue 让 admin 审核

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Source of truth | Spanner（强一致 + global） | Cassandra（eventual，admin UI 不友好） |
| Hot read | Bloom + LRU + Redis 三层 | 只 Redis：QPS 上限 |
| Propagation | CDC + Kafka | DB polling：延迟高 |
| Expiry | Spanner TTL + bloom 重建 | Bloom 支持 delete：复杂 |
| Audit | 独立 immutable table | 改 entry 行：失审计 |

## 容量估算

- 100M entries × 200 字节 = 20 GB（Spanner & Redis cluster 都装得下）
- Bloom filter ~170 MB per service instance
- Read QPS 1M：99% Bloom hit (0.5μs) + 1% Redis (1ms) → P50 < 0.1ms, P99 < 5ms
- Write QPS 1k peak (admin + ML) → Spanner 撑得住

## 关键技术决策

- **Read-heavy → 多层 cache + Bloom**：1M QPS 不允许每 read 查 DB
- **Strong consistency for write → Spanner**：admin 不能容忍 "I just blocked it but UI still shows active"
- **Audit immutability** → 独立 table append-only
- **Multi-region with managed propagation**：CDC + Kafka 比 DB multi-master 简单

> [!key]
> 三大要点：(1) **Bloom + LRU + Redis 三层 read cache** 把 1M QPS hot path 干到 P99 < 5ms；(2) **Spanner source of truth** 保证 admin 一致性；(3) **CDC + Kafka 全球 propagation** 1 分钟生效。

> [!pitfall]
> ❌ 只用一层 Redis cache —— QPS 上限不够；
> ❌ Bloom filter 不更新 —— 新 block 不生效；
> ❌ 没 audit log —— compliance 失败；
> ❌ Delete entry 不软删 —— 失去 historical audit；
> ❌ 用 Cassandra source of truth —— admin UI 看到 eventual lag confused。

> [!followup]
> "如果某 region Redis 挂了？" → fallback 查 Spanner，serve 较慢但仍 work；"Phishing URL 这种 prefix-based block？" → 加 trie 索引或 prefix matcher 在 Redis；"如何 detect 大规模 abuse？" → ML model 离线扫 + 自动 block；"如何防止 self-DoS（误 block 大量好用户）？" → 加 admin double-confirm + 自动 rollback 5 分钟。
