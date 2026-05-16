## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Search query** | 用户在 Google 搜索框输入的文本 | "OpenAI 招聘" |
| **Query latency** | 一次 search 从发出到收到结果的耗时 | 点菜到上菜的时间 |
| **p99 latency** | 99% 请求快于这值（剩 1% 慢于）| 班级 99% 同学成绩 |
| **Heavy hitter** | 出现频繁的 item，需要专门跟踪 | 网红 hashtag |
| **Sampling** | 不存全部，随机抽样部分 | 民意调查 |
| **HDR Histogram** | 高动态范围直方图，省内存算 percentile | 体重分布图 |
| **T-digest** | 流式 percentile 算法 | 滚动算中位数 |
| **Query template** | 类似 query 的归一化形式（"OpenAI X" 都同 template） | 公式模板 |
| **Stream processor** | 实时处理流数据的服务（Flink / Spark Streaming）| 流水线工人 |
| **TSDB** | 时序数据库 | 体重记录本 |
| **Regression** | 性能突然变差 | 病情突然加重 |
| **A/B test** | 同时跑两版对比 | 实验组对照组 |

---

## 1. 题目本质 — 这是什么问题

**Distributed system for getting the slowest query from Google search** = 从 Google search 每天 **10B+ 次查询**里找出"哪些 query 让 search service 最慢"，作为性能优化目标。

**为什么需要这个系统**：

1. **Performance bug 难定位**：search 总体 p99 涨 50ms，但是哪种 query 慢？需要找到 outlier。
2. **Regression detection**：新版本上线后某种 query 突然变慢
3. **Optimization prioritization**：开发资源有限，先优化最慢的 N 个 query 类型，性价比最高
4. **SLO accountability**：定 SLO "all queries < 500ms"，超时哪些？

**与 trending hashtag (cm7honmgk0278imqn03o95rtg) 区别**：

| 维度 | Trending Hashtag | Slowest Query |
|---|---|---|
| 信号 | count (出现次数) | latency (耗时) |
| 算 top-K by | frequency | latency (max / p99) |
| 关心的 entity | hashtag 字符串 | query template |
| 用户 | end user (前端展示) | 内部工程师 (debug) |
| 实时性 | 1 min | 5-15 min OK |

考点：**streaming top-K by metric + sampling + query normalization + regression detection**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：metric 用什么？max latency？还是 p99？  
**典型答**：p99 更稳定。单次 outlier 不代表"种类慢"。但也存 max 作 hot signal。

**你问**：query 怎么算"同一类"？  
**典型答**：normalize template。"OpenAI 招聘" "OpenAI engineering" 都归 template "OpenAI [生词]"。

**你问**：要不要 dimension breakdown（按 region / 设备 / 时间）？  
**典型答**：要。"亚洲移动端慢" vs "欧洲 desktop 慢" 是不同根因。

**你问**：要不要 regression alert（新慢出现）？  
**典型答**：要。"新出现的 top-100 慢 query" 应立即 alert。

### 2.2 非功能性

**你问**：query 总量？  
**典型答**：10B/day = 116k QPS, peak 300k QPS。

**你问**：处理延迟？  
**典型答**：< 15 min ingest-to-dashboard。

**你问**：保留？  
**典型答**：30 day fine breakdown，1 year aggregate。

### 2.3 需求清单

```
功能：
- 实时聚合 query latency
- Top-K slowest query templates per region/version/device
- p99 跟踪 + max outlier 跟踪
- Regression alert (新慢 query)
- 历史 trend (回放优化效果)

非功能：
- 300k QPS ingest peak
- < 15 min lag
- Query template cardinality 数百万
```

> [!key]
> 关键 trick：**不要存所有 query**！10B/day × 100B 每条 = 1 PB/day，浪费。**Sample + template normalization** 是核心。

---

## 3. 容量估算

### 3.1 原始 query 数据量

```
10B query/day × 平均 100 byte query + 16 byte latency 
= 11.6 TB/day raw
```

→ 全存爆，必须聚合。

### 3.2 Sampling

10% sample → 1.16 TB/day 仍多。但**关键观察**：top-K slowest 是 heavy hitters，sample 不会丢精度。

```
10% sample × 关键 metric only (template + latency) 
= 1B records/day × ~50 byte 
= 50 GB/day
```

### 3.3 Template aggregation

```
~1M unique template/day (normalize 后)
每 template: histogram (HDR / t-digest) ~500 byte
总 internal state: 1M × 500 = 500 MB
```

→ **轻量！** 这就是聚合的力量。

### 3.4 估算清单

```
Raw: 11.6 TB/day → 不存
Sample: 50 GB/day raw archive
Aggregated state: 500 MB（内存够装）
Output: top-100 slowest / region/version = 几 KB / minute
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：朴素方案

```ascii
   Every search query → log to DB
   分析师每天跑 SQL:
   SELECT query, AVG(latency) FROM search_log
   WHERE day = '2026-05-15'
   GROUP BY query
   ORDER BY AVG(latency) DESC LIMIT 100;
```

**问题**：
- 10B records/day，scan 太慢
- `GROUP BY query` 每 query 不 normalize 都唯一 → group 1B+ groups 内存爆
- 不实时（dashboard 每天才更新）

### 4.2 第 1 步：Query Template Normalization

```
"OpenAI 招聘 software engineer"      → "OpenAI [token]"
"OpenAI engineering blog"             → "OpenAI [token]"
"Google software engineer salary"     → "Google [token]"
```

把含动态值的部分替换成 placeholder。**1B unique query → 1M unique template**，aggregation 可行。

```python
def normalize_template(query: str) -> str:
    tokens = tokenize(query)
    # 替换数字 / 罕见词 / 用户名为 placeholder
    template = []
    for tok in tokens:
        if is_number(tok):
            template.append('[NUM]')
        elif is_rare_word(tok):
            template.append('[RARE]')
        else:
            template.append(tok)
    return ' '.join(template)
```

### 4.3 第 2 步：Streaming Aggregation

```ascii
   search service emit: {query, normalized_template, latency, region, version, device, ts}
        │
        ▼
   ┌──────────────┐
   │ Kafka topic  │  search.latency
   │ (sampled 10%)│
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────────────────────┐
   │ Stream Processor (Flink)             │
   │ keyBy (template, region, device, version)│
   │ window 5min tumbling                 │
   │ aggregate per group:                 │
   │   - count                            │
   │   - sum latency                      │
   │   - HDR histogram (for p50/p95/p99)  │
   │   - max latency                      │
   └──────┬───────────────────────────────┘
          │
          ▼ emit every 5 min
   ┌──────────────────┐
   │ Top-K Aggregator │  cross-group: pick top 100 by p99
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ Slowest TSDB +   │
   │ Dashboard        │
   └──────────────────┘
```

### 4.4 第 3 步：HDR Histogram / T-digest

普通 array 算 p99 需要 sort。10k records/template → 30 ms。1M template → 30000s. **不行**。

**HDR Histogram**: 固定 bucket 数（~200 个，按 log scale），每个 bucket 计数。p99 = 累计 99% 的 bucket boundary。

```python
class HDRHistogram:
    def __init__(self, max_value=1_000_000_000, num_significant=3):
        # log-scale buckets, sub-buckets for precision
        self.buckets = [0] * BUCKET_COUNT
    
    def record(self, value):
        bucket = log_bucket(value)
        self.buckets[bucket] += 1
    
    def percentile(self, p):
        total = sum(self.buckets)
        cumulative = 0
        target = total * p / 100
        for i, c in enumerate(self.buckets):
            cumulative += c
            if cumulative >= target:
                return bucket_to_value(i)
```

每 template 内存 ~500 byte，update O(1)，query p99 O(BUCKET_COUNT)。**完美**。

### 4.5 第 4 步：完整架构

```ascii
   Search service (300k QPS)
        │ emit (query, template, latency, dims)
        ▼ 10% sample
   ┌──────────────┐
   │ Kafka        │  partition by template
   └──────┬───────┘
          │
          ▼
   ┌──────────────────┐
   │ Flink            │  keyBy (template, dims)
   │                  │  5min window
   │                  │  HDR Histogram per group
   └──┬───────────┬───┘
      │           │
      ▼           ▼
   ┌──────┐  ┌──────────────┐
   │ Top-K│  │ Anomaly /    │
   │ rank │  │ Regression   │
   │ per  │  │ Detector     │
   │ dim  │  └──────┬───────┘
   └──┬───┘         │
      │             ▼
      ▼        ┌──────────────┐
   ┌─────────┐ │ Alert        │
   │ TSDB +  │ │ (PagerDuty / │
   │ Dashbrd │ │  Slack)      │
   └─────────┘ └──────────────┘

   Cold:
   ┌──────────────┐
   │ S3 Parquet   │  raw sampled records，历史回放
   └──────────────┘
```

---

## 5. 每个组件深挖

### 5.1 Query Template Normalization

```python
import re

class TemplateNormalizer:
    PATTERNS = [
        (r'\b\d+\b',              '[NUM]'),
        (r'\b\d{4}-\d{2}-\d{2}\b', '[DATE]'),
        (r'\b\w+@\w+\.\w+\b',     '[EMAIL]'),
        (r'\bhttps?://\S+\b',     '[URL]'),
        (r'"[^"]*"',              '[QUOTED]'),
    ]
    
    def normalize(self, query: str) -> str:
        for pat, repl in self.PATTERNS:
            query = re.sub(pat, repl, query)
        tokens = query.lower().split()
        # 替换 rare token (在 ML model 字典外的)
        return ' '.join(t if t in COMMON_VOCAB else '[RARE]' for t in tokens)
```

**例**：

```
"buy iPhone 15 pro max 2024"  → "buy iphone [NUM] pro max [NUM]"
"buy iPhone 16 pro max 2025"  → "buy iphone [NUM] pro max [NUM]"
→ 归一化到同 template
```

### 5.2 HDR Histogram 实战

```python
from hdrh.histogram import HdrHistogram

class TemplateAggregator:
    def __init__(self):
        self.histogram = HdrHistogram(1, 60_000, 3)  # 1ms - 60s, 3 sig figs
        self.count = 0
        self.max_latency = 0
        self.max_query = ''  # 保留 max 那个 query 作为 example
    
    def record(self, query, latency_ms):
        self.histogram.record_value(latency_ms)
        self.count += 1
        if latency_ms > self.max_latency:
            self.max_latency = latency_ms
            self.max_query = query
    
    def emit(self):
        return {
            'p50': self.histogram.get_value_at_percentile(50),
            'p95': self.histogram.get_value_at_percentile(95),
            'p99': self.histogram.get_value_at_percentile(99),
            'p999': self.histogram.get_value_at_percentile(99.9),
            'count': self.count,
            'max': self.max_latency,
            'max_example': self.max_query,
        }
```

### 5.3 Top-K Aggregator

```python
import heapq

def top_k_slowest(template_stats, k=100, by='p99'):
    """Pick top-K templates by latency metric."""
    heap = []  # min-heap of (metric, template)
    for template, stats in template_stats.items():
        val = stats[by]
        if len(heap) < k:
            heapq.heappush(heap, (val, template))
        elif val > heap[0][0]:
            heapq.heapreplace(heap, (val, template))
    return sorted(heap, reverse=True)
```

### 5.4 Multi-dimension Aggregation

不只全 global，按维度 breakdown：

```
keyBy:
  - global (no dim)
  - (region) 单维度
  - (region, device) 二维度
  - (region, device, version) 三维度

每维度独立 top-K
```

存储分别一份。dashboard 让 user 选 dimension 看 breakdown。

### 5.5 Regression Detection

```python
def detect_regression(today_top_k, last_week_top_k):
    """Find templates that are NEW or much slower than last week."""
    last_week_map = {t['template']: t for t in last_week_top_k}
    regressions = []
    
    for today in today_top_k:
        tmpl = today['template']
        if tmpl not in last_week_map:
            regressions.append({'template': tmpl, 'reason': 'new_in_top_k'})
        else:
            old_p99 = last_week_map[tmpl]['p99']
            new_p99 = today['p99']
            if new_p99 > old_p99 * 1.5:
                regressions.append({
                    'template': tmpl,
                    'reason': 'regression',
                    'old_p99': old_p99,
                    'new_p99': new_p99,
                    'ratio': new_p99 / old_p99,
                })
    return regressions
```

发现 regression → alert + 记录到 incident tracking。**版本 deploy 后**特别关注 (auto compare new version vs previous)。

### 5.6 Sampling Strategy

10% uniform sample 简单但 miss rare query。**Stratified sampling**:

```
- Random 1% (representative)
- + 100% of any query with latency > 500ms (capture all slow events)
- + 100% of new version deploys' first 1 hour (regression detection)
```

混合保证 outlier 不丢。

### 5.7 Cold Storage (history)

```
Sample records → daily → S3 Parquet (compressed columnar)

Schema:
  - ts, query (string), template, latency, region, version, device, user_seg

Query via Athena: 
  "show me slowest restaurant queries last month"
  Athena scan with partition pruning (by day) → ~minute
```

历史 deep dive 用 cold storage。Real-time top-K 用 in-memory + TSDB。

### 5.8 Dashboard 设计

```
Dashboard:
  - Top 100 slowest templates (current 5 min)
  - Filterable by: region, version, device
  - Per template detail:
    - Trend over time (last 7 days)
    - p50/p95/p99/p999 + max example query
    - Compare to last week (regression highlight)
    - Sample queries (real examples)
  - Alert feed: 新出现的 top-100 + regression
```

工程师每天 standup 看 dashboard 决定 today's optimization priority。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - Slowest by max / mean / p99?
  - Query 归一化？
  - Real-time / batch?

0:05 - 0:10  Capacity Estimation
  - 10B/day, 300k QPS peak
  - Sample 10%
  - 1M unique templates

0:10 - 0:15  High-Level Architecture
  - Sample → Kafka → Flink → top-K aggregator → TSDB

0:15 - 0:30  Deep Dive
  ★ Template normalization
  ★ HDR Histogram p99
  ★ Multi-dim aggregation
  ★ Regression detection
  ★ Stratified sampling

0:30 - 0:38  Follow-ups
  - Cold storage / history
  - Trace 集成
  - Cost

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK，找 search 最慢的 query。先 clarify：用 p99 latency 而非 max 单 outlier；query 必须 normalize 成 template，不然 1B unique query 没法聚合。
> 
> 估算：10B/day = 116k QPS, peak 300k。Raw 11.6 TB/day 不能全存。**Sample 10% + template aggregate** 后 internal state 500 MB，超轻。
> 
> 整体：search service emit (query, latency, dims) → 10% sample 进 Kafka → Flink stream processor → per (template, dims) HDR Histogram 5 min window → 每窗口 emit p99 → top-K aggregator 选 top-100 slowest → TSDB + dashboard。
> 
> **HDR Histogram** 是 p99 计算关键：固定 200 buckets log-scale，每 update O(1)，query p99 O(200)。每 template 内存 500 byte，1M template 总 500 MB。
> 
> **Template normalization** 是另一个 trick：regex 替换数字 / 日期 / 邮箱 / rare word 为 placeholder。'iPhone 15' 和 'iPhone 16' 归到 'iphone [NUM]'。1B unique → 1M unique → aggregation 可行。
> 
> **Regression detection**: 每窗口与上周同窗口对比，新出现 top-100 或 p99 涨 50%+ → alert PagerDuty + 加入 priority bug list.
> 
> **Stratified sampling**: 不只 uniform 10%，加入 latency > 500ms 100% + 新 deploy 第一小时 100% → capture rare 但重要的事件。
> 
> Cold tier：sample records 每天 export S3 Parquet，Athena query 用于历史 deep dive。
> 
> 想 deep dive HDR Histogram 还是 regression detection？"

---

## 8. Follow-up 演练

### Q1: Max latency 用还是 p99？

**答**：**两个都存**。p99 更稳定，更适合识别"种类慢"；max + example query 帮助 debug 单点 worst case。Dashboard 两者都显示。

### Q2: Template normalization 太 aggressive 会怎样？

**答**：normalize 过头 → 不同 query 归同 template，丢失信息（"buy iPhone" 和 "buy car" 都成 "buy [RARE]"）。
**Trade-off**：normalize 程度。Conservative 用 named entity recognition (NER) + 保留 main verb / noun。

### Q3: Sample 不到 rare query (1 day 只 1 个但 5 秒)？

**答**：Stratified sample，latency > threshold 100% 保留。或 query frequency < N 都保留（rare query 不会让总量爆）。

### Q4: Regression false positive 怎么 reduce？

**答**：
- 至少 2 个连续 window 都 regression 才 alert
- 同时看 traffic 是否变化（traffic spike 时 latency 自然涨）
- ML model 学正常 variance pattern

### Q5: 怎么把 slowest query 关联到具体 service / endpoint？

**答**：emit metric 时除了 query + latency 还带 service trace breakdown：

```
{ query, latency, services: [{name, time_ms}, ...] }
```

聚合时多 dimension：per template × per service。"Templates that spend 80% time in service X" → 知道是 X 慢。

### Q6: Cost 怎么 control?

**答**：
- 10% sample （不是 100%）
- Flink HDR aggregation 内存常量 cost
- Cold storage S3 Parquet 比 TSDB 便宜 50x
- Dashboard query 限速 + cache 5 min

### Q7: 如何 measure 优化效果？

**答**：优化某 template 后：
- Track p99 over time
- Compare 同 dim 与 baseline
- A/B test：deploy 到 1% traffic 先看 metric 变化

---

## 9. 常见易错点

> [!pitfall]
> ❌ **不 normalize template** —— 1B unique query 无法 group；  
> ❌ **算 mean latency** —— outlier 拉高 mean 不能区分"种类慢"；用 p99；  
> ❌ **直接 sort 算 p99** —— 10k record × 1M template = TLE；用 HDR；  
> ❌ **Uniform sample** —— rare 但 important slow query 丢；用 stratified；  
> ❌ **不存 example query** —— 工程师看 top-K 没法 reproduce；存 max 那条；  
> ❌ **Regression alert 太宽** —— PagerDuty 烦；需 2 window 持续 + traffic adj；  
> ❌ **不分 dimension** —— "全球慢" 但实际只是 APAC mobile 慢，optimization 方向错。

---

## 10. 加分项

- **Distributed tracing 集成**：每 slow query 关联 trace → 看哪 service 占耗时
- **Cohort analysis**：power user vs casual user 慢的不同
- **Real user monitoring**：客户端测，end-to-end 包括网络
- **Auto-bug-filing**：top-100 + new regression 自动 file JIRA / Asana
- **What-if simulation**：估"如果我能优化 template X 50%，全 service p99 减多少"
- **ML root cause**：correlate slowness 与 deploy / config change → 自动找 culprit

---

## 11. 总结：你应该记住的 3 件事

1. **Template normalization 让 high cardinality 可聚合**。这是这类系统的灵魂 trick。

2. **HDR Histogram / T-digest 是 percentile 的工业算法**。O(1) update, O(K) query, 500 byte state per series。一定要会。

3. **Stratified sampling + multi-dim aggregation 让稀有重要事件不丢**。Uniform 10% sample 看起来够，实际 rare 慢 query 被漏。

> [!followup]
> **学习推荐**：(a) HDR Histogram 实现 / 用 hdrh Python 库；(b) 读 t-digest paper (Ted Dunning)；(c) 学 Flink stream window；(d) 看 Google "Dapper" / "Monarch" paper 关于内部 monitoring；(e) 思考"如果 trace_id 关联 cross-service，怎么算 cross-service slowest endpoint"。
