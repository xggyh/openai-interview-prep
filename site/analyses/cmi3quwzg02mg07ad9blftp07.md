## 题目本质

设计 **Fast Food Restaurant Chain Management System**：McDonalds / Subway 类全球连锁的 IT 系统：POS、库存、订单、会员、餐厅运营。

## 需求

- 30k+ 餐厅全球
- 高峰每秒 100k 订单
- 实时库存
- 会员 + 积分
- 餐厅 offline 时仍可下单

## 整体架构

```ascii
   Customer (mobile / kiosk / POS)
       │
       ▼
  ┌──────────────┐
  │  Order API   │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐    ┌──────────────┐
  │ Order Svc    │ ── │ Inventory    │
  │              │    │ Service      │
  └──┬───────────┘    └──────────────┘
     │
     ▼
  ┌──────────────┐    ┌──────────────┐
  │ Kitchen      │    │ Payment      │
  │ Display      │    │ Service      │
  └──────────────┘    └──────────────┘
         │
         ▼
  ┌──────────────┐
  │ Per-Restaurant│  local DB sync periodically
  │ Edge Server   │
  └──────────────┘
         │
         ▼
  Cloud Backend ← analytics, supply chain, member
```

## 核心组件

### 1. Hybrid edge + cloud

每餐厅有 local edge server (NUC / mini-PC)：
- 本地 cache menu / prices / inventory
- Local POS 可 offline 操作
- 每分钟 sync 到 cloud（订单上报、inventory pull）

**Why edge**：30k 餐厅同时连 cloud → 网络抖动时不能停业。

### 2. Inventory tracking

每 restaurant 每 item current count：
- POS 减库存（订单 confirm 后）
- 收货增库存
- Inventory event 写本地 + 异步 sync cloud

低库存 alert：local alert + cloud aggregated forecast。

### 3. 订单 lifecycle

```
placed → kitchen prep → ready → delivered → completed
                                      ↓ refund
                                  cancelled
```

每 status change emit event。

### 4. Kitchen Display System (KDS)

订单 push 到厨房屏幕。按 priority + ETA 显示 ticket。完成时员工 tap → ready。

### 5. 会员 + 积分

中心 member service（不在 edge）。Loyalty point = order total × multiplier。Async crediting (5 分钟内显示在 app)。

### 6. Payment

- Credit card：external gateway (Square / Stripe)
- 移动支付：Apple Pay / Google Pay / Alipay
- Cash：POS 自己 reconcile

### 7. 实时 analytics

每订单 emit event → Kafka → Flink → 实时 metric：
- Per-store hourly revenue
- Hot items
- Order wait time

Manager dashboard 看实时 + 日报告。

### 8. Supply chain

每 store inventory level → forecast model → 供应商 PO。自动 reordering when below threshold。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Edge | Per-store mini server | Cloud only：offline 停业 |
| Inventory | Eventual consistency | Strong：跨 store 慢 |
| Order ID | Snowflake | UUID：sort 难 |
| KDS sync | Local + push | Pull：延迟 |
| Member | Central | Per-store：积分错乱 |

## 容量估算

- 30k store × 100 orders/hour peak = 3M orders/hour = 833 orders/sec
- 边缘 server CPU 4 core + 16 GB 足够
- Cloud 主要 analytics + member + supply chain

## 易错点

> [!pitfall]
> ❌ Cloud-only architecture → 网络抖动停业；
> ❌ Inventory 强一致 → 跨 store 写延迟；
> ❌ KDS 全 cloud → 厨房显示卡；
> ❌ Member 数据 per-store → 跨店积分丢；
> ❌ 订单 ID 用 auto-increment → 不能离线生成。

> [!key]
> 三大要点：(1) **Edge + Cloud hybrid** 处理 offline；(2) **Inventory eventual consistency + 本地权威**；(3) **Member / supply chain central + analytics 实时**。

> [!followup]
> "Mobile order ahead (skip-the-line)？" → app order + ETA → KDS 提前 prep；"Drive-thru 优化？" → CV count cars + wait time predict；"国际化 menu / 价格？" → per-region config service；"实时 menu 更新（item out of stock）？" → push from KDS 到 customer-facing apps。
