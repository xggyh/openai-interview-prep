## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Race condition** | 多个请求同时到达，操作同一个资源 → 结果取决于谁先谁后，bug 难复现 | 两个人同时抢一个座位 |
| **Optimistic lock** | "乐观锁" —— 假设不冲突，更新时检查版本号；冲突就 retry | 两个人都说"我先来"，谁版本号对谁赢 |
| **Pessimistic lock** | "悲观锁" —— 直接锁住资源不让别人碰 | 占座放包包 |
| **Redis SETNX** | "SET if Not eXist" —— 原子操作，set 成功返回 True | 抢座位时贴个 sticker，已贴则失败 |
| **TTL (Time To Live)** | 数据存活时间。过期自动消失 | 临时占位条 5 分钟到期 |
| **DB Transaction** | 一组操作要么全成功要么全失败，原子性 | 转账时 "扣 A + 加 B" 一起完成 |
| **Saga** | 跨多服务的"分布式 transaction"实现方式：每步成功了下一步；失败了倒着做 compensating | 多人接力跑，跑错了反向跑回来 |
| **Idempotency key** | "幂等 key" —— 同一个 key 多次提交 server 只处理一次 | 同一张工单号交两次只入一次账 |
| **WebSocket** | 客户端服务器持久双向连接，可以 push 消息 | 走廊对讲机 vs 拨电话 |
| **Pub/Sub** | 发布订阅模式，发布者发 message，所有订阅者收到 | 群发短信 |
| **Sharding** | 把数据切片到多台机器，按 key (如 event_id) 分配 | 大厨房按菜系分多个工作台 |
| **Captcha** | 人机验证，挡 bot | "请勾选我不是机器人" |

---

## 1. 题目本质 — 这是什么问题

**Ticket Booking System** = 用户买演唱会 / 火车 / 电影票。流程：
1. 浏览 event（演唱会、火车班次）
2. 选 seat（A 排 12 号）
3. **5 分钟内付款** → 出票
4. 不付款 → seat 释放给别人

**为什么这道题这么难（区别于普通电商）**：

| 普通电商 | Ticket Booking |
|---|---|
| 商品大量 inventory（10000 件 T 恤） | **每个 seat 唯一**（A12 只有 1 个） |
| 用户可以买 5 件，下次再来还有 | **抢手 event 卖完就没了**，错过等下次 |
| QPS 平稳 | **开抢瞬间 10M 人涌入** |
| 卖多了可以补货 | **绝对不能 oversell**（卖出 2 张同 seat = 法律纠纷） |
| Hold 库存 5 分钟不要紧 | **Hold 5 分钟 vs 立即给别人，钱可能差 1 万** |

核心矛盾：**高并发抢同一资源 + 绝对不能 oversell**。

Google 报告 9 次，是经典 SD 题。考点：**concurrency control + race condition + payment Saga**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：用户可以选具体座位还是只选区域？  
**典型答**：**两种都要**。VIP 区可选具体座位（A12）；普通区只选区（"front row"）系统随机分配。

**你问**：Hold 多长时间？  
**典型答**：5 分钟。超时自动释放。

**你问**：能不能一次买多张？团购？  
**典型答**：可以。最多 8 张。如果是相邻座位需 group hold（都成功或都失败）。

**你问**：付款失败 / cancel 怎么办？  
**典型答**：seat 立即释放，让其他人抢。

**你问**：退票 / 改签？  
**典型答**：支持，但有 cancellation window（开演前 24h 可退）。

### 2.2 非功能性

**你问**：QPS 量级？  
**典型答**：平时 1k QPS read；**热门 event 开抢瞬间 1M+ concurrent users**（如 Taylor Swift / cricket / 春运 12306）。

**你问**：单 event 多少 seat？  
**典型答**：10k-100k seat (体育馆) 到 1M+ seat (跨日 cricket / 春运全列车)。

**你问**：能 oversell 一张吗？  
**典型答**：**绝对不行**。法律风险。

**你问**：付款多久要确认？  
**典型答**：< 30s P99。

### 2.3 需求清单

```
功能：
- 浏览 events
- 选 seat (具体或区域)
- Hold 5 分钟付款
- 不付款自动释放
- 支持多张 (相邻座位)
- 退票 / 改签

非功能：
- 平时 1k QPS，开抢峰值 1M+ concurrent
- 单 event 1M+ seats
- 绝对不 oversell
- Payment P99 < 30s
- 高峰 system 不 down
```

> [!key]
> "**绝对不能 oversell**" 是这道题的灵魂约束。所有架构决策都围绕它。其他系统可以"差不多就好"，ticket booking 不行。

---

## 3. 容量估算

### 3.1 平时 vs 高峰

**平时**：
```
1k QPS browse + 100 QPS book
```
单 server 都能撑。

**热门 event 开抢**：
```
10M user 在 11:00:00.000 同时点 "立即购买"
= 瞬时 10M concurrent
= 假设动作分散在 1 分钟 = 167k QPS persistent
```

→ 这是真挑战，需要**专门为开抢设计**。

### 3.2 数据量

```
1B users × ~1 booking/year = 1B bookings/year history
≈ 3B records/year (含 cancellations / changes / payment history)
× 500 bytes/record = 1.5 TB/year
```

不大。Postgres / Spanner 都装得下。

### 3.3 单 event seat 数

```
体育馆: 50k seats
跨城演唱会巡回: 5 城 × 50k = 250k seats
12306 春运: 4000 趟车 × 1500 座 = 6M seats
```

→ **每 event 一个独立"小宇宙"**。可按 event_id sharding。

---

## 4. 整体架构 step by step

### 4.1 第 0 步：最朴素的方案（会出问题）

```ascii
   User
     │  POST /book {event_id, seat_id}
     ▼
   ┌──────────────┐
   │ API          │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Postgres     │  UPDATE seats SET sold=true WHERE id=? AND sold=false
   └──────────────┘
```

**为什么会 oversell**：
- 用户 A、B 同时 `SELECT WHERE sold=false` → 都看见 seat 可用
- 都 UPDATE → DB row lock 让一个等
- 但应用层已经返回 "seat A12 你的了！" 给两个用户

**正确做法**：UPDATE 必须**带 WHERE sold=false 检查**作为 atomic compare-and-set：

```sql
UPDATE seats SET sold=true, user_id=$user WHERE id=$seat AND sold=false;
-- 如果 affected_rows = 0 → 已被人抢，本用户失败
```

这个 atomic 操作避免 oversell。但...

**新问题**：10M user 同时 `UPDATE seats WHERE event_id=X` → DB row lock contention 爆炸，DB CPU 100%。

### 4.2 第 1 步：加 Redis 做 hold

把 hold 操作从 DB 挪到 Redis（内存，超快）：

```ascii
   User select seat A12
     │
     ▼
   API: SETNX seat:event123:A12 user_id EX 300
     │
     ├─ True → "你抢到了，5 分钟内付款"
     └─ False → "已被别人占了"
```

**为什么 Redis 适合**：
- `SETNX` 是 atomic，无 race condition
- 内存操作 50us，能撑 100k+ QPS / instance
- TTL 自动过期，不付款的 5 分钟后释放

```
10M user 抢 100k seat → Redis 撑得住
DB 不在 hot path
```

### 4.3 第 2 步：付款 + DB transaction（two-phase）

Phase 1: Redis hold；Phase 2: 付款成功 → DB transaction 把 hold 转 sold。

```ascii
User pay
   │
   ▼
   call payment gateway (Stripe)
   │ wait...
   ▼ 
   成功？
   │
   ├── No → DEL Redis hold (释放 seat)
   └── Yes:
         │
         ▼
       BEGIN TRANSACTION
         INSERT orders (user, event, seat, payment_id, status='paid')
         UPDATE seats SET sold=true WHERE id=$seat AND status='held'
         IF UPDATE 0 rows → ROLLBACK (hold expired)
       COMMIT
         │
         ▼
       DEL Redis hold
       Send ticket / email
```

**为什么 DB 还要 `WHERE status='held'`**：双保险。Redis 数据丢失（极少但可能）时，DB 的 `WHERE status='held'` 仍能防止重复 sell。

### 4.4 第 3 步：防开抢瞬间 burst

**问题**：10M 用户同时 click "Buy"。即使 Redis 100k QPS，也撑不住 10M 瞬时。

**方案 A：排队系统**

```ascii
   User click Buy
     │
     ▼
   ┌──────────────┐
   │ Virtual      │  → 把用户放进 queue，分配排位 (#10342)
   │ Queue Service│  → 前端显示 "你前面还有 N 人"
   └──────┬───────┘
          │ 每秒放 100 人进
          ▼
   ┌──────────────┐
   │ Booking      │  → 正常 Redis SETNX
   │ Service      │
   └──────────────┘
```

这就是 Ticketmaster / 12306 / Cricket 大型购票的真实做法 —— 你在 12306 开抢时看到的"前面还有 12000 人"就是这个。

**方案 B：sharding by seat**

```
seat hash → 路由到对应 Redis instance
1M 用户分散到 100 Redis instances，每 instance 10k QPS
```

### 4.5 第 4 步：实时 seat map 更新

用户看 seat map 选座，**对方 hold 后 UI 要立刻变灰**，否则用户点击发现 "已被占" 体验差。

```ascii
User opens event seat map
   │
   ▼
   WebSocket subscribe `event:123`
   │
   ▼
   有人 hold seat A12
   │
   ▼
   Server: SETNX 成功后 publish "seat A12 held" to channel event:123
   │
   ▼
   所有看 event 123 的 client WS receive → UI 变灰 A12
```

技术：Redis Pub/Sub 或 SSE。

### 4.6 完整架构

```ascii
                       User
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
    Browse API     WebSocket          Booking API
        │           (seat map)            │
        ▼                                 ▼
   ┌──────────┐                    ┌──────────────┐
   │ Event    │                    │ Virtual Queue│
   │ Catalog  │                    │ (大热 event) │
   │ Service  │                    └──────┬───────┘
   └──────────┘                           │ 1s 一批放行
                                          ▼
                                   ┌──────────────┐
                                   │ Booking      │
                                   │ Service      │
                                   └─┬──────┬─────┘
                                     │      │
                  ┌──────────────────┘      └──────────────────┐
                  ▼                                            ▼
            ┌──────────────┐                            ┌──────────────┐
            │ Redis        │  ← SETNX hold 5min          │ Payment       │
            │ (per-event   │     publish to WS           │ Service       │
            │  sharded)    │                            │ (Stripe etc)  │
            └──────────────┘                            └──────┬────────┘
                                                               │
                                                               ▼ paid
                                                         ┌──────────────┐
                                                         │ Postgres /   │
                                                         │ Spanner      │
                                                         │ (orders +    │
                                                         │  seats)      │
                                                         └──────────────┘
```

---

## 5. 每个组件深挖

### 5.1 Data model

```sql
-- events
CREATE TABLE events (
  id            UUID PRIMARY KEY,
  organizer_id  UUID,
  name          TEXT,
  venue_id      UUID,
  start_at      TIMESTAMPTZ,
  status        TEXT,  -- 'upcoming' / 'on_sale' / 'sold_out' / 'cancelled'
  ...
);

-- seats per event
CREATE TABLE seats (
  event_id    UUID,
  seat_id     TEXT,                 -- e.g. "A12" / "FRONT_ROW_5"
  zone        TEXT,                 -- "VIP" / "Standard"
  price_cents BIGINT,
  status      TEXT,                 -- 'available' / 'held' / 'sold'
  user_id     UUID,                 -- null if available
  held_until  TIMESTAMPTZ,
  PRIMARY KEY (event_id, seat_id)
);
-- 关键：按 event_id partition / shard

-- orders（payment 确认后写）
CREATE TABLE orders (
  id            UUID PRIMARY KEY,
  user_id       UUID,
  event_id      UUID,
  seat_ids      TEXT[],
  payment_id    TEXT,
  total_cents   BIGINT,
  status        TEXT,             -- 'pending' / 'paid' / 'refunded' / 'cancelled'
  created_at    TIMESTAMPTZ,
  paid_at       TIMESTAMPTZ
);
```

**新手 question**：

❓ **为什么 seats 表不直接删掉 sold 行而是用 status 字段？**  
退票需要还原 seat → available。Soft state 更易管理。

❓ **为什么 (event_id, seat_id) 是 PK，不是单一 UUID？**  
这样 seat_id 在 event 内 human-readable（"A12"），seats 表自然按 event_id 分区。

### 5.2 Redis Hold 详细

```python
def hold_seat(event_id: str, seat_id: str, user_id: str) -> bool:
    """Try to hold a seat. Returns True if success."""
    key = f"hold:{event_id}:{seat_id}"
    # SETNX with TTL = atomic
    ok = redis.set(key, user_id, nx=True, ex=300)  # nx=only if not exists; ex=5min
    return ok

def release_seat(event_id: str, seat_id: str, user_id: str):
    """Release if I'm the holder. Lua script for atomicity."""
    lua = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    redis.eval(lua, 1, f"hold:{event_id}:{seat_id}", user_id)
```

**为什么 release 要 Lua**：你想"我 release 我的 hold"，不是"我 release 任意人的 hold"。GET + DEL 两步不 atomic，可能被人 race。Lua script Redis 单线程执行天然 atomic。

### 5.3 Group Hold (相邻 N 张)

用户买 4 张相邻座位，必须**4 个 hold 全成功**或**全失败**：

```python
def hold_group(event_id, seat_ids: list, user_id):
    held = []
    for sid in seat_ids:
        if hold_seat(event_id, sid, user_id):
            held.append(sid)
        else:
            # 失败：把已 hold 的释放
            for s in held:
                release_seat(event_id, s, user_id)
            return False
    return True
```

每秒可能上千 group hold 同时尝试，**先来的赢**（first SETNX wins）。

### 5.4 Payment + DB Transaction

**核心问题**：Payment gateway 在外部（Stripe / 支付宝），可能 5-30 秒延迟。期间状态机怎么管？

```ascii
1. User click "Pay" → create order (status='pending') 写入 DB
2. Order id 作 idempotency key 调 payment gateway
3. Gateway 5-30s 后回 callback
4. 收到 callback:
   ├── success → DB transaction:
   │             UPDATE orders SET status='paid'
   │             UPDATE seats SET status='sold' WHERE seat_id IN (...) AND status='held'
   │             COMMIT
   │             ↓
   │             DEL redis holds
   │             send ticket email + push
   │
   └── failure → DB UPDATE orders SET status='failed'
                 DEL redis holds
```

**Idempotency**：Stripe webhook 可能重传（网络抖动）。Order id 作幂等 key，重复 callback 只处理一次。

**Saga compensating actions**：

```
forward:
  1. create order
  2. charge user
  3. mark seats sold
  4. notify user

if 2 fail:
  - release seat holds (compensate 1)

if 3 fail (seat 已被别人抢):
  - refund payment (compensate 2)
  - return error to user
  - alert team (这不应该发生，logic bug)
```

### 5.5 Virtual Queue 详解

**问题**：热门 event 开抢 11:00:00 瞬间 10M 人涌入，连 booking API 都打不通。

**方案**：开抢前所有 user 进入 "queue"。Server 按位次每秒放 N 人进入正式 booking。

```python
# 用户 click "Buy now" 时
queue_pos = redis.incr(f"queue:event:{event_id}")
# 返回前端：你的位置 #{queue_pos}, 预计 {queue_pos / 100} 秒后轮到

# Server 后台 worker
while True:
    cursor = redis.get(f"queue:cursor:{event_id}")  # 当前已放行号
    target = cursor + 100  # 每秒放 100 人
    redis.set(f"queue:cursor:{event_id}", target)
    # 通知 cursor 之前的所有用户 "你可以进入了"
    sleep(1)
```

用户客户端**轮询 / WebSocket**：当我的 queue_pos <= cursor 时，跳到正式 booking 页。

**为什么是 100 人/秒**：根据下游 (Redis SETNX + booking API + payment) 实际容量定。给 booking 后端留余地处理。

### 5.6 防 bot / 黄牛

热门 event 黄牛大量 bot 抢票：

```
对策：
- Captcha (开抢前必须完成)
- Account age check (新注册 < 7 天不能买)
- Device fingerprint (一设备 1 张限制)
- Rate limit by IP (10 ticket per IP)
- ML anti-fraud model
- 实名制（演唱会越来越实名）
```

### 5.7 Sharding by event

不同 event 独立 partition：

```
event_id hash → 分到对应 Redis cluster + DB partition
event A 开抢的 burst 不影响 event B 的正常 booking
```

每 event 一个"小宇宙" → 故障 / 性能问题被局部化。

### 5.8 退款 / 改签

退款流程：

```
1. User cancel
2. Check policy (event 是否在 cancellation window)
3. DB transaction:
     UPDATE order SET status='refunded'
     UPDATE seats SET status='available', user_id=NULL
4. Call payment gateway refund
5. 通知 WS publish "seat A12 again available" → 其他 user 抢
```

改签 = 退 + 重买。或合并 transaction 直接换 seat。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 单座 vs 区域选座？
  - Hold 时长？
  - 多张 group hold？
  - 平时 vs 开抢 QPS

0:05 - 0:10  Capacity Estimation
  - 平时 100 QPS booking
  - 开抢 10M concurrent → 167k QPS / min
  - 强调 oversell 绝对不允许

0:10 - 0:15  High-Level Architecture
  - User → API → Redis (hold) → DB (paid)
  - WebSocket for seat map updates
  - Virtual queue for burst

0:15 - 0:30  Deep Dive
  ★ Redis SETNX hold (race condition 怎么消除)
  ★ Payment Saga + idempotency
  ★ Virtual queue for burst
  
0:30 - 0:38  Follow-ups
  - Group hold (相邻 N 张)
  - 防黄牛 bot
  - 退票
  - Sharding strategy

0:38 - 0:45  Wrap-up
  - 三大决策: SETNX + double-check at DB + virtual queue
  - Improvements
```

---

## 7. 面试样板讲解

> "OK，先确认几件事：seat 是用户选具体的（A12）对吧？Hold 5 分钟我假设。多张 group hold 我做。开抢 burst 是关键挑战 —— 你提到 Taylor Swift 那种 10M 同时抢，对吧？... 好。
> 
> 关键约束：**绝对不能 oversell**。这是法律风险，整个架构围绕这个建。
> 
> 我提出 two-phase 方案：
> 
> **Phase 1 (Hold)** —— 用户选座，server 用 Redis SETNX 抢锁。SETNX 是 atomic 的 'set if not exists'，加上 5min TTL 自动过期。两个用户同时点 A12，**只有一个 SETNX 成功**，另一个收到 'seat taken'。
> 
> **Phase 2 (Payment + Confirm)** —— Hold 成功后用户付款，5-30 秒回 callback。callback 触发 DB transaction:
> ```
> INSERT order...
> UPDATE seats SET sold=true WHERE id=$seat AND status='held'
> ```
> WHERE status='held' 是双重防线 —— Redis 数据丢了 DB 仍能防 oversell。
> 
> 开抢 burst 用 **Virtual Queue** —— 用户 click 后入队拿 #N，server 每秒放 100 人进。前端显示 '你前面 5000 人，预计 50 秒后'。这是 12306 / Ticketmaster 实战做法。
> 
> 实时 seat map 用 WebSocket，hold 时 publish 通知所有 viewer 灰掉 seat。
> 
> Sharding 按 event_id —— 开抢 burst 局部化，event B 正常 booking 不受影响。
> 
> 想 deep dive payment Saga 还是 anti-bot？"

---

## 8. Follow-up 演练

### Q1: Payment gateway timeout 怎么办（不知道到底扣没扣）？

**答**：order 保持 `status='pending'`，每分钟一个 reconcile job 跟 Stripe API 拉对账。
- Stripe 说 paid → 转 'paid'，confirm seat
- Stripe 说 failed → 转 'failed'，release seat
- 仍 unknown → 继续等，最长 24h，超时人工 review

### Q2: 用户付了款但 seat 已被人抢（极端 race，理论可能）？

**答**：DB transaction 失败时**立即 refund** + 通知用户 "抱歉支付已退" + alert 开发团队（这不应该发生，可能是 Redis / DB 同步 bug）。

### Q3: Redis 挂了怎么办？

**答**：
- Redis cluster + replication（高可用部署）
- Fallback：直接打 DB（性能差但仍能 serve，开抢 burst 不行但平时 OK）
- Hold expire 用 DB scheduled job 替代（每秒 scan released_holds）

### Q4: 同 user 抢多张 (4 张连座)？

**答**：Lua script 在 Redis 里 atomic 抢 4 个 SETNX。任一失败全部释放。或先用 Redis WATCH/MULTI 实现。

### Q5: 防黄牛 bot？

**答**：
- Captcha
- Account age > 7 days
- Device fingerprint
- IP rate limit (10 票 / IP / 月)
- ML anti-fraud
- 实名 + 人脸（演唱会越来越普遍）

### Q6: 退款 / 改签？

**答**：DB transaction 把 seat 状态 revert + call payment refund + WS publish "seat 再次可用"。改签 = 退 + 重 hold 重买，或合 transaction 原子换。

### Q7: 同时多 region 开抢？

**答**：每 event 单 region 开抢（主办方决定开抢 region）。如果跨 region，DB 用 Spanner 强一致 + each region 一个 Redis cluster handle 本 region traffic。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **DB row lock 抢座** —— 写热点，10M 用户同时 lock 同 table，DB CPU 100%；用 Redis SETNX；  
> ❌ **不带 WHERE status='held' check** —— Redis 数据丢失或同步问题时 oversell；DB 是 final 防线；  
> ❌ **Payment 同步阻塞** —— 用户等 30s 才知道结果；async + idempotent webhook；  
> ❌ **不做 Idempotency-Key** —— Stripe webhook 重试导致用户被扣两次；  
> ❌ **不做 Virtual Queue** —— 10M 涌入瞬间 server down；  
> ❌ **seat map 静态显示** —— 用户辛苦选了发现 'sold'，体验差；用 WebSocket；  
> ❌ **同 event 不 shard** —— 单 Redis 撑不住开抢；  
> ❌ **不防 bot** —— 黄牛瞬间抢光，被骂。

---

## 10. 加分项（What else）

- **Dynamic pricing**：高 demand 时 surge price（小心法规）
- **Best Available Seat 推荐**：用户不选具体，系统给最优
- **Multi-event basket**：同一订单买不同 event
- **Multi-currency / 国际化**
- **GraphQL API** 让前端按需 fetch
- **Real-time analytics dashboard** 给主办方看销售进度
- **Wait list**：sold out 时排队，有人退票自动通知
- **Resale market** (官方二级市场，防黄牛)
- **NFT ticket**：blockchain-based 防伪 + 可追溯

---

## 11. 总结：你应该记住的 3 件事

1. **Hold + Confirm 二阶段是 ticket booking 的标准模式**：Redis SETNX (atomic + TTL) hold；DB transaction (strong consistency + WHERE check) confirm。两层防 oversell。

2. **Burst 流量 = Virtual Queue**。10M 用户瞬间涌入 = 用 queue 削峰填谷。Ticketmaster / 12306 真实使用。

3. **Payment 一定 async + idempotent**。同步等 gateway 30 秒会死。Webhook callback + Idempotency-Key + Saga 是分布式 transaction 的标准模式。

> [!followup]
> **学习推荐**：(a) 实现一个 Redis SETNX + TTL 的简单 hold 系统；(b) 读 Stripe webhook idempotency 文档；(c) 看 Ticketmaster Verified Fan 是怎么防黄牛的；(d) 学一下 12306 春运历年优化（从 oversell 到 virtual queue）；(e) 考虑：演唱会换季后老 event 的数据保留多久 / 怎么 archive？
