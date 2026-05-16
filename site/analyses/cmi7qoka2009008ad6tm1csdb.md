## 题目本质

设计 **E-commerce Offer Subscription System**：商家发优惠，用户订阅感兴趣 categories / merchants，新优惠时 notify 用户。Groupon / 京东预约 / Amazon Daily Deals。

## 需求

- 100M users
- 1M offers/day
- Real-time delivery (< 1 min)
- Personalized matching
- Multi-channel notify (email / push / app feed)

## 整体架构

```ascii
   Merchant
       │ create offer
       ▼
  ┌──────────────┐
  │ Offer Service│  CRUD + validation
  └──────┬───────┘
         │ publish
         ▼
  ┌──────────────┐
  │ Offer Stream │  Kafka topic: offers.new
  │ (Kafka)      │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Matching Service │  match offer to subscribers
  │  (per subscript) │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Notification     │  Push / Email / In-app feed
  │ Fan-out          │
  └──────────────────┘
```

## 核心组件

### 1. Subscription model

User 订阅维度：
- Merchant ("我关注 Nike")
- Category ("running shoes")
- Price range
- Location (店在 5km 内)
- Keyword ("vegan")

存 Postgres + ES。

### 2. Matching algorithm

每新 offer 来到：对所有 subscription 做 match。N subscriptions × M offers/day = 巨大。

**Inverted index 优化**：
- `category -> subscriber_ids`
- `merchant -> subscriber_ids`
- Offer 来：lookup matching subscribers 是 set union

不要每 offer × 每 user 全 scan。

### 3. Personalization

匹配后还要 rank：
- User past behavior (click rate on similar offers)
- Recency weighting
- User active hour (push 时机)

### 4. Notification channels

- Push (FCM / APN)：immediate
- Email：digest，每 user 每天最多 1 封
- In-app feed：push 到 user feed, 用户 open app 时看

每 user 自选 channel + frequency。

### 5. De-dup + rate limit

同 user 30 分钟内 max 3 push。同 merchant 24 小时内只通知 user 一次。

### 6. Geo

Offer 含 GPS / 地址。User 当前 location 或 home location。Geo-radius filter。

### 7. Real-time vs batched

Real-time offers (flash sale): 5 min 内 push
Daily digest: 凌晨 aggregate yesterday's offers + 早 8 点发邮件

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Match | Inverted index | Full scan：N×M 慢 |
| Channel | User config | Default all：spam |
| Rate limit | Per-user cap | 无：unsubscribe |
| Personalization | ML ranking | Random：低 CTR |

## 容量估算

- 1M offers/day × 1k matched subscribers avg = 1B notifications/day = 12k QPS
- Push fan-out: 12k QPS → FCM / APN handle 这 scale

## 易错点

> [!pitfall]
> ❌ N×M scan match → 慢；用 inverted index；
> ❌ 不 rate limit → spam unsubscribe；
> ❌ Single channel → 用户 missed；
> ❌ 不 personalize → 低 CTR；
> ❌ Geo 用 lat/lng range query → 慢；用 H3 / S2 cell。

> [!key]
> 三大要点：(1) **Inverted index matching** 处理 1M×100M 配对；(2) **多 channel + rate limit + frequency cap**；(3) **ML personalization ranking**。

> [!followup]
> "Flash sale rate limit 不 dropping 重要 user？" → user importance 加权；"实时 inventory check (offer 已售完不再 push)？" → inventory service 联动；"如何 measure success？" → CTR / conversion / unsubscribe rate；"GDPR opt-out？" → unsubscribe link + 即时生效。
