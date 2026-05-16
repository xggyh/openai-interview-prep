## 题目本质

设计 **Ad Server**（Google Ads / FB Ads serving）：page load 时 < 100ms select + return relevant ad。Targeting + auction + budget pacing.

## 需求

- 1M+ QPS global
- < 100ms P99 latency
- Targeting: user demographics, interests, geo
- Real-time bid (RTB) auction
- Advertiser budget + frequency capping
- Click / impression tracking

## 整体架构

```ascii
   Page request
       │ page_id, user_id, context
       ▼
  ┌──────────────────┐
  │ Ad Request API   │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐    ┌────────────────┐
  │ Ad Selector      │ ── │ User Profile   │  ML-served features
  │ (candidate gen)  │    │ Service        │
  └──────┬───────────┘    └────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ ML Ranker /      │  predicted CTR × bid
  │ Auction          │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Budget Pacer     │  check budget + frequency cap
  └──────┬───────────┘
         │
         ▼
   Return ad + impression token
         │
         ▼
   Client renders → triggers impression beacon → track service
```

## 核心组件

### 1. Candidate generation

10M active ads → narrow to ~1k candidates for a request:
- Geographic match
- Interest match (user's interest 标签)
- Demographics match
- Budget remaining
- Recent frequency below cap

Inverted index: targeting_attribute → list of ad_ids。Set intersection。

### 2. Ranking + auction

每 ad 有 advertiser bid (per click or per 1k impression)。Server algos:

**Second-price auction**:
- 按 predicted CTR × bid 排序
- Pick top
- Charge winner = (second-place's bid × second's CTR) / winner's CTR + ε

**ML CTR prediction**:
- Features: (ad, user, context, page) → model → P(click)
- Model: gradient boosting / DNN
- Refresh hourly

### 3. Budget pacing

Advertiser sets daily budget. Server pace spending evenly throughout day:
- Hourly budget = daily / 24 × (hourly traffic share)
- 接近 budget exhaustion 时降权 (lower probability of serving this ad)
- 防 burst spend in morning then quiet rest of day

### 4. Frequency capping

Per user：max N times in 24h see same ad。Redis sorted set per user (ad_id → last_seen_ts)。Filter out frequency-capped during candidate gen。

### 5. Real-time bid (RTB)

For external advertisers, exchange protocol:
- Page load → bid request to multiple DSPs (Demand Side Platforms)
- DSPs reply bid + ad
- Auction picks winner
- 全流程 < 100ms

### 6. Tracking

Impression beacon:
```
<img src="https://tracking.example.com/i?ad=X&u=Y&token=Z" />
```

Click tracking:
```
<a href="https://tracking.example.com/c?ad=X&u=Y&redirect=https://...">
```

Async write to Kafka → analytics / billing。

### 7. Fraud detection

Bot clicks invalidate budget。ML on click patterns:
- Same IP many clicks
- Click before impression render
- Click 后 immediate bounce
- Suspicious user agent

Charge backs for detected fraud。

### 8. Privacy

GDPR / CCPA：consent management。Opt-out user 不用 personalized targeting。Cookie deprecation → FLoC / cohort-based targeting。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Candidate | Inverted index | Brute force：1M scan |
| Auction | Second-price | First-price：advertiser 倾向 underbid |
| Pacing | Hourly budget | Free spend：early burnout |
| Tracking | Beacon async | Sync：page load 慢 |

## 容量估算

- 1M QPS × 100ms = 100k concurrent requests
- ML CTR prediction: 1k candidates × 1ms per scoring = 1s per request → 加 parallel + caching
- Storage: impression / click logs ~10 KB × 1M QPS × 86400 = 1 PB/day raw

## 易错点

> [!pitfall]
> ❌ Candidate gen 不 prune → 1M ad 都 rank；
> ❌ Budget 不 pace → 上午 burn out；
> ❌ 不 frequency cap → 用户反感；
> ❌ 同步 tracking → page load 慢；
> ❌ 不 detect click fraud → advertiser unhappy。

> [!key]
> 三大要点：(1) **Candidate gen + ML ranking + auction**；(2) **Budget pacing + frequency capping** balance UX 和 advertiser；(3) **Async impression/click tracking + fraud detection**。

> [!followup]
> "如何 cold start ML CTR (new ad)？" → use ad category prior + exploration (Thompson sampling)；"Video ad？" → completion rate 不只是 click；"Programmatic vs direct deal？" → guaranteed inventory before auction。
