## 题目本质

设计 **Trending Hashtags System**（Twitter Trends / Instagram trending）：从 social media 实时流中识别"热门 hashtag"，按 region / global 展示 top-N，每分钟更新。

Google 报告 10 次。考点：**实时流处理 + sliding window count + top-K**。

## 需求拆解

- 1B posts/day, 10k posts/sec average, 100k peak
- 每分钟更新 trending list (top 50 per region)
- 多 region：global + 各国
- "热度" 不只是 count，要 detect "**rate of change**"（突然爆涨的）

## 整体架构

```ascii
   Post stream (Kafka)
         │
         ▼
  ┌──────────────────┐
  │ Hashtag Extractor│  parse #tags, region, ts
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Stream Aggregator│  Flink/Spark Streaming
  │ (per-region      │  - sliding window count
  │  windows)        │  - count-min sketch for top-K
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Trending Store   │  Redis ZSET per region
  │ (top-50 + scores)│  TTL 5 min
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ API + CDN cache  │  GET /trending?region=X
  └──────────────────┘
```

## 核心组件

### 1. Stream pipeline

```
post → extract hashtags → emit (hashtag, region, ts)
   ↓
keyBy (hashtag, region)
   ↓
sliding window (5 min, slide 1 min)
   ↓
count → top-K reducer
```

### 2. Counting algorithm

**Naïve**：每 hashtag-region 一个 counter。问题：1B unique hashtag → 内存爆。

**Count-Min Sketch**：固定大小的 probabilistic counter，O(1) per update，准确率高（top-K hashtag 是"high count"，误差小）。

```python
class CountMinSketch:
    def __init__(self, width=10000, depth=5):
        self.width, self.depth = width, depth
        self.table = [[0]*width for _ in range(depth)]
        self.hashes = [random_hash() for _ in range(depth)]
    def add(self, key, count=1):
        for i, h in enumerate(self.hashes):
            self.table[i][h(key) % self.width] += count
    def estimate(self, key):
        return min(self.table[i][h(key) % self.width]
                   for i, h in enumerate(self.hashes))
```

加上 **heavy hitters** 维护（min-heap of top-K with estimated counts）—— 每次 add 后 check 是否进 top-K。

### 3. Sliding window

5 分钟窗口、1 分钟 slide：
- 维护 5 个 1-minute "sub-window" counter
- 每分钟 expire 最早的 sub-window
- 查询 trending = sum 5 个 sub-window 的 top-K

Flink 原生支持 sliding window，不必自己实现。

### 4. Rate of change

不只看 absolute count。计算 **"current 5-min count vs prior 5-min count" 的 ratio**：

```
trending_score(tag) = current_count × log(1 + current_count / prior_count)
```

突然爆涨的 ratio 大，score 高。这比纯 count 更能 surface emerging trends。

### 5. Multi-region

每个 region 独立 stream pipeline：
- US, EU, APAC 各自 Flink job
- Global trending = re-aggregate all regions（轻量）

按地理坐标 / 时区 / language hint 把 post 分到 region。

### 6. Anti-spam

热门 hashtag 容易被 bot 刷。Filter：
- Per-user 每分钟同 hashtag 限制 10 次
- ML model 识别 coordinated inauthentic behavior
- Bot signal 加权降低 trending score

### 7. API + caching

```
GET /trending?region=US&top=50
→ 直接读 Redis ZSCORE per region
→ CDN cache 30 秒（用户不需要秒级实时）
```

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Counting | Count-Min Sketch + heavy hitters | exact counter：内存爆 |
| Window | 5min sliding, 1min slide | 1min tumbling：bursty 不平滑 |
| Score | count × rate-of-change | pure count：missing emerging |
| Storage | Redis ZSET | DB：read 慢 |
| Pipeline | Flink | Custom：reinvent wheel |

## 容量估算

- 100k posts/sec × 2 hashtags avg = 200k events/sec
- CMS table 100k × 5 depth × 4 bytes = 2 MB per region per minute → trivial
- Redis ZSET per region: top 1k × 50 bytes = 50 KB → 50 region × 50 KB = 2.5 MB
- API QPS: 100k peak → CDN 99%, origin 1k QPS

## 易错点

> [!pitfall]
> ❌ Exact counter per hashtag —— 内存爆；
> ❌ Pure count 不考虑 rate-of-change —— "the" "and" 永远 top；
> ❌ 不 anti-spam —— bot 操纵 trending；
> ❌ 每查询都重算 —— 应预聚合到 Redis；
> ❌ Window 太大 / 太小 —— 5 min 是 Twitter 实战调好的 sweet spot。

> [!key]
> 三大要点：(1) **Count-Min Sketch + heavy hitters** 处理高基数；(2) **Sliding window + rate-of-change score** surface emerging trends；(3) **Anti-spam ML model** 防止 manipulation。

> [!followup]
> "Personalized trending（每用户不同）？" → 加入 user interest embedding 重排 top-K；"Hashtag co-occurrence？" → 建 graph + cluster；"Real-time < 1 min？" → 降 slide window；"Historical trending data？" → 每分钟 snapshot 存 cold storage (S3 Parquet)。
