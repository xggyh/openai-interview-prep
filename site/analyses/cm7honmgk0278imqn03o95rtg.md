## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Hashtag** | 推文里 `#word` 这种标签，把同主题内容串起来 | 商品上的"分类标签" |
| **Stream processing** | 数据像水流一样连续来，**边来边处理**（vs batch 一次性处理完） | 流水线 vs 大锅烩 |
| **Flink / Spark Streaming** | 业界主流的实时流处理框架 | 流水线的传送带 + 工人 |
| **Tumbling window** | 时间窗口"一格接一格不重叠"。如 1 分钟一格 | 钟表的分针 |
| **Sliding window** | 时间窗口**重叠**滑动。如 5 分钟窗口每 1 分钟滑一次 | 一辆缓缓前进的车上 5 分钟视野 |
| **Top-K** | 找前 K 个最大/最热的 | 排行榜 Top 10 |
| **Count-Min Sketch (CMS)** | 一种**省内存的近似计数器**。能估"X 出现过多少次"，有可控误差 | 漏勺 —— 大颗粒精准、小颗粒可能漏几个 |
| **Cardinality** | 不同值的数量。10 亿不同 hashtag 是高 cardinality | 一个抽屉里多少种不同纽扣 |
| **Heavy hitter** | 出现次数远高于平均的元素（"网红 hashtag"） | 一群人里最高的几个 |
| **Kafka topic / partition** | Kafka 把消息分到不同 partition 并行处理 | 邮局多个窗口同时收件 |
| **Redis SortedSet (ZSET)** | Redis 内置的"按分数排序的集合"，O(log N) 插入/查询 | 自动按分数排好的排行榜 |
| **CDN** | 全球内容分发网络，缓存静态资源就近返回 | 全球连锁店 |

---

## 1. 题目本质 — 这是什么问题

**Trending Hashtags System** = 实时从海量推文里**识别出当下最热门的话题标签**，每分钟更新一次。

**典型产品**：
- Twitter / X 首页右侧 "What's happening" 列表
- Weibo 热搜
- Instagram Explore 上的热门标签
- TikTok 趋势话题

**为什么有难度**：

1. **数据量巨大**：1B 用户、每秒 100k 推文，每推文平均 2 个 hashtag → 200k events/sec
2. **hashtag 种类极多**（high cardinality）：一天可能出现 1000 万种 hashtag（含拼写错误、生僻词）。**naive 给每个 hashtag 开一个 counter，内存爆**
3. **要"实时"**：< 1 分钟必须 detect 新爆款（明星出事了几分钟没上热搜，PR 大事故）
4. **要区分"刚刚爆"和"一直热"**：`#OpenAI` 也许每天都热，但 `#ChatGPT5发布` 是突然爆 —— 后者更应该上 trending
5. **多 region**：北京热搜 vs 纽约热搜不一样

Google 报告 10 次，考的是**实时流处理 + top-K + 近似算法**三套核心技能。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：要 global trending 还是 per-region trending？  
**典型答**：都要。Global + 按 country/city 切分。

**你问**：算"热门"的标准是**累计出现次数**，还是**最近一段时间的增长率**？  
**典型答**：以最近 5-15 分钟的"突然爆涨"为主，纯累计 count 会让"the / and" 类停用词永远 #1。

**你问**：用户多久看到 trending 更新一次？  
**典型答**：每 1 分钟更新前端就够（不需要秒级）。

**你问**：是不是要 personalized trending（每个用户看到不一样的）？  
**典型答**：v1 不需要，全 region 一样。v2 可以加 personalization。

**你问**：返回 top 多少 hashtag？  
**典型答**：top 50 per region 就够。

### 2.2 非功能性

**你问**：写入量？  
**典型答**：100k tweets/sec peak，平均 2 hashtag → 200k hashtag events/sec。

**你问**：查询量？  
**典型答**：1B 用户每天平均刷 5 次首页 → 5B 次/day = 60k QPS 读 trending。

**你问**：trending 数据延迟容忍多少？  
**典型答**：< 1 分钟（"实时"的工业标准）。

### 2.3 需求清单

```
功能：
- 实时识别热门 hashtag
- 按 region / global 切分
- 衡量"爆涨速度"而非纯 count（避免 stop-word 永远 top）
- 每分钟更新 top 50

非功能：
- 写入 200k events/sec
- 读 60k QPS
- 端到端延迟 < 1 分钟
- 支持 1B+ hashtag 种类（high cardinality）
```

> [!key]
> "实时 vs 准确" 是这道题的核心 trade-off。Twitter / Weibo 的实战经验：**绝对准确不重要，5 秒内大概率显示给用户**比"10 分钟后精确数字"价值高 10x。

---

## 3. 容量估算

### 3.1 写入 QPS

```
100k tweets/sec × 2 hashtags/tweet = 200k hashtag events/sec
```

每 event 大小 ≈ 100 bytes (hashtag string + ts + region + tweet_id)  
→ 200k × 100B = 20 MB/sec = 160 Mbps 写带宽。

### 3.2 高基数（cardinality）问题

**naive 估算**：每天可能出现 **1000 万种** hashtag (其中大部分只出现 1-10 次)。如果每种分配一个 64-bit counter：

```
10M × 8 bytes = 80 MB 计数器存储 (per minute window)
```

听起来 OK？但 **5 分钟 sliding window × 多 region × 历史保留** → 80 MB × 5 × 200 region × 90 天 = ~7 TB 内存。**会爆**。

→ 必须用 **Count-Min Sketch 近似** 替代精确 counter。

### 3.3 CMS 内存

```
CMS: width = 10000, depth = 5
size = width × depth × 4 bytes = 200 KB per window
```

→ 每窗口 200 KB（vs naive 80 MB）。**400x 节省内存**。

### 3.4 读 QPS

```
60k QPS GET /trending?region=X
```

每查返回 top 50 hashtag × 100B = 5 KB。

→ 总下行带宽：60k × 5KB = 300 MB/sec。**走 CDN cache** —— 大部分 hit edge，回源 < 1k QPS。

### 3.5 估算清单

```
写入：200k events/sec, 20 MB/sec
内存：~10 MB total CMS (across windows × regions)
读：60k QPS (大部分 CDN hit)
延迟：< 1 分钟 end-to-end
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：最朴素的方案

```ascii
Tweet → DB (insert with hashtag column)
      ↓
User views trending:
   SELECT hashtag, COUNT(*) FROM tweets
   WHERE created_at > NOW() - INTERVAL '5 min'
   GROUP BY hashtag ORDER BY COUNT DESC LIMIT 50;
```

**问题**：
- `GROUP BY` 1B+ hashtag 每分钟跑一次，DB 直接死
- 实时性差（query 跑 5 分钟，trending 已过时）
- 高 cardinality → 内存爆

### 4.2 第 1 步：用 Stream Processing

把 tweet 当作"流"实时处理，预聚合后存结果：

```ascii
Tweet → Kafka → Stream Processor → 预聚合 top-K → Redis → API → User
```

**为什么这条链**：
- **Kafka** 缓冲数据，避免 stream processor 慢时丢数据
- **Stream processor**（Flink）按窗口实时算 top-K
- 算完写 **Redis**，前端读 Redis 就好

### 4.3 第 2 步：Count-Min Sketch + Heavy Hitters

**问题**：1000 万种 hashtag 每个开 counter → 内存爆。

**解决**：用 **Count-Min Sketch** 近似计数 + 一个 **min-heap of size K** 维护 top-K。

```python
# 伪代码
class HeavyHitters:
    def __init__(self, K=50):
        self.cms = CountMinSketch(width=10000, depth=5)
        self.heap = []   # min-heap of (estimated_count, hashtag)，size ≤ K
        self.in_heap = set()
        self.K = K

    def add(self, hashtag):
        self.cms.add(hashtag)
        est = self.cms.estimate(hashtag)
        if hashtag in self.in_heap:
            # 已在 heap，更新它的 count
            self._update_heap(hashtag, est)
        elif len(self.heap) < self.K:
            heappush(self.heap, (est, hashtag))
            self.in_heap.add(hashtag)
        elif est > self.heap[0][0]:
            # 比 heap 最小的大，踢掉最小的
            old = heappushpop(self.heap, (est, hashtag))
            self.in_heap.discard(old[1])
            self.in_heap.add(hashtag)
```

**关键**：CMS 用 200 KB 替代 80 MB，heap 只保留 top-50，内存超省。

### 4.4 第 3 步：Sliding Window

每 1 分钟一个"sub-window"，5 个 sub-window 拼成完整 5 分钟视图：

```ascii
时间 →  [m-5][m-4][m-3][m-2][m-1][cur]
                            ↑
        合并这 5 个 sub-window 的 CMS + heap = 5 分钟 trending
        每 1 分钟最旧 sub-window 过期，开新的 sub-window
```

**为什么这样做**：
- 1 分钟 sub-window 让我们能 **逐分钟过期老数据**（而不是一次过期 5 分钟全部）
- 拼接 5 个 sub-window 数据 = 5 分钟视图
- 重叠 4 分钟 → 每分钟更新但平滑（不会因为窗口刚好切换而 trending 跳变）

### 4.5 第 4 步：Rate-of-change Score

纯 count 让"the/and/我"永远 top。我们要 detect "**突然爆涨**"。

```
trending_score = current_5min_count × log(1 + current / previous)
```

- `current_5min_count` 当前 5 分钟出现次数
- `previous` 前 5 分钟（即 [10min - 5min]）出现次数
- ratio 大 = 突然爆涨（如 #ChatGPT5 ratio 100x）

`log` 让超大 ratio 不会让 trending 完全被一个 hashtag 主导。

### 4.6 第 5 步：分 region

每个 region 独立跑 stream pipeline：

```ascii
                    ┌── Flink job (US) ──→ Redis ZSET (trending:US)
Tweet →  Kafka  ──→ ├── Flink job (EU) ──→ Redis ZSET (trending:EU)
                    ├── Flink job (CN) ──→ Redis ZSET (trending:CN)
                    └── Flink job (Global) → Redis ZSET (trending:global)
```

按 `tweet.geo_region` partition Kafka。每 region 独立计算 → 互不影响。

Global trending = 各 region top-K union 后重新 rank（或者单独跑 global Flink job）。

### 4.7 第 6 步：完整架构

```ascii
   Tweet write API
       │ extract hashtags + region
       ▼
  ┌──────────────────┐
  │ Kafka            │  topic: hashtag.events
  │ (partition by    │  per-region partition
  │   region)        │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────────────────┐
  │ Flink Stream Processor       │
  │ - keyBy region               │
  │ - sliding window (5min/1min) │
  │ - CMS + heavy hitters        │
  │ - rate-of-change score       │
  └──────┬───────────────────────┘
         │ 每分钟 emit top-K
         ▼
  ┌──────────────────┐
  │ Redis ZSET       │  key: trending:{region}, member=hashtag, score=trending_score
  │ (per region)     │  TTL 5 minutes
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ API + CDN cache  │  GET /trending?region=X → cached 30s
  └──────┬───────────┘
         │
         ▼
       Client
```

---

## 5. 每个组件深挖

### 5.1 Hashtag 提取 + 规范化

```python
import re

def extract_hashtags(text: str) -> list[str]:
    """从 tweet 文本提取 hashtag。"""
    # 找 #word 模式
    raw = re.findall(r"#(\w+)", text, re.UNICODE)
    # 规范化：lowercase + strip emoji
    return [h.lower() for h in raw if 2 <= len(h) <= 50]
```

**新手 question**：

❓ **为什么 lowercase？**  
`#ChatGPT` 和 `#chatgpt` 是同一个 hashtag。不规范化会拆成两个，flat 化都不上 trending。

❓ **为什么 length 2-50？**  
单字符（`#A`）噪声；长字符串（`#thisisaverylongspamtag1234`）多半是 spam，不应进 trending。

❓ **要不要去重 tweet 内多个相同 hashtag？**  
要（"`#crypto #crypto #crypto` 求高音量" 是 spam）。每 tweet 同 hashtag 只算 1 次。

### 5.2 Count-Min Sketch 深讲

**这是这道题最核心的技术**，要讲明白。

**Count-Min Sketch 是什么**：一个 **2D 数组** + **多个哈希函数**。

```
table = [[0]*width for _ in range(depth)]
# 例：depth=5, width=10000 → 5 行 10000 列
hashes = [h1, h2, ..., h_depth]   # depth 个独立哈希
```

**add(item)**：每个哈希函数算一个 column index，对应位置 +1。

```python
def add(item, count=1):
    for i in range(depth):
        col = hashes[i](item) % width
        table[i][col] += count
```

**estimate(item)**：每行查 column 值，取**最小**作为估计。

```python
def estimate(item):
    return min(table[i][hashes[i](item) % width] for i in range(depth))
```

**为什么 取 min？** 因为 hashing 冲突让 table[i][col] 可能因其他 item 加了多，**只会偏大不会偏小**。取最小消除冲突的累加。

**误差**：

```
Pr(estimate(x) > true_count(x) + ε × total) ≤ exp(-depth)
```

意思：`depth = 5` 时，估计偏差超过 `ε × 总事件数` 的概率小于 `e^(-5) ≈ 0.7%`。

**对 trending 任务的好处**：
- top-K 都是 high-count item，CMS 估计**对它们超准**
- low-count item（噪声）估计可能偏，但反正进不了 top-K，**误差不影响结论**

```ascii
hashtag "#chatgpt" 真值 50000
CMS estimate 可能 50100 (偏 +0.2%)
heap 排序里仍然在 top-K

hashtag "#xyz123random" 真值 3
CMS estimate 可能 850 (偏 850x！)
但 850 仍远低于 trending threshold，不影响 top-K
```

### 5.3 Min-heap 维护 top-K

新事件来：
1. CMS add + 估计新 count
2. 如果 item 已在 heap → update（用 lazy delete）
3. 否则比 heap 最小：大于 → 换；小于 → 不动

每次 add O(log K) heap 操作。K=50 → log K=6 操作，超快。

**lazy delete**：heap 不支持任意位置删除。已在 heap 的 item count 更新时，**直接 push 新的**（不删旧的），pop 时 check item 是否过期。简化代码。

### 5.4 Rate-of-Change Score

**问题**：纯 count 让 `#OpenAI` 永远第一（每天都热）。我们要 detect "**新爆款**"。

**Score 公式**：

```
score(tag) = current_count × log(1 + current_count / previous_count)
```

- `current_count`：当前 5 分钟出现次数
- `previous_count`：前 5 分钟（10 分钟前 到 5 分钟前）出现次数

**例**：

```
#OpenAI: 当前 5000, 之前 4800 → 5000 × log(1.04) = 5000 × 0.04 = 200
#ChatGPT5: 当前 8000, 之前 100 → 8000 × log(80) = 8000 × 4.4 = 35200
```

→ #ChatGPT5 score 高 170x，正确捕捉到"新爆款"。

**为什么用 log**：
- 没 log：ratio 100x 会让 score 增 100x → trending 完全被一个 hashtag 占满
- 有 log：ratio 100x 只让 score 增 4x → trending 仍有多样性

**新手 question**：

❓ **previous_count = 0 怎么办？**  
+1 平滑：`log(1 + current / (previous + 1))`。或直接 trending_score = `current`。

❓ **首次见的 hashtag？**  
进入"new" pool，单独 top-K。

### 5.5 Redis ZSET 存 top-K

每 region 一个 ZSET：

```redis
ZADD trending:US 35200 "#ChatGPT5"
ZADD trending:US 200 "#OpenAI"
...
EXPIRE trending:US 300   # 5 分钟自动过期防止 stale
```

读 top-50：

```redis
ZREVRANGEBYSCORE trending:US +inf -inf WITHSCORES LIMIT 0 50
```

O(log N + K) 取出 top-K。极快。

每分钟 Flink job 更新这个 ZSET。

### 5.6 Anti-spam

热门 hashtag 易被 bot 操纵。常见 spam 模式：

1. **Coordinated bot push**：1000 个 bot 同时发 `#promote_my_coin`
2. **Hashtag stuffing**：单 tweet 含 30+ 不相关 hashtag
3. **Cross-tweet copy**：同一文字同 hashtag 大量转发

**对策**：

```
Filter pipeline:
- 用户级 rate limit (同一 user 同 hashtag 1 分钟 < 5 次)
- ML model detect coordinated inauthentic behavior
- Bot score 降低 hashtag 权重 (bot 报 1 次 ≠ 真人 1 次)
- Cluster similar tweet text，dedup 计数
```

→ Bot 报 1 次 计 0.01 次，真人 1 次 计 1 次。Bot 的 manipulation 大幅削弱。

### 5.7 多 region 划分

```python
# Tweet event 进入时按地理打 region
def get_region(tweet):
    # 优先 user-set location > GPS > IP geo > language hint
    if tweet.user.set_location:
        return tweet.user.set_location.country
    if tweet.gps:
        return reverse_geocode(tweet.gps).country
    if tweet.client_ip:
        return geoip(tweet.client_ip).country
    return language_to_region(tweet.language)
```

Kafka partition key = region → 同 region tweet 路由到同 Flink subtask → 独立窗口。

### 5.8 API + CDN

```http
GET /trending?region=US&limit=50
→ 200 [{"hashtag":"#ChatGPT5","score":35200,"rank":1}, ...]
Cache-Control: max-age=30
```

用户不需要秒级实时，**30s CDN 缓存** 让 origin 服务器 QPS 从 60k 降到 < 1k。

CDN by (region, limit) 作 cache key。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 累计 count 还是 rate-of-change？
  - Region / global 都要？
  - 更新频率？返回 top 多少？
  - QPS / 延迟 / cardinality

0:05 - 0:10  Capacity Estimation
  - 200k events/sec write
  - 高 cardinality（10M 不同 hashtag/day）→ 必须近似算法
  - 60k QPS read → CDN cache 99%

0:10 - 0:15  High-Level Architecture
  - Tweet → Kafka → Flink → Redis → API → CDN
  - 解释 each box 干什么

0:15 - 0:30  Deep Dive
  ★ Count-Min Sketch 详细讲（这是 hot topic）
  ★ Sliding window 设计 (5min / 1min)
  ★ Rate-of-change score 公式 + 例子
  
0:30 - 0:38  Follow-ups
  - Anti-spam
  - Multi-region
  - Cold start (新 hashtag 永远没历史)
  - Personalization v2

0:38 - 0:45  Wrap-up
  - 三大决策：CMS / sliding / rate-score
  - Improvement ideas
```

**新手注意**：CMS 是这题最值得讲透的。如果你能讲清"为什么 200K 内存装下 10M unique items"，面试官会大加分。

---

## 7. 面试样板讲解

> "OK 我先确认几个事。这是 trending hashtag，对吧？我假设几件事 —— 算法用'5 分钟内 rate-of-change' 而不是纯 count，否则 the/and 这种词永远 top。Region 我做 per-region + global。更新频率前端 1 分钟，端到端延迟 < 1 分钟。
> 
> 估算：peak 100k tweets/sec × 2 hashtag = 200k events/sec write。读端 1B 用户 × 5 次/day = 60k QPS，但走 CDN 99% hit，origin < 1k QPS。
> 
> 难点是 cardinality —— 一天 1000 万不同 hashtag。如果给每个开 counter，5 min × 5 sliding × 200 region = 内存几 TB。
> 
> 关键 idea: **Count-Min Sketch + heavy hitter heap**。CMS 用 5×10000 数组 + 5 个哈希，每 hashtag add 时 5 个位置 +1，估计时取 min。空间 200 KB 装下任意 cardinality。Top-K 用 size-K min-heap 维护。1000 万 hashtag 实际有用的只有 top-50，剩下都丢。
> 
> Sliding window：每分钟一个 sub-window，5 个 sub-window 拼成完整 5 分钟视图。每分钟最老 sub-window expire。
> 
> Score 用 `current × log(1 + current/previous)` 让 rate-of-change 主导，避免 stop word。
> 
> 数据流：Tweet → Kafka (partition by region) → Flink per-region keyBy + sliding window + CMS → 每分钟 emit top-50 to Redis ZSET → API GET → CDN 30s cache → client。
> 
> 接下来想 deep dive CMS 算法细节，还是 anti-spam？"

---

## 8. Follow-up 演练

### Q1: 怎么处理 "新爆款 hashtag 没有 previous count"？

**答**：previous = 0 时用平滑 `log(1 + current / (previous + 1))`。或者把 "previous == 0 且 current > threshold" 的 hashtag 单独放 "Emerging" 列表（很多产品就是这么做的）。

### Q2: CMS estimate 真的不漏 top-K 吗？

**答**：理论上 top-K 是 **heavy hitters**，CMS 对它们估计偏差 < `ε × total`，远小于真值。即使估计稍偏，相对排序基本不变。**实战 recall@50 通常 > 99%**。如果完全要 exact top-K，可以 Flink 算精确 (每 region 数据量可能小到能 exact)。

### Q3: Anti-spam 怎么做？

**答**：
- 用户级 rate limit（同 hashtag 同 user 1 分钟 ≤ 5）
- ML model on coordinated patterns (1000 个 bot 同 5 秒发同 hashtag 是 strong signal)
- Bot score 加权（已识别 bot 报 1 次只算 0.01 次）
- Hashtag stuffing detection（单 tweet ≥ 5 hashtag 减权）
- Cluster similar text（copy-paste 算 1 次）

### Q4: 如果一个 hashtag 在 region A 大热 + region B 没人提，global 怎么算？

**答**：global = 各 region top-K union 后重 rank。region A 的 hashtag 进 global pool。但 global score 可以 normalize per-region cardinality（防止 region A 用户多就 dominate global）。

### Q5: Personalized trending（每个用户看不一样）怎么做？

**答**：基于 user interest embedding 重 rank。流程：
1. 标准 trending 算出 region top-200 (而非 top-50)
2. 对每个 user：(user_embedding · hashtag_embedding) 加权重 rank
3. Top-50 输出 personalized

成本：增加 200 QPS rerank, ML model 上线 + cache per-user 1 小时。

### Q6: 历史 trending（"昨天热门是什么"）怎么查？

**答**：每分钟 trending snapshot 写到 cold storage (BigQuery / S3 Parquet)。Query 时按时间查。冷数据不影响实时 hot path。

### Q7: 怎么 detect 操纵 trending 的事件（aka "trends manipulation"）？

**答**：异常检测 model 监控 hashtag 的 user diversity，IP diversity，account age 分布。如果一个 hashtag 95% 来自新注册 < 7 天的账号，强烈 manipulation signal → 不上 trending 或 alert 人工 review。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **用精确 counter** —— 内存爆，10M cardinality 不可能；  
> ❌ **纯 count 排 trending** —— stop word（the/and）永远第一，没有信号；  
> ❌ **Tumbling window (不重叠)** —— window 切换瞬间 trending 跳变，UX 差；用 sliding；  
> ❌ **不分 region** —— 美国用户看到日本热搜，相关性差；  
> ❌ **每查询实时聚合 60k QPS** —— DB 死；预聚合到 Redis；  
> ❌ **不做 anti-spam** —— 黑灰产 1 小时操纵 trending；  
> ❌ **CDN 不缓存** —— origin 60k QPS 抗不住；  
> ❌ **新 hashtag 没 previous count 时 score = 0** —— 错过最关键的爆款。

---

## 10. 加分项（What else）

- **Auto-suggested tags**：trending hashtag 推到 compose 框，鼓励用户用
- **Topic clustering**：相关 hashtag 聚类（`#OpenAI #GPT5 #ChatGPT5` 合成一个 trending topic）
- **Decline detection**：识别"曾经热但正在凉"的 hashtag，避免长尾占榜
- **Trending storytelling**：每个 trending 配一段自动生成的 context（"为什么这个热"）
- **Hashtag→Content recommendation**：点 trending 跳到相关内容流
- **Real-time A/B**：测试不同 ranking 算法对 retention 的影响
- **Trend forecasting**：基于早期增长曲线预测哪个 hashtag 会大爆 (early warning)

---

## 11. 总结：你应该记住的 3 件事

1. **高 cardinality + 实时 + Top-K = Count-Min Sketch + min-heap**。这套组合是工业界 trending / heavy hitter / DDoS detection 等问题的标准方案。会画 CMS table、能解释 false-positive 是工业级 SD 必修。

2. **Sliding window 比 tumbling window 用户体验好得多**。每分钟滑一格、维护 5 个 sub-window 的拼接是流处理 framework 的常见 idiom。

3. **Rate-of-change > absolute count**。设计 trending、anomaly、newsworthy 类系统时，"突变"信号比"高值"信号更有用。`score = current × log(current/previous)` 这种 log-ratio 公式记住。

> [!followup]
> **学习推荐**：(a) 自己用 Python 实现 Count-Min Sketch 50 行；(b) 跑一遍 Flink Quickstart 体验 stream window；(c) 读 "Mining of Massive Datasets" 第 4 章 (heavy hitters)；(d) 看 Twitter 公开的 trending architecture (Heron / Storm 时代的 paper)；(e) 思考：weibo 热搜被人为操纵时是怎么发现的？
