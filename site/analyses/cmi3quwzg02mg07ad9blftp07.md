## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **POS** | Point of Sale，收银机 + 软件 | 收银台 |
| **Kitchen Display System (KDS)** | 后厨显示器，显示订单 + 状态 | 厨房的电子菜单 |
| **Edge server** | 装在门店本地的小服务器，offline 也能 work | 门店保险柜 |
| **Inventory** | 库存（牛肉饼 / 面包 / 番茄酱）| 仓库存货 |
| **Eventual consistency** | 数据各点最终会一致，但短期可能不同步 | 全国分店每天对一次账 |
| **Edge computing** | 在边缘（门店）处理，不全靠云 | 门店自给自足 |
| **CDC** | DB 变化通知 | "我加菜单了，告诉云" |
| **Multi-tenant** | 不同 franchisee（加盟商）数据隔离 | 一栋楼多家公司 |
| **Saga** | 分布式事务，每步 compensating | 接力跑跑错往回跑 |
| **Loyalty program** | 会员积分 / 优惠 | 集邮票 |
| **PCI DSS** | 支付卡数据合规标准 | 银行级别安全规范 |

---

## 1. 题目本质 — 这是什么问题

**Fast Food Restaurant Chain Management System** = 一套软件，让一个连锁餐厅集团（McDonalds 40k 店 / Subway 40k 店 / 蜜雪冰城 38k 店）运营：

1. **门店运营**：POS 收银 + KDS 厨房显示
2. **订单管理**：堂食 / 外卖 / 自取 / 外卖平台聚合
3. **库存管理**：实时 + 自动补货
4. **会员 + 积分**：跨店通用
5. **供应链**：自动下 PO 到供应商
6. **运营分析**：每店 / 每区 / 全国 metrics

**为什么这道题难**：

1. **30k+ 门店全球**，每店网络 / 设备 / 操作员千差万别
2. **门店 offline 不能停业**：断网 5 分钟仍要能收单
3. **高峰订单 burst**：午餐 12-13 点全国 100k+ 订单/分钟
4. **跨店会员**：北京会员上海消费要算分
5. **多 tenant**：franchisee（加盟商）有自己 admin，但总部要全局 view
6. **多渠道下单**：堂食 / app / 外卖 (美团 / Uber Eats / DoorDash)

考点：**Edge + Cloud 混合架构 + Eventual consistency + Multi-tenant + 业务系统集成**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：哪些渠道下单？  
**典型答**：(a) 堂食 (POS)；(b) 自家 app；(c) 外卖 third party (Uber Eats, DoorDash, 美团)；(d) 自助 kiosk。

**你问**：门店断网时怎么办？  
**典型答**：必须能 offline 收单。Sync 上线后。

**你问**：实时库存 / 餐厅状态（卖完了某 item）显示给 app 用户吗？  
**典型答**：要。卖完 Big Mac 时 app 不能再下单。

**你问**：会员 / 积分跨店通用？  
**典型答**：要。全国 / 全球通用。

**你问**：franchisee 多 admin？  
**典型答**：是。每 franchisee 看自己店面，总部看全国。

### 2.2 非功能性

**你问**：店面规模 / 订单量？  
**典型答**：30k 门店全球，peak 100k 订单 / 分钟全国 = ~1700 QPS。

**你问**：订单端到端响应？  
**典型答**：POS 录单 → KDS 显示 < 2 秒。

**你问**：库存更新延迟？  
**典型答**：5-10 秒（卖完 propagate to app 用户）。

**你问**：法规 / 合规？  
**典型答**：PCI DSS (支付卡)，GDPR (用户数据)，per-country tax law。

### 2.3 需求清单

```
功能：
- POS / KDS / Inventory / Loyalty / Supply Chain / Analytics
- 多渠道下单 (堂食 / app / 第三方外卖 / kiosk)
- Offline 操作
- 跨店会员
- Multi-tenant (franchisee + corporate)

非功能：
- 30k stores
- Peak 1700 QPS order
- < 2s POS-to-KDS
- 库存 5-10s 同步
- PCI/GDPR
```

---

## 3. 容量估算

### 3.1 订单量

```
30k stores × peak hour 200 orders/h = 6M orders/h global = 1700 orders/sec
× 100B record = 170 KB/sec write to cloud

每店 local 200 orders/h = 0.06 order/sec → 单 edge server 轻松
```

### 3.2 库存 events

```
每订单 use 5-10 ingredients → 10000 inventory events/sec global
但 mostly local (店内决策) → cloud-bound 仅 summary
```

### 3.3 数据存储

```
全球 365 day × 6M orders/h × 24h × 365 = ~50B orders/year
× 1 KB/record = 50 TB/year
+ inventory + loyalty + analytics = ~200 TB/year
```

### 3.4 估算清单

```
Per store: 0.1 QPS sustained
Global: 1700 QPS peak  
Cloud network: 几 MB/sec aggregate (most stays local)
Storage: 200 TB/year
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：纯云方案（行不通）

```ascii
   Store POS → Internet → Cloud Backend
```

**问题**：
- 门店网络抖动 → POS 卡，付款失败
- 总部网络挂了 → 全国 30k 店都停业 → 灾难
- 即使网络好，跨洋延迟 > 200 ms 影响 POS UX

### 4.2 第 1 步：Edge + Cloud 混合

每店一个 **Edge Server**（一台 Intel NUC mini-PC）：

```ascii
   Store:
   ┌──────────────────────────────────┐
   │ POS / Kiosk / KDS / Tablet       │
   │     │                            │
   │     ▼                            │
   │  Edge Server (NUC, 16GB RAM)     │
   │  - Local DB (Postgres)           │
   │  - Local cache menu / prices     │
   │  - Order routing                 │
   │  - KDS push                      │
   │  - Inventory tracking            │
   └──────────┬───────────────────────┘
              │ async sync
              ▼
        ┌──────────────┐
        │ Cloud        │
        └──────────────┘
```

**Edge 的工作**：
- POS 录单 → local DB → KDS 推 → 立即 ack 给收银员
- 网络好时 async sync 到 cloud
- 网络断时 buffer 本地，恢复后 sync

**优势**：
- POS < 100ms 响应（本地）
- 断网仍能下单（buffer + replay）
- 网络成本低（只 sync summary，不每订单实时上传）

### 4.3 第 2 步：Inventory 同步策略

**关键 trade-off**：库存是 store-local (本店有多少 patty) 还是 global (全国库存)？

**答**：**Per-store local source of truth**，cloud 是 reporting + supply chain decision。

```python
# 卖一个 Big Mac
def sell_bigmac(store_id):
    # Local DB transaction
    db.execute('UPDATE inventory SET quantity = quantity - 1 WHERE store_id=? AND item="patty"', store_id)
    db.execute('UPDATE inventory SET quantity = quantity - 1 WHERE store_id=? AND item="bun"', store_id)
    # async push to cloud
    queue.put('inventory_event', {store, items, delta})
```

**Cloud aggregation**：每分钟收 events 聚合，触发：
- Reorder (库存低 → 发 PO 给供应商)
- Mobile app inventory display ("This store sold out of Big Mac")

### 4.4 第 3 步：Order Routing (多渠道)

```ascii
   堂食 POS ─────┐
   自家 app ──────┼─→ Cloud Order API ──→ Edge Server (target store) ──→ KDS
   第三方外卖 ──┤
   Kiosk ───────┘
```

**Multi-channel** 不同渠道下单**最终汇到同一 Edge KDS**，否则厨师看 4 个屏幕。

**Cloud → Edge push**：用 WebSocket / Long-poll。Edge 一直连云，云 push 订单 down。

### 4.5 第 4 步：Loyalty (跨店通用)

```ascii
   Customer A 在 Store 1 消费 $10
        │ POS 扫 customer QR / phone
        ▼
   Edge Server:
     - Local price + tax 计算
     - Async POST cloud: { user_id, store, amount, ts }
        │
        ▼
   Cloud Loyalty Service:
     - Update user.points (在 central DB)
     - Notify user app (推送 "你得了 X points")
```

**Trade-off**：loyalty 用 **central DB 强一致** —— 用户 next time 5 秒后查 points，必须看到最新值。

如果 Edge 断网，loyalty event buffer 本地，sync 后 cloud 加分。**用户即时显示** 可以 trust edge 算的（offline 加分）+ later reconciled。

### 4.6 第 5 步：完整架构

```ascii
┌────────────────────── Store (30k) ─────────────────────────┐
│                                                             │
│  POS / Kiosk / KDS / Tablet                                 │
│     │                                                       │
│     ▼                                                       │
│  Edge Server (NUC)                                          │
│  - Local Postgres                                           │
│  - Order / Inventory / Print receipt                        │
│  - Background sync to cloud                                 │
└──────────┬──────────────────────────────────────────────────┘
           │ async + reliable (Kafka edge)
           ▼
┌────────────────── Cloud Backend ───────────────────────────┐
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Order    │ │ Inventory│ │ Loyalty  │ │ Supply   │        │
│  │ Service  │ │ Agg      │ │ Service  │ │ Chain    │        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘        │
│       │            │            │            │              │
│       ▼            ▼            ▼            ▼              │
│  ┌──────────────────────────────────────────────────┐       │
│  │ Cloud DB (Spanner / Aurora)                      │       │
│  │ + Analytics warehouse (BigQuery)                 │       │
│  └──────────────────────────────────────────────────┘       │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Customer │ │Franchisee│ │ Corporate│ │ Supplier │        │
│  │ App      │ │Admin     │ │ Dashboard│ │ Integration│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 每个组件深挖

### 5.1 Edge Server 详细

**硬件**：Intel NUC / Mac mini class，16 GB RAM，1 TB SSD。

**软件 stack**:
- OS: Linux  
- Local DB: Postgres (orders, inventory, loyalty events)
- Application: containerized Java / Python
- Communication: Kafka producer (push to cloud), WebSocket consumer (recv from cloud)

**Resilience**:
- Power outage: UPS 1 小时
- Hardware fail: 总部寄备机 → 客户重启用
- Data loss: 每天 incremental backup to cloud + 1 month retention

### 5.2 Order State Machine

```python
class OrderStatus:
    PLACED = 'placed'               # 下单
    KITCHEN_PREP = 'kitchen_prep'   # 厨房做
    READY = 'ready'                 # 做好
    HANDED_OFF = 'handed_off'       # 给顾客
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

# Transitions (state machine)
ALLOWED = {
    PLACED: {KITCHEN_PREP, CANCELLED},
    KITCHEN_PREP: {READY, CANCELLED},
    READY: {HANDED_OFF, REFUNDED},
}
```

每 state transition 触发 event → Kafka → cloud analytics + customer notification ("Your order is ready")。

### 5.3 Database schema

```sql
-- Local (Edge) DB
CREATE TABLE orders (
  id              UUID PRIMARY KEY,
  store_id        UUID,
  customer_id     UUID,
  channel         TEXT,         -- 'pos' / 'app' / 'doordash' / 'ubereats'
  items           JSONB,        -- [{sku, qty, price, modifiers}]
  total_cents     BIGINT,
  status          TEXT,
  payment_id      TEXT,
  placed_at       TIMESTAMPTZ,
  ready_at        TIMESTAMPTZ,
  synced_at       TIMESTAMPTZ,  -- 是否已 sync to cloud
  metadata        JSONB
);

CREATE TABLE inventory (
  store_id        UUID,
  sku             TEXT,
  quantity        DECIMAL,
  last_count_at   TIMESTAMPTZ,
  PRIMARY KEY (store_id, sku)
);

CREATE TABLE pending_sync_events (
  id              BIGSERIAL,
  topic           TEXT,
  payload         JSONB,
  created_at      TIMESTAMPTZ,
  sent_at         TIMESTAMPTZ
);
```

### 5.4 Sync Engine

```python
class SyncEngine:
    """Background process push pending events to cloud."""
    
    async def run(self):
        while True:
            events = db.fetch('SELECT * FROM pending_sync_events WHERE sent_at IS NULL LIMIT 100')
            if not events:
                await sleep(5)
                continue
            
            try:
                # Push to Kafka cluster (cloud)
                await kafka.produce_batch(events)
                # Mark sent
                ids = [e.id for e in events]
                db.execute('UPDATE pending_sync_events SET sent_at = NOW() WHERE id IN (...)', ids)
            except NetworkError:
                # Backoff and retry
                await sleep(30)
```

**保证最终一致性**：网络断了 events buffer 本地，恢复后 push。Postgres replication WAL 类似机制。

### 5.5 Cloud Order Aggregation

```python
# Cloud Order Service consumes Kafka
def handle_order_event(event):
    store_id = event['store_id']
    
    # Persist to central DB
    db.upsert(orders_table, event)
    
    # Update analytics
    analytics_kafka.produce({'event_type': 'order_placed', ...})
    
    # Notify customer (if loyalty member)
    if event['customer_id']:
        notification.push(event['customer_id'], "Order placed at " + event['store_id'])
    
    # Inventory aggregation
    for item in event['items']:
        inventory_kafka.produce({'store_id': store_id, 'sku': item.sku, 'delta': -item.qty})
```

### 5.6 第三方外卖集成

```ascii
   DoorDash app
       │ user places order
       ▼
   DoorDash backend
       │ webhook
       ▼
   Cloud Order API
       │ route to target store
       ▼
   Edge Server
       │
       ▼
       KDS
```

每个第三方平台一个 webhook integration。Order 进来标 `channel='doordash'`。结算时按合同抽成。

### 5.7 Inventory Management

```
Store inventory:
  - Per-SKU count
  - Reorder threshold

Auto-reorder logic:
  When quantity < threshold:
    1. Generate PO (Purchase Order) draft
    2. Send to franchisee admin or auto-approve
    3. Push PO to supplier system
    4. Track expected delivery

ML forecast:
  Per store × per SKU × per day-of-week × seasonality
  → forecast 下周需求 → 自动调 reorder threshold
```

### 5.8 Loyalty 计算

```python
def loyalty_earn(customer, amount_cents, store_id):
    points = amount_cents // 100  # 1 point per $1
    # Multiplier 
    if is_member_tier_gold(customer):
        points *= 2
    # Promo (周二 double points)
    if today_is_double_point_day():
        points *= 2
    
    # Atomic update (Cloud DB)
    db.execute('UPDATE customers SET points = points + ? WHERE id = ?', points, customer.id)
    # Audit log
    insert_audit(customer.id, store_id, points, 'earn')
    return points
```

### 5.9 Multi-tenant (Franchisee + Corporate)

```
RBAC:
  store_employee: read/write own store's POS only
  store_manager: + analytics for own store
  franchisee_admin: + analytics across all franchisee's stores
  corporate_admin: + analytics nationally + can modify menu
  corporate_super: + can disable any franchisee

Data isolation:
  All tables have franchisee_id + store_id
  Query layer enforces filter based on user role
```

### 5.10 Analytics

```
Real-time (last hour):
  - Per-store sales / order count
  - Best-selling items
  - Average wait time
  - Customer NPS (post-order survey)

Daily reports:
  - Per franchisee revenue
  - Inventory waste %
  - Forecast accuracy

ML insights:
  - Demand forecasting (next week)
  - Customer churn prediction
  - Optimal staffing per store per shift
```

存 BigQuery / Snowflake → 跑 SQL + ML。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 渠道（POS/app/外卖）
  - Offline support？
  - 跨店 loyalty？
  - 规模

0:05 - 0:10  Capacity Estimation
  - 30k stores, 1700 QPS peak
  - 大部分 traffic 本地 stay
  - 200 TB/year cloud storage

0:10 - 0:15  High-Level Architecture
  - Edge + Cloud hybrid
  - 每店 NUC + local DB
  - Cloud aggregator + dashboard

0:15 - 0:30  Deep Dive
  ★ Edge server resilience (offline)
  ★ Sync engine (eventual consistency)
  ★ Multi-channel order routing
  ★ Loyalty (cloud strong consistency)
  ★ Multi-tenant RBAC

0:30 - 0:38  Follow-ups
  - 第三方外卖 integration
  - Auto-reorder
  - Analytics / ML

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK fast food chain. Key insight 来源于一个观察：**门店不能因为网络断而停业**。一家 McDonald's 1 小时无 POS = 几万损失。所以核心是 **Edge + Cloud hybrid**。
> 
> 每店一个 mini PC (NUC, 16GB RAM)，跑本地 Postgres + 应用。POS / KDS / Kiosk / Tablet 都连这台 edge server。订单录入：local DB → KDS 推 → < 2 秒响应。**网络断仍能 work**。
> 
> Edge 后台 sync engine 把订单 / inventory / loyalty events 异步 push 到云。Kafka 本地 buffer，断网时不丢。恢复后批量 push。
> 
> 多渠道下单：堂食 (POS) / 自家 app / 第三方外卖 (DoorDash/Uber Eats/美团) / Kiosk —— 全部最终走 cloud Order API → push 到 target store edge → KDS 显示。Edge 是 single source of truth for "什么订单要做"。
> 
> Inventory：**per-store local** 是 truth (因为每个 patty 在哪个店是物理事实)。Cloud 收 events 聚合，触发 auto-reorder PO to supplier，触发 app 库存显示。
> 
> Loyalty：用户跨店要 immediate 看到 points → **cloud central DB 强一致**。Edge offline 加分 buffer，sync 后 reconcile。Trade-off 用户 5 秒内可能看 stale points (offline 期间)。
> 
> Multi-tenant: store_employee / store_manager / franchisee_admin / corporate_admin / corporate_super 五级 RBAC。每 table 含 franchisee_id + store_id，query 强制 filter。
> 
> Dashboards: real-time per-store sales, daily franchisee report, ML demand forecast for 自动 reorder threshold。
> 
> 想 deep dive offline 仍工作详细，还是 multi-tenant RBAC?"

---

## 8. Follow-up 演练

### Q1: Edge server 挂了怎么办？

**答**：
- 总部备机寄付 (overnight)
- 期间临时方案：iPad POS app 直接连云（性能差但 work）
- Cloud 仍能 view recent orders（last sync 前的）

### Q2: 第三方外卖订单丢失，customer 找上来？

**答**：
- DoorDash webhook 有 idempotency key + retry policy
- Cloud 收到去重，落地 + ack DoorDash
- Cloud → Edge push 也 retry + idempotent
- Customer 报告 missing order → query orders by customer_id + window → trace 哪一步丢

### Q3: 怎么处理 menu / 价格 update？

**答**：
- Corporate admin update menu → CDC → 同步 all edge servers
- Pricing rules 复杂（限时 / 区域 / 会员折扣）→ 中心 pricing engine compile rules，push compiled config 到 edge
- 每个 edge 启动 / 周期 pull config

### Q4: 12 点 lunch rush 1700 QPS 怎么 scale?

**答**：
- 大部分 traffic 本地 (POS) 不上云
- Cloud 部分主要是 event ingest (Kafka 撑得住)
- Order API for app/外卖 集中 cloud → auto-scale stateless service
- Dashboard query 慢可 cache

### Q5: 怎么 prevent over-discount (同 user 多次用同 coupon)?

**答**：
- Coupon 有 unique code + redemption limit
- Cloud DB tracks redemptions
- POS scan code → cloud check → return valid / used
- 网络断时 edge 用 stale data，可能 accept 已用 coupon → 风险接受 (rare event，loss 小)

### Q6: GDPR 删除某 user？

**答**：
- Soft delete: customer.deleted_at = NOW()
- Loyalty / orders 保留 (audit 需要)，但 PII (name, email, phone) 替换 hash
- 30 day grace period，硬删 PII
- 跨多 system propagate via event

### Q7: 怎么训练 demand forecast ML?

**答**：
- 历史 order data + weather + holiday + 促销 → features
- Per store × per SKU × per (hour, day-of-week, month) granularity
- Gradient boosting / time series model
- Weekly retrain
- A/B test 准确度
- Forecast 用于 auto-reorder threshold + staffing schedule

---

## 9. 常见易错点

> [!pitfall]
> ❌ **纯 cloud architecture** —— 一断网 30k 店 stop 营业；  
> ❌ **Edge / cloud 不区分 source of truth** —— inventory 究竟以谁为准？应明确 per-store local；  
> ❌ **Loyalty 用 eventual consistency** —— 用户跨店扫积分看不到 immediate 不行；  
> ❌ **不做 channel 归一化** —— 第三方外卖各自不同 webhook 格式，处理乱；  
> ❌ **不做 multi-tenant RBAC** —— franchisee 看到别家数据；  
> ❌ **Auto-reorder 没人监督** —— 错误 forecast 导致大量浪费 / 缺货；  
> ❌ **Menu update 推全店实时** —— 推送爆 + 推时网络挂部分店 stale；用 versioned config + pull；  
> ❌ **不做 idempotency** —— 第三方外卖 webhook 重试 duplicated order。

---

## 10. 加分项

- **Drive-thru optimization**：用摄像头 detect 车队长度 + 预估等待时间
- **AI menu personalization**：app 根据用户口味推荐
- **Voice ordering** in drive-thru (whisper + LLM)
- **Dynamic pricing** (peak hour 微涨 / 闲时打折)
- **Sustainability dashboard**：food waste / energy / packaging
- **Franchisee benchmarking**：自家 vs region avg vs national best
- **Crew scheduling**：ML 根据 forecast demand 安排员工
- **Robot kitchen integration**：自动炒蛋 / 油炸机器人 API

---

## 11. 总结：你应该记住的 3 件事

1. **Edge + Cloud hybrid 是连锁零售 / 餐饮 IT 系统的金科玉律**。所有 customer-facing 操作必须 local，cloud 是 sync + 分析。

2. **明确 source of truth per domain**：inventory 在 store 本地；loyalty / 会员在云；订单同时存两份（local + synced to cloud）。每个 domain 选不同的 consistency model。

3. **Multi-channel ingestion 必须归一化到统一 order schema**。POS / app / 第三方各异的 input format 在 cloud 适配后再 push 到 store edge。

> [!followup]
> **学习推荐**：(a) 读 Square / Toast 这类餐饮 SaaS 的工程博客；(b) 学 Postgres logical replication for edge-cloud sync；(c) 看一篇关于 retail edge computing 的 paper；(d) 跑通 Kafka edge producer + cloud consumer；(e) 思考 "如果未来 30k 店都装 GPU + LLM voice ordering，架构怎么变"。
