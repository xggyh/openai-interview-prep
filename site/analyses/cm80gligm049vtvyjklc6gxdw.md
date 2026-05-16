## 题目本质

设计 **Web Crawler**（如 Googlebot）：从 seed URLs 出发抓取整个 web 上 billions of pages。礼貌爬 + dedup + parsing + 持续更新。

## 需求

- 100B+ pages，每天爬 1B+ pages
- 礼貌（robots.txt + per-host rate limit）
- Detect dup content / dup URL
- Re-crawl 频率按 page change rate 自适应

## 整体架构

```ascii
   Seed URLs (启动 + ongoing discovery)
         │
         ▼
   ┌──────────────────┐
   │  URL Frontier    │  priority queue per host，去重 URL
   │  (BIT-style      │
   │  scheduling)     │
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │  Fetcher Worker  │  HTTP GET, follow redirects
   │  Pool (1000 box) │  retry + timeout + politeness
   └──────┬───────────┘
          │ raw HTML
          ▼
   ┌──────────────────┐
   │  Parser          │  extract text + links + metadata
   └──┬───────────┬───┘
      │           │
      ▼           ▼
   ┌─────┐  ┌──────────────┐
   │Dedup│  │ Link Extract │ → push to URL Frontier
   │(sim │  └──────────────┘
   │hash)│
   └─┬───┘
     │ new content
     ▼
   ┌──────────────┐
   │ Document     │  Bigtable / GFS
   │ Store        │
   └──────┬───────┘
          │
          ▼
   Indexer → Search index
```

## 核心组件

### 1. URL Frontier

不是简单 queue。要：
- **Per-host queue + scheduler**：保证同 host 不被同时打太多并发（politeness）
- **Priority**：重要 page (high PageRank) 优先
- **URL dedup**：已 scheduled / fetched URL 不重新 enqueue

实现：每 host 一个 sub-queue，scheduler 按 rate limit (每 host 2 req/s) 取 URL。

### 2. Politeness

- 每 host 启动前 fetch + cache `/robots.txt`（24h TTL）
- Crawl-Delay header 遵守
- 同 host 并发限制（默认 1）+ 每秒限制（默认 2 req/s）

### 3. URL dedup

Naïve set 1B URL × 100 bytes = 100GB —— 单机装不下。

**Bloom filter** + **distributed dedup service**：
- Bloom filter 第一层（每 worker local，false positive < 0.1%）
- Bloom miss → 查中心 dedup service（Redis / RocksDB）

URL normalization 必须先做：
- Lowercase host
- Sort query params
- Remove `#fragment`
- Resolve relative paths

### 4. Content dedup（simhash）

不同 URL 可能同 content（mirror / syndication）。计算 page content **simhash** （64-bit）。Hamming distance < 4 视为重复。

### 5. Re-crawl 调度

- Sitemap.xml 提示 lastmod
- Page change rate history (上次 crawl 之间 diff 大小)
- 重要 page (news) 每小时 re-crawl；rare page 每月

### 6. Distributed scaling

- 1000+ fetcher workers，各自有 sub-frontier
- 中心 Coordinator 分配 URL ranges based on URL hash → 同 host 路由到同 worker（politeness 协调容易）

### 7. JavaScript-heavy pages

Modern web 大量 SPA。Headless browser (Chromium puppeteer) 渲染后取 DOM。比 plain HTTP fetch 慢 50x → 只对"必要"page 走 JS render（先 fetch HTML，发现是空壳再 JS render）。

### 8. Errors / Trap detection

- 4xx / 5xx 退避重试
- Infinite redirect loop detect
- Crawler traps（calendar like `/2026/1/1/...`）：限制 depth + URL pattern detection

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Frontier | Per-host scheduler | Single queue：违反 politeness |
| Dedup | Bloom + center service | Set in memory：OOM |
| Content dedup | Simhash | exact hash：mirror 算不同 |
| JS render | Selective puppeteer | All puppeteer：成本 50x |
| Re-crawl | History-based + sitemap | Fixed interval：浪费 |

## 容量估算

- 1B pages/day × avg 100 KB = 100 TB / day raw
- Fetcher: 1000 boxes × 100 req/sec = 100k req/s → 1 day = 8.6B requests（10% success bandwidth)
- Storage: compressed 5x → 20 TB/day → 7 PB/year

## 易错点

> [!pitfall]
> ❌ 不读 robots.txt → 被网站 block；
> ❌ 同 host 并发太多 → DDOS 别人 → 被封 IP；
> ❌ URL 不 normalize → dedup 不准（trailing slash, ?utm 等）；
> ❌ Content dedup 用 exact hash → mirror 算不同；
> ❌ 不限制 depth → crawler trap 死循环。

> [!key]
> Web crawler 工程难点：(1) **politeness vs throughput**；(2) **URL + content dedup at scale**；(3) **adaptive re-crawl**。算法不难，scale 和 robustness 是关键。

> [!followup]
> "Real-time newsworthy content (news as it breaks)？" → push-based subscription (PubSubHubbub / WebSub)；"How to crawl behind login？" → 通常不爬（respect privacy）；"如何 detect spam / SEO manipulation？" → ML model on link patterns + content signals；"Multilingual？" → per-language parser + tokenizer。
