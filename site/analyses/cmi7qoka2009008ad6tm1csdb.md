## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Offer / Deal** | 商家发的优惠 (e.g., "iPhone 八折") | 报纸上的折扣广告 |
| **Subscription** | 用户订阅了某类目 / 商家 | 订报纸 |
| **Pub/Sub** | 发布订阅模式 | 报社发报，订户收 |
| **Fan-out (写时)** | 一条 offer → 立即写到每个订户的 inbox | 发报员挨家挨户送 |
| **Fan-out (读时)** | 用户查 feed 时再去 query 所有订阅的源 | 订户来报亭翻所有今天的报纸 |
| **Notification channels** | push (APNs/FCM), email, SMS, in-app | 多种到达用户的途径 |
| **User preference** | 用户偏好（class, brand, price range） | 客户画像 |
| **Geofencing** | 基于位置过滤 (附近商家优惠) | "你在购物中心附近，附近店有 deal" |
| **Idempotency** | 同 offer 不能重复通知用户 | 同一份报纸不送两次 |
| **Throttling** | 限制单用户每天 notification 数量 | 每天最多塞 10 张广告单 |
| **Real-time vs scheduled** | 立即推送 vs 定时（如 daily digest） | 突发新闻 vs 早报 |

---

## 1. 题目本质

**E-commerce Offer Subscription** = 商家发优惠 → 系统按用户订阅 + 偏好匹配 → 实时/批量通知。

**典型产品**：
- **Amazon Daily Deals** / **Wishlist alerts**
- **Groupon** —— deal-of-the-day mass marketplace
- **京东预约 / 双 11 抢购**
- **Slickdeals** —— UGC + alerts
- **CamelCamelCamel** —— Amazon price alert
- **Best Buy / Target deals app**

**为什么这是 STAFF 题**：

考的是**pub/sub + 个性化 + multi-channel 通知**：

1. **千万级 user × 百万级 offer** 的匹配
2. **Fan-out 策略**：write fan-out vs read fan-out
3. **Multi-channel delivery** (push / email / SMS / in-app) + dedup
4. **User preference + geofence** filter
5. **Throttling**：不能 spam 用户

考 STAFF 关键：**不是简单 pub/sub，是匹配 + 节流 + 多 channel**。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `Subscribe(user, category | merchant | keyword | price_range)` | 订阅 |
| `Unsubscribe(user, subscription_id)` | 退订 |
| `PublishOffer(merchant, offer_data)` | 商家发优惠 |
| `GetUserFeed(user, page) -> offers[]` | 用户的优惠 feed |
| `SetPreferences(user, prefs)` | 用户偏好 |
| `MuteUntil(user, time)` | 静音 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Delivery latency** | breaking deal < 5 min 到 99% subscribers |
| **Scale** | 100M users, 10M subscriptions/user (avg 50 per user) → 5B subscription rows |
| **Offer throughput** | 100k new offers/day = 1.2 QPS sustained, 100 QPS peak |
| **Notification rate** | < 5 push notifications / user / day (avoid spam) |
| **Reliability** | offers must reach subscribed users (at-least-once) |

---

## 3. 容量估算

- 100M users × avg 50 subscriptions = 5B subscription rows × 50 B = 250 GB
- 100k offers/day × avg 100 matching subscribers = 10B notification events/day = **115k notification QPS sustained**, 1M peak
- Storage offers: 100k/day × 5 KB × 365 = 180 GB/year + S3 archive

---

## 4. 关键 trade-off: Write vs Read Fan-out

### Option A: Write fan-out (push, like Twitter feed)

```
Merchant publishes offer
  → Service finds all matching subscribers (e.g., 1M users)
  → Insert 1M rows into "user_feed" table
  → Send 1M push notifications
```

**优点**：read 简单 (just SELECT from user_feed)
**缺点**：write amplification (1 offer → 1M writes)。如果 100k offers/day × avg match 1k = 1亿 writes/day. Borderline。

### Option B: Read fan-out (pull, like Gmail)

```
Merchant publishes offer
  → Store in offers table by (category, merchant, ...)
  → User opens app → service queries "what offers match my subs in last 24h?"
```

**优点**：write 便宜 (1 row per offer)
**缺点**：read 复杂 + slow，每用户每次 query 都要 cross-join sub × offers

### Option C: Hybrid (推荐)

- **Real-time push notifications**: write fan-out for matched subscribers (limited to opt-in for push)
- **In-app feed query**: read fan-out (pull on demand)
- **Email digest**: batch fan-out daily/weekly (write to email queue once a day)

**Why hybrid**:
- Push 需要立即到达 → write fan-out
- In-app feed 多数用户每天打开 1-2 次 → read fan-out OK
- Email 是 batched scheduled → batch write fan-out

---

## 5. 高层架构

```
┌──────────────────────────────────┐
│  Merchant Portal                  │
│  PublishOffer(category, ...)      │
└──────────────────────────────────┘
              ↓
┌──────────────────────────────────┐
│  Offer Service                    │
│  - Validate + dedup               │
│  - Store offer (Spanner)          │
│  - Emit Kafka event               │
└──────────────────────────────────┘
              ↓
┌──────────────────────────────────┐
│  Match Service                    │
│  - For each new offer:            │
│    1. Find matching subscriptions │
│    2. Apply user preference       │
│    3. Apply geofence              │
│    4. Apply throttle (per user)   │
│    5. Emit "notify" events        │
└──────────────────────────────────┘
              ↓
┌──────────────────────────────────┐
│  Notification Dispatch            │
│   ├── Push (APNs/FCM)             │
│   ├── Email (SMTP/SendGrid)       │
│   ├── SMS (Twilio)                │
│   └── In-app inbox write          │
└──────────────────────────────────┘
              ↓
┌──────────────────────────────────┐
│  User Devices                     │
└──────────────────────────────────┘
```

### Step 1: Offer ingestion

Merchant 发 offer → 立即存 + 标记 `category, merchant_id, price, location, expires_at`。

### Step 2: Subscription matching

Match service consume Kafka `offer.created`:
- Query subscriptions: `SELECT user_id FROM subscriptions WHERE category = ? AND (price_range matches) AND ...`
- Returns list of user_ids (could be 1M)

**Indexing**:
- `(category, active=true)` index
- `(merchant_id, active=true)` index
- Compound: `(category, price_max, active)` 等

For very common subs (e.g., "Electronics" 10M subs)：分批 emit notify events.

### Step 3: Preference + Throttle filter

For each candidate user:
- Check user preferences (e.g., excluded brands)
- Check throttle ("user X already got 5 today")
- Check do-not-disturb hours
- If pass → emit `notify` event to dispatch queue

### Step 4: Dispatch

Multiple channels in parallel:
- Push: APNs/FCM (Kafka topic `push.send`)
- In-app inbox: write to `user_inbox` table
- Email: queue to email batcher (daily digest)
- SMS: opt-in only, rare events

### Step 5: Dedup

Same offer + same user must not notify twice across channels. Use `offer_id × user_id` dedup key in Redis (TTL = offer expires).

---

## 6. 组件深挖

### Deep Dive 1: Subscription Matching Performance

**Naive**: SELECT * FROM subscriptions WHERE category = ? → 10M rows scan slow.

**Index design**:

```sql
CREATE INDEX idx_subs_cat ON subscriptions(category, active);
CREATE INDEX idx_subs_merchant ON subscriptions(merchant_id, active);
CREATE INDEX idx_subs_price ON subscriptions(price_max);  -- for "below X" subs
```

**Offer matching query** (for category=Electronics, price=500):
```sql
SELECT user_id FROM subscriptions
  WHERE active=true
    AND (category = 'Electronics' OR merchant_id = 'AppleStore')
    AND (price_max >= 500 OR price_max IS NULL)
```

**Sharding**: subscriptions table sharded by `user_id` (each user's subs co-located)。But the matching query scans across shards (scatter-gather).

**Alternative**: invert index → `category_to_users` table 直接 lookup user_ids by category.

### Deep Dive 2: Geofence Matching

User 在购物中心附近 → 优先 push 附近店 offer.

```
Geo index: subscriptions with `match_radius_km` and current `user_location`

Query: offer in lat/lng → R*-tree query → users with active geo subscriptions within radius
```

**Implementation**:
- Redis GEOADD / GEOSEARCH (O(log N) for radius queries)
- Or PostGIS / S2 Geometry

### Deep Dive 3: Multi-channel Delivery + Dedup

Same user might be subscribed via push + email. **Don't notify twice**.

**Dedup strategy**:
- Single notify event per (user, offer) → dispatch decides channels
- Channel priority: push > in-app > email
- 24h dedup window in Redis

```python
def dispatch(notify_event):
    user, offer = notify_event
    key = f"notify_dedup:{user}:{offer}"
    if redis.exists(key):
        return  # skip duplicate
    redis.set(key, 1, ex=86400)
    
    for channel in user.preferred_channels:
        send(channel, user, offer)
```

### Deep Dive 4: Throttle (Anti-spam)

Goal: max N notifications / user / day.

**Token bucket**:
```python
def can_send(user_id):
    bucket = redis.get(f"throttle:{user_id}")
    if bucket > 0:
        redis.decr(f"throttle:{user_id}")
        return True
    return False

# Refill每天 midnight: SET throttle:* to N
```

**Smart throttling**: pick "best" offer to send (highest CTR predicted) when over budget。Otherwise queue for next day.

### Deep Dive 5: Push Delivery at Scale

1M push/sec sustained：

- **APNs**: Apple 限制 connection 数 (use HTTP/2 multiplexing)，throughput 大约 10k/sec/connection
- **FCM (Google)**: HTTP batch API (100 tokens per call) → 较高 throughput
- **Internal**: 100 push workers maintain APNs/FCM connections, consume Kafka push.send topic

**Token refresh**: device token rotation handled via app SDK; service detects invalid → mark stale.

### Deep Dive 6: Daily Digest Email

**Different pattern from push**:

- All matched offers throughout day → buffer
- 8 AM local time per user → email worker pull buffered offers → format HTML → send via SendGrid

Per user: 100 candidate offers/day → rank top-10 by relevance + recency → email。

### Deep Dive 7: Offer Expiration

Offers have `expires_at` (e.g., "ends Sunday midnight"):

- When time approaches expiry: re-notify? (e.g., "ending in 1 hour" reminder for limited stock)
- After expiry: hide from feed, retain in DB for analytics

**TTL job**: Cron every 5 min check `expires_at < now` → soft delete + clean up.

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：channels (push/email/in-app)? geofence? batch vs real-time? |
| 5-10min | 容量：100M users, 5B subscriptions, 100k offers/day |
| 10-15min | Fan-out 决策：hybrid push 实时 + pull in-app + daily digest email |
| 15-25min | 高层架构：Offer → Match → Filter → Dispatch (channels) |
| 25-40min | Deep dives: matching index / geofence / dedup / throttle |
| 40-45min | push API scale / digest / expiry |

---

## 8. 样板讲解稿

> Offer subscription 关键 trade-off 是 **write fan-out vs read fan-out**。
>
> **决策**：**hybrid**
> - **Push notifications**: write fan-out (实时性强)
> - **In-app feed**: read fan-out (查时再聚合)
> - **Email digest**: batch fan-out (daily, write 一次给 email worker)
>
> **架构**：
> 1. Merchant publishes → Offer Service (validate + store) → Kafka
> 2. **Match Service**: query subscriptions by category/merchant/price → user list
> 3. **Filter**: user preference + geofence + throttle
> 4. **Dispatch**: multi-channel parallel (push/email/in-app/SMS)
> 5. **Dedup**: Redis key (user × offer) prevent duplicates
>
> **Indexes**: `(category, active)`, `(merchant, active)`, geofence via Redis GEO or PostGIS。
>
> **Anti-spam**: token bucket (N notif/day per user), smart prioritization。
>
> Numbers: 100M users × 50 subs = 5B subscription rows, 100k offers/day, 1M push peak QPS.

---

## 9. Follow-up Q&A

### Q1: "1M user 订阅 Electronics 类，一个 offer 怎么 notify 全部？"

**A**：
- Match service partition fan-out: 1M users → divided into 1000 batches × 1000 users
- 每 batch 通过 Kafka push.send 流水线 dispatch
- APNs/FCM HTTP/2 multiplex 100 push workers → 1M tokens 在 ~1 min 内全推完

### Q2: "user 在 push + email 都订了，怎么不双发？"

**A**：dispatch service 维护**单一 notify event** per (user, offer) → 根据 user.preferred_channels 选 channel。Redis dedup key `notify:{user}:{offer}` TTL 24h 防 retry 重复。

### Q3: "用户每天最多 5 个 notification 怎么实现？"

**A**：
- Token bucket per user, daily refill (cron midnight set to 5)
- Match 时检查 bucket > 0 否则 drop / queue
- **Smart**: 不是 first-come, 而是 prioritize by predicted CTR (ML model) → 给用户 5 个最相关的

### Q4: "如果 offer 5 min 失效，怎么快速 retract notification？"

**A**：
- Push 已发送的不能撤回（APNs 不支持）
- App-side：notification 内嵌 expiration timestamp，client 显示前 check
- In-app feed: server filter expired
- 防止：发 push 前 check `expires_at - 5min < now` → 不发

### Q5: "User 改 preferences 后，pending notifications 怎么办？"

**A**：
- Match 是 stateless query → 下次新 offer 直接用 latest preferences
- Pending notifications (already in Kafka queue): dispatch 时再 check user preferences → drop 不符合的
- 已 push 出去的不能撤回

### Q6: "怎么 A/B test notification 文案？"

**A**：
- Dispatch service knows user's bucket
- Render notification text by template (variant A vs B)
- Track CTR per variant via tracking pixel / link
- Conversion model retrain

### Q7: "Subscriptions DB 5B rows 怎么 scale？"

**A**：
- Sharded by user_id (each user's subs together)
- Cross-shard inverted: maintain `category_to_users` secondary index in separate KV (Cassandra)
- Most matching queries hit secondary inverted, no scatter-gather

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **Pure write fan-out** → push works but in-app feed write amplification high
2. **Pure read fan-out** → real-time push 无法实现
3. **Sub matching is full scan** → 10M subs 慢
4. **没 dedup** → 多 channel 双发，spam 用户
5. **没 throttle** → 用户 angrily 卸载
6. **Push 用单一 connection** → 1M push 要小时
7. **没考虑 offer expiration** → 过期 offer 仍 push

### ✅ 加分项

1. **Hybrid fan-out** based on channel
2. **Inverted index for matching** (category → user list)
3. **Token bucket throttle** + smart prioritization
4. **Multi-channel dedup via Redis** key (user × offer)
5. **APNs HTTP/2 multiplexing** for throughput
6. **Geofence via Redis GEO / PostGIS**
7. **Daily digest batching** for email
8. **ML model** for CTR-based prioritization

> [!key] STAFF vs SENIOR：能讲清"hybrid push / pull / batch 三种 fan-out 同时存在 + dedup + throttle"是 STAFF；只说 pub/sub 是 SENIOR。

---

## 11. Cheat Sheet

```
3 种 fan-out 共存:
  - Push: write fan-out (即时)
  - In-app feed: read fan-out (lazy)
  - Email digest: batch fan-out (daily)

架构层次:
  Merchant → Offer Service → Kafka
                              ↓
                          Match Service (find matching users)
                              ↓
                          Filter (prefs/geo/throttle)
                              ↓
                          Dispatch (push/email/in-app/SMS)
                              ↓
                          Dedup (Redis key)
                              ↓
                          Channel-specific delivery

Sub matching:
  Indexes: (category, active), (merchant, active)
  Inverted: category → [user_ids] (Cassandra)
  Geofence: Redis GEO / PostGIS

Anti-spam:
  Token bucket per user, refill midnight
  Smart prioritization (ML CTR predict)
  Do-not-disturb hours

Dedup:
  notify:{user}:{offer} in Redis, TTL 24h

数字:
  100M users × 50 subs = 5B rows
  100k offers/day → 10B notifications/day (raw)
  Filtered by throttle → ~5/user/day = 500M
  Push peak 1M/sec
```
