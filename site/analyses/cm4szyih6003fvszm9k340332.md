## 题目本质

设计 **Wikipedia Crawler**：专门爬 Wikipedia（vs general web crawler）。规模小、结构化更强。

与 [[cm80gligm049vtvyjklc6gxdw]] (general Web Crawler) 共享 framework，但有特殊点：

## Wikipedia 特殊性

1. **Single host**：所有 page 在 wikipedia.org → politeness 简化但 throughput 限制大
2. **Structured**：有标准 URL pattern `/wiki/Topic_Name`，有 sitemap，有 API
3. **Frequently updated**：每秒数千 edits → 需要持续 re-crawl
4. **多语言**：300+ 语言子域名
5. **已有 export**：dumps.wikimedia.org 提供完整 dump

## 推荐策略

### Option A：用 dumps（推荐）

Wikipedia 每 2 周发布完整 dump（~80 GB compressed XML for English）。下载 + 解析。

- 优点：单次下载 vs 几百万 HTTP request；正式 ToS 鼓励
- 缺点：lag 2 周

### Option B：爬 + dump 混合

Initial: 用最新 dump 加载所有 page。
持续：用 Wikipedia EventStream API 订阅 real-time edits → incremental update。

### Option C：纯爬（不推荐）

爬 ~6M page × 50 KB = 300 GB。HTTP rate limit (Wikipedia 容忍 ~200 req/s for bots)。需 17 小时不停爬，但**违反 ToS**（要求用 API or dump）。

## 整体架构（Option B 最推荐）

```ascii
   Initial Load
       │
       ▼
   ┌──────────────┐
   │ Dump Loader  │  parse XML.bz2 → extract page records
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Page Parser  │  Wikitext → plain text / structured fields
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Storage      │  Postgres + ES for search
   └──────┬───────┘

   Continuous Updates
        │
        ▼
   ┌──────────────┐
   │ EventStream  │  ← https://stream.wikimedia.org
   │ subscriber   │     SSE / WebSocket of edits
   └──────┬───────┘
          │ revision event
          ▼
   ┌──────────────┐
   │ API Fetcher  │  → fetch page via Action API
   └──────┬───────┘    /w/api.php?action=parse&page=...
          ▼
   Update Storage
```

## 核心组件

### 1. Wikipedia EventStreams

```
GET https://stream.wikimedia.org/v2/stream/recentchange
SSE: 每个 edit event JSON 推送
```

订阅后 real-time 收到所有 wiki 的 edits。Filter by wiki (enwiki / zhwiki / etc.)。

### 2. Wikitext parsing

Wikipedia 用 MediaWiki Wikitext，不是 plain HTML。需要 parser：
- 提取 plain text（剥 link / template / table syntax）
- 解析 infobox（structured 数据）
- 解析 categories
- 解析 references / citations

工具：[mwparserfromhell](https://github.com/earwig/mwparserfromhell)（Python）。

### 3. 页面 schema

```sql
CREATE TABLE pages (
  page_id      BIGINT PRIMARY KEY,
  title        TEXT,
  language     TEXT,
  revision_id  BIGINT,             -- 最新 revision
  content_raw  TEXT,                -- wikitext
  content_plain TEXT,               -- parsed plain text
  categories   TEXT[],
  infobox      JSONB,
  links        TEXT[],
  updated_at   TIMESTAMPTZ
);
```

### 4. Revision history

每 page 可能想保留 N 个历史 revision（diff 分析 / dispute resolution）。单独表 + foreign key。

### 5. Multilingual

按 (page_id, language) 复合 key 或 partition。Wikipedia 同 topic 不同语言不一定 ID 一致 (Wikidata Q-ID 连接)。

### 6. 搜索

ES 全文索引 plain text + title boost + category filter。Wikipedia 自己用 CirrusSearch (ES based)。

### 7. Rate limit

即使用 API：
- API 限 ~200 req/s for bots (User-Agent 必须含 contact info)
- 大量并发用 batch API（`titles=A|B|C`，一次 50 page）

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Initial | Dump | Crawl：浪费 |
| Update | EventStream + API | Polling sitemap：lag |
| Parser | mwparserfromhell | Custom：reinvent |
| Schema | Per-page record + history | Append-only：query 麻烦 |

## 易错点

> [!pitfall]
> ❌ 朴素 HTTP 爬 page → ToS 违反；
> ❌ 用 HTML parsing → wikitext source 才是正版；
> ❌ 不订阅 EventStream → 数据 lag；
> ❌ 不 separate language → 数据混；
> ❌ 不记 revision history → dispute 无法 trace。

> [!key]
> Wikipedia 不是普通 web。Use **dumps + API + EventStream** instead of raw HTML crawl。Respect ToS + provide User-Agent.

> [!followup]
> "解析 Citations 做 knowledge graph？" → mwparserfromhell 提取 + entity linking；"如何 detect vandalism / hoax？" → ML on edit patterns；"实时 search index update？" → ES index alias rotation；"如何 contribute back / verify 爬取数据正确？" → cross-check against Wikipedia search API。
