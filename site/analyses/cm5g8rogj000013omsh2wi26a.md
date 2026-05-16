## 题目本质

**Design a Ticket Booking System (Product Architecture)** —— 参考 [[cm4szwvht003pnqlrkhad2xjd]] (System Design Ticket Booking)。这个分类是 Product Architecture 而非 System Design —— focus 更产品 + 模块化思维。

## Product Architecture 视角

Product Arch 的不同：
- 不只是 backend system，含 **frontend module + business logic + admin tool**
- **Module boundaries** 是核心
- **Customer journey** 驱动设计

## Modular Breakdown

```
┌────────────────────────────────────────┐
│   User-facing Apps                     │
│   - Web (search, booking, account)     │
│   - Mobile (iOS/Android)               │
│   - Kiosk (event venue)                │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│   Backend Services                     │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Event       │  │ Inventory   │      │
│  │ Catalog     │  │ (Seats)     │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Booking     │  │ Payment     │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Notification│  │ Reporting   │      │
│  └─────────────┘  └─────────────┘      │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│   Admin / Organizer Tools              │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Event Mgmt  │  │ Seat Map    │      │
│  │ (organizer) │  │ Builder     │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Pricing     │  │ Analytics   │      │
│  │ Engine      │  │ Dashboard   │      │
│  └─────────────┘  └─────────────┘      │
└────────────────────────────────────────┘
```

## 关键 Module 设计

### 1. Event Catalog Service

```python
class Event:
    id: UUID
    organizer_id: UUID
    name: str
    venue_id: UUID
    start_at: datetime
    duration_min: int
    category: str
    description: str
    image_urls: list[str]
    pricing_tiers: list['PricingTier']
    status: 'draft' | 'published' | 'sold_out' | 'cancelled'

class PricingTier:
    id: UUID
    name: str            # "VIP", "Standard"
    seat_zone_ids: list[UUID]
    base_price: Decimal
    fees: Decimal
```

Public API: search / filter / get details。Admin API: create / update / publish。

### 2. Inventory (Seat Map) Service

Per event 的 seat 状态：available / held / sold。详见 [[cm4szwvht003pnqlrkhad2xjd]]。

抽象：每 venue 一个 SeatMap（reusable across events at same venue）。

### 3. Booking Service

Booking 流程 state machine：

```
created → seats_held → payment_pending → confirmed
                  ↓                ↓
              expired          payment_failed
```

每 booking 含 user_id, event_id, seat_ids, total, status。

### 4. Payment Service

集成多 gateway (Stripe / PayPal / Alipay)。Saga pattern handle distributed transaction。

### 5. Notification Service

Channel：email (ticket PDF), SMS, push。多语言 template。

### 6. Reporting / Analytics

Real-time dashboard for organizer:
- Tickets sold by tier
- Revenue
- Refund rate
- Funnel (viewed event → started booking → paid)

### 7. Organizer Tools

- Event creation wizard
- Seat map builder (drag & drop 类似 Canva)
- Pricing rules (dynamic pricing based on demand)
- Promo codes
- Refund management

## 商业逻辑

### Pricing strategy

- Fixed tier
- Dynamic (high demand → ticket price 上涨)
- Group discount
- Early bird

Engine 独立 service，可配 rules。

### Refund

Cancellation window + 部分 refund (扣 service fee)。Bookings table 有 refundable_until。

### Resale

Authorized resale market (StubHub-like)。Original ticket 在系统里 transfer 给买家。

## Module 边界

Domain-Driven Design 思考：
- **Bounded context**：Event, Inventory, Booking, Payment 是 separate context
- **Anti-corruption layer**：跨 context 通信用 well-defined contracts，不要 share DB

## 易错点

> [!pitfall]
> ❌ Booking module 直接读 inventory DB → coupling；用 API；
> ❌ Pricing logic 嵌在 booking → 不可复用；分离 service；
> ❌ Notification 同步发 → 慢 + fail block booking；async；
> ❌ Organizer tool 共享 customer DB → 性能影响；分离 read replica；
> ❌ Admin module 没 audit → compliance fail。

> [!key]
> Product Architecture vs System Design：**前者 module / domain boundary，后者 service / infra**。Ticket booking 在 product view 更强调 organizer tools + customer journey + pricing engine。

> [!followup]
> "如何 multi-tenant (multiple ticket platforms 用同 backend)？" → tenant_id 在所有 row + RBAC isolation；"如何 internationalization？" → i18n service for text + currency conversion；"如何 mobile-first？" → API design responsive，offline caching for event browsing。
