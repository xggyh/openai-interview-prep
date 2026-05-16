## 题目本质

**Design a log storage service (Product Architecture)** —— 参考 [[cm6jx0wxh016bui4b2oqtwudo]] (System Design Logger System)。Product Arch 视角更聚焦 **API + tenant model + retention tier + UX**。

## Product Architecture 视角

服务作为 product 提供给客户。考虑：
- **Self-service onboarding** (developer copy-paste 1 line setup)
- **Multi-tenant 隔离 + 配额**
- **Pricing tier** (free / pro / enterprise)
- **Query UI** developer-friendly

## Modular Breakdown

```
┌────────────────────────────────┐
│ Ingest Layer                   │
│ - SDKs (Python/Node/Go/...)    │
│ - HTTP / gRPC / syslog endpoint│
│ - Agent (Fluent Bit fork)      │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│ Pipeline Layer                 │
│ - Parsing (JSON / regex)       │
│ - Enrichment (geo, user-agent) │
│ - Filtering (PII redact)       │
│ - Sampling                     │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│ Storage Tier                   │
│ - Hot: searchable (7 days)     │
│ - Warm: cheap query (30 days)  │
│ - Cold: archive (1 year)       │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│ Query / Analytics              │
│ - Full text search             │
│ - SQL-like aggregation         │
│ - Live tail                    │
│ - Saved query / dashboard      │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│ Alerting & Monitoring          │
│ - Rule-based alert             │
│ - Anomaly detection            │
│ - Integration: PagerDuty, Slack│
└────────────────────────────────┘
```

## 关键 Product 决策

### 1. SDK + Endpoint

各语言 SDK。一行 init：

```python
import logservice
logservice.init(api_key='xxx')
import logging
logging.info("user logged in", extra={"user_id": 42})
```

SDK 内部 batch + async ship to ingest endpoint。

### 2. Multi-tenant model

每 tenant：
- API keys (rotate-able)
- Quota (events/day, storage GB, retention days)
- Configurable parsing pipeline
- Custom dashboard

Storage 物理 isolation: per-tenant index/partition + RBAC。

### 3. Pricing tier

- **Free**: 1 GB/day, 7 days retention
- **Pro**: 100 GB/day, 30 days, basic alerting
- **Enterprise**: unlimited, 1 year cold, SSO, audit log, dedicated support

### 4. Retention tier UX

User dashboard 显示 hot / warm / cold breakdown。Query > 30 day 自动 trigger cold query (with "may take few minutes" warning)。

Smart：frequently queried recent data 自动 hot；rare query 老数据 stay cold。

### 5. Query language

DSL 类 KQL / SPL:
```
service:foo AND level:error
| stats count() by host
| sort -count
| limit 10
```

或 SQL on logs (DuckDB / Snowflake style)。

### 6. Live tail

WebSocket: `tail "service:foo"` → 实时 push matching log entries。Developer debug 友好。

### 7. Alerting

UI rule builder：
```
WHEN error_count > 100 IN 5min FOR service:checkout
THEN notify #oncall
```

Email / Slack / PagerDuty / webhook channels。

### 8. Self-service onboarding

Funnel:
1. Sign up → get API key (instant)
2. SDK setup (copy-paste, 5 lines)
3. First log appears in UI ~10 sec
4. Sample dashboard auto-generated

降低 friction = retention。

### 9. Compliance features

- SOC 2 Type II / HIPAA / GDPR
- PII detection + redaction
- Data residency (EU / US / APAC)
- Audit log (who queried what)

Enterprise tier 卖点。

## Differentiation vs Splunk / DataDog

- **Modern UX** (Splunk old, DataDog complex)
- **Cheaper cold tier** (S3 Parquet vs Splunk indexer)
- **Open OTel standard** (avoid vendor lock-in)
- **AI-powered insights** (auto anomaly, summary)

## 易错点

> [!pitfall]
> ❌ 不 multi-tenant isolation → cross-customer data leak；
> ❌ Hot tier 全 30 days → 成本爆 (10x of S3 Parquet)；
> ❌ Self-service onboarding 麻烦 → developer 不 stick；
> ❌ 无 audit log → enterprise 不买；
> ❌ Query language too custom → 学习曲线 high。

> [!key]
> Log service as a product = **SDK + ingest + tiered storage + query + alert + multi-tenant isolation + pricing tier**。区别于 internal logger (cm6jx0wxh016bui4b2oqtwudo) 的关键是 product features：onboarding, pricing, compliance, dashboard。

> [!followup]
> "如何 attract enterprise customer？" → SSO, audit, compliance cert, dedicated support；"如何 prevent log data abuse (customer mining other tenant data)？" → strict RBAC + per-tenant resource quota；"如何 OTel ecosystem integration？" → native OpenTelemetry collector support。
