## 题目本质

设计一个**支付清算系统**：用户发起一笔交易 → 调用外部支付网关授权 → 资金被冻结（hold）→ 当天结束批处理统一扣款（capture）。规模：10k TPS。

这题真正考的是**"先 authorize 后 capture" 的两阶段语义** + **冻结资金的幂等管理** + **批处理可重放**。不是写一个 Stripe 集成。

## 需求拆解

**功能性：**
- 用户发起 charge：金额 + 卡 token → 外部网关返回 approve/deny
- approve 后冻结金额，记录 hold
- 当天 23:59 跑批，把所有当日 hold 真正扣款 + 通知商家结算
- 退款（refund） + 部分扣款（partial capture）

**非功能性：**
- 10k TPS（峰值更高 2x）
- 端到端 authorization 延迟 P99 < 500 ms
- 资金安全：**绝对不能重复扣款，不能丢失扣款**（financial correctness）

**容量估算：**
- 10k TPS × 86400 s ≈ 864M 笔/天
- 每笔记录 ≈ 1 KB → 每日数据增长 ≈ 864 GB（需分区/归档）

## 整体架构

```ascii
 Client ─▶ API GW ─▶ [Auth Service] ─▶ Idempotency Store (Redis)
                            │
                            ├──▶ Payment Gateway (Stripe/Adyen)
                            │       │
                            │       ▼ approve / deny
                            ▼
                       [Ledger DB]            ← 强一致 (Postgres + tx)
                            │   (HOLD entry)
                            ▼
                       Kafka topic: "hold_created"
                            │
                            ▼
                   Batch Scheduler (daily 23:55)
                            │
                            ├──▶ Capture Worker (consume holds)
                            │       │
                            │       └▶ Payment Gateway capture
                            │              │
                            │              ▼ ack
                            ▼
                       [Ledger DB]
                          (CAPTURED entry)
                            │
                            ▼
                       Merchant Settlement Service
```

## 核心组件设计

### 1. Idempotency（最关键）

每个 charge 请求必须带 `Idempotency-Key`（client 生成 UUID）。服务端在 Redis 用 `SETNX idempotency:{key} -> {request_hash}` + TTL 24h 保证同一 key 只处理一次。**这是支付系统第一防线**。

```python
def handle_charge(req):
    key = req.headers['Idempotency-Key']
    cached = redis.get(f"idemp:{key}")
    if cached:
        return cached  # 直接返回前一次结果，不重复调用网关
    # ... 执行 charge ...
    redis.setex(f"idemp:{key}", 86400, response)
```

### 2. Ledger 设计（核心数据模型）

**双重记账（double-entry）模型**：每笔操作生成两条 ledger entry —— 一条 debit、一条 credit，永远平衡。

```sql
CREATE TABLE ledger_entry (
  entry_id     BIGSERIAL PRIMARY KEY,
  txn_id       UUID NOT NULL,         -- 同一业务事务的多条 entry 共享
  account_id   UUID NOT NULL,         -- 用户账户 / 商家账户 / 网关账户
  amount       BIGINT NOT NULL,       -- 单位：cents
  direction    CHAR(1) CHECK (direction IN ('D','C')),  -- Debit/Credit
  state        TEXT NOT NULL,         -- PENDING / HOLD / CAPTURED / REVERSED
  created_at   TIMESTAMPTZ DEFAULT now(),
  external_ref TEXT                   -- 网关返回的 auth_id
);
CREATE INDEX idx_ledger_state_created ON ledger_entry(state, created_at);
```

**为什么 ledger 而不是直接改账户余额？** 余额是 ledger 的 derived view（`SUM` over entries）。所有变动都是 append-only，**审计 + 对账 + 回放**都靠这个表。

### 3. 两阶段 Authorize / Capture

```python
# Phase 1: Authorize（实时）
@transactional
def authorize(card, amount, idemp_key):
    txn_id = uuid4()
    gateway_resp = gateway.authorize(card, amount)
    if gateway_resp.status != 'approved':
        ledger.insert(txn_id, account='user', dir='D', state='DENIED', amount=amount)
        return Reject
    # Approved: 写 HOLD entry
    ledger.insert(txn_id, account='user',      dir='D', state='HOLD', amount=amount,
                  external_ref=gateway_resp.auth_id)
    ledger.insert(txn_id, account='gateway',   dir='C', state='HOLD', amount=amount)
    return Ok(txn_id)

# Phase 2: Capture（每日批处理）
def capture_batch(date):
    holds = ledger.scan(state='HOLD', date=date)
    for hold in holds:
        try:
            gateway.capture(hold.external_ref)  # 网关侧幂等
            ledger.update(hold.txn_id, state='CAPTURED')
        except CaptureFailed:
            ledger.insert(reversal_entry)  # 写补偿
            alert()
```

### 4. 批处理可重放

Batch job 必须**幂等**：如果跑到一半挂了，第二次跑要能从中断处继续。靠的是 `state=HOLD` 这个状态过滤 —— 已 CAPTURED 的会被 skip。再加每条 hold 上的 `external_ref`，网关侧 capture 也是幂等的（`Idempotency-Key` 相同）。

### 5. 分区策略

- Ledger 按 `created_at` 月分区 + `account_id` hash 子分区
- 热数据（30 天内）在主 Postgres，冷数据归档到 S3 + Athena
- 读 / 报表查询走只读副本 + 列存（ClickHouse 同步）

## 取舍 / 权衡

| 决策 | 选择 | 替代 + 为什么不选 |
|---|---|---|
| 存储 | Postgres（强一致） | Cassandra：不行，最终一致性写会破坏金额平衡 |
| 队列 | Kafka | RabbitMQ：吞吐不够；Kafka 还能做 audit trail |
| 同步/异步 | Authorize 同步（用户等结果），Capture 异步批处理 | 全异步：用户等不了；全同步：网关 API 频次上不去 |
| 幂等 | Redis + DB UNIQUE 约束双保险 | 仅 Redis：Redis 挂了就丢防线 |

## 风险控制

- **欺诈检测**：authorize 之前过 fraud service（特征：IP、卡 BIN、设备指纹、velocity）
- **限速**：用户级 + 卡级 rate limit
- **对账**：每日跟网关下行的 settlement 文件做 reconciliation，差异立刻 alert

> [!key]
> 这题在 OpenAI 53 人报告，是仅次于 Online Chess 的最热 SD。核心点：**ledger + idempotency + 两阶段授权**。面试官会狠抠"重启批处理不重扣"和"网关 timeout 怎么办"。

> [!pitfall]
> ❌ 直接改账户余额（无法审计 / 无法回滚）；
> ❌ Authorize 用异步队列（用户等不了几秒钟）；
> ❌ 不做 Idempotency-Key（重试一次扣两次）；
> ❌ Capture 失败简单 retry（可能已经扣过了 —— 必须用 external_ref 做网关侧幂等）；
> ❌ 用 Cassandra / Dynamo 存 ledger（最终一致性 ≠ 金额准确）。

> [!followup]
> "如果网关返回 timeout，到底扣了没？" 答：等 reconciliation 文件，期间 hold 状态保留为 `UNCONFIRMED`，到账后核对再转 HOLD 或 REVERSED。"如何处理跨币种？" 答：在 ledger 里多存 `currency + fx_rate`，记账时分两条（用户币种 D，商家币种 C，差额计入 fx_pnl 账户）。
