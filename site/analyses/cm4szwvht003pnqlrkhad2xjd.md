## 题目本质

设计 **Ticket Booking System**（Ticketmaster / 中国 12306）：用户浏览 events → 选 seats → 在 5 分钟 hold time 内付款。**关键挑战：并发抢同一 seat**。

Google 报告 9 次。考点：**并发 seat lock + 倒计时 + payment 一致性**。

## 需求拆解

- 100M events / year，single event 100k seats
- Burst：cricket / Taylor Swift 票开抢瞬间 10M concurrent users
- Hold time 5 分钟，付款失败 release
- 不能 oversell（金科玉律）
- 退款 / 换票

## 整体架构

```ascii
    User                       
      │ browse / select         
      ▼                        
  ┌──────────────┐
  │ Edge / CDN   │  → cached event list & seat map
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐    ┌───────────────────┐
  │ Booking API  │ ── │ Redis: seat locks │
  └──────┬───────┘    │ (5 min TTL)       │
         │            └───────────────────┘
         │ confirm payment
         ▼
  ┌──────────────┐
  │ Payment Svc  │ ── external gateway (Stripe)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Order DB     │  Postgres + strong consistency
  │ + Seat State │
  └──────┬───────┘
         │ CDC
         ▼
  Notification, ticket gen, etc.
```

## 核心机制

### 1. Seat lock：两阶段

**Phase 1 (Hold)** — Redis SET NX 抢座：

```python
lock_key = f"seat:{event_id}:{seat_id}"
ok = redis.set(lock_key, user_id, nx=True, ex=300)   # 5 min TTL
if not ok:
    return SeatTaken
# 用户进入支付流程
```

**Phase 2 (Confirm)** — 付款成功后转 DB：

```python
# In transaction:
INSERT INTO orders (...);
UPDATE seats SET status='sold', user_id=? WHERE event_id=? AND seat_id=? AND status='held';
DEL seat:{event_id}:{seat_id} from Redis
```

### 2. 防 oversell

DB 层 unique constraint + status='sold' check 是 final 防线。即使 Redis 数据丢失，DB transaction 保证不会两人买同一座。

### 3. Hold 自动 expire

Redis TTL 自然处理 —— 5 分钟内不付款，lock 自动释放。

### 4. 高并发抢票

热门 event 开售瞬间几百万 user 同时抢：
- **Queue + 排队** UI 流量控制（"你前面还有 N 万人"）
- **Sharded seat**：把座位分 region，按 user_id hash 路由到不同 partition 抢
- **Pre-warm Redis cluster**：开抢前预先 partition 好 + replica 加倍
- **Captcha + bot detection**：黄牛拦截

### 5. Seat map UI 实时更新

WebSocket broadcasting seat state change：
```
user A hold seat 5A → Redis SET → publish "seat 5A held" → 所有看 event 的 client UI 灰掉 5A
```

Pub/sub 通过 Redis 或 SSE 实现。

### 6. Payment + Saga

```
1. Create order (status=pending)
2. Hold seat (Redis lock)
3. Call payment gateway
4. On success: confirm in DB transaction (orders + seats)
5. On failure: release Redis lock + order status=failed
6. On timeout: 类似 failure
```

Compensating actions on each step 确保不会"扣款但没座"。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Hold mechanism | Redis SETNX + TTL | DB row lock：写热点 |
| Final state | DB strong consistency | Eventual：oversell 风险 |
| Seat map sync | WebSocket pub/sub | Polling：UX 差 |
| Anti-bot | Queue + captcha | 无：黄牛 |
| Shard | Per-event sharding | Global single：DB 写热点 |

## 容量估算

- 100k 座 × Redis SETNX 操作 ≈ 100k QPS peak → Redis cluster 撑得住
- Confirm 写 ≈ 100k / 5 min = 333 QPS → Postgres 单机可
- 但 10M concurrent users browse → CDN + read replica

## 易错点

> [!pitfall]
> ❌ 用 DB row lock 抢座 —— 写热点 + 锁等死；
> ❌ 没 TTL 自动 release —— hold 永久占座；
> ❌ Payment 后才 hold —— 多人成功支付同 seat；
> ❌ 不做 oversell DB 防线 —— Redis 数据丢失就完；
> ❌ 不做 bot 拦截 —— 黄牛瞬间抢光；
> ❌ Seat map UI 不实时 —— 用户选了发现已被抢。

> [!key]
> 三大要点：(1) **Redis SETNX + TTL** 做 hold lock；(2) **DB strong consistency** 防 oversell（final 防线）；(3) **Saga 处理 payment failure** + WebSocket 实时 seat map。

> [!followup]
> "换票？" → 释放旧 + hold 新 + DB transaction；"团体购票（一次 50 张相邻）？" → seat group lock + 检查 contiguous；"退款？" → reverse saga；"VIP 优先购？" → pre-sale window + auth check。
