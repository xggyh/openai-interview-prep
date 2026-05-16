## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Log** | 程序运行时输出的事件记录（一行一行 text） | 餐厅订单流水 |
| **Structured log** | JSON / key-value 格式的 log（vs plain text） | 表格 vs 散文 |
| **Log Agent** | 装在每台 server 上的小程序，收集 log 推到中心 | 餐厅里的收单员 |
| **Fluent Bit / Fluentd / Vector** | 工业级 log agent | 商用版收单 |
| **Kafka** | 高吞吐消息队列，常作 log pipeline 中转 | 高速传送带 |
| **Elasticsearch (ES)** | 全文搜索 + 时序数据的 NoSQL DB，业界 log 主存 | 图书馆全文索引 |
| **Parquet** | 列式压缩文件格式，适合大数据 | 高效压缩档案 |
| **S3** | 对象存储，便宜但查询慢 | 仓库 |
| **Hot / Warm / Cold tier** | 数据分层 —— 热的快但贵，冷的便宜但慢 | 桌面 / 抽屉 / 仓库 |
| **Live tail** | 实时 streaming log（如 `tail -f` 但跨集群） | 直播 |
| **PII** | Personally Identifiable Info，敏感个人数据 | 身份证号 |
| **Sampling** | 不存全部数据，按比例存（如只存 1% INFO log） | 抽样调查 |
| **Index** | 帮助快速查找的数据结构（vs scan 全表） | 书目录 |
| **Cardinality** | 不同值的数量。High cardinality = label 值太多 → 索引爆 | 调色板有多少种颜色 |

---

## 1. 题目本质 — 这是什么问题

**Logger System** = **公司内所有应用产生的 log 集中收集、存储、可搜索、可告警**的系统。

**典型产品**：
- Splunk（商业）
- DataDog Logs / Loggly / Sumo Logic（云 SaaS）
- ELK stack (Elasticsearch + Logstash + Kibana，开源）
- 阿里云 SLS / Grafana Loki

**为什么这道题考的多**：

1. **规模炸裂**：1M+ servers × 各种应用 = **PB 级日志/天**
2. **写入巨大**：1M events/sec peak（peak hour 翻倍）
3. **查询多样**：开发者要 grep "error"，PM 要看 conversion funnel，安全要 detect attack
4. **保留时间长**：30 天热搜索 + 1 年归档审计
5. **不允许丢日志**（troubleshoot 时漏一条可能找不到 bug）
6. **PII / 合规**：日志可能含用户数据，要 redact

考点：**ingest 解耦 + 多 tier 存储 + 索引设计 + 成本控制**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：日志哪几种？  
**典型答**：应用 log（每行结构化 JSON）、access log (nginx) 、infra log (kubelet)。

**你问**：怎么 ingest？  
**典型答**：每 host 一个 agent (Fluent Bit) 推 → Kafka → indexer → store。

**你问**：查询方式？  
**典型答**：(a) 按 service + level + time range；(b) 关键词 (full-text)；(c) 聚合统计 (count error by host)。

**你问**：要不要 alert？  
**典型答**：要。如 "1 min 内 error > 100" → PagerDuty。

**你问**：保留时间？  
**典型答**：30 day hot searchable；90 day warm；1 year cold archive。

### 2.2 非功能性

**你问**：ingest QPS？  
**典型答**：peak 1M events/sec。

**你问**：每条 log 多大？  
**典型答**：avg 500 bytes，max 10 KB (stack trace)。

**你问**：emit 到 queryable 多久延迟？  
**典型答**：< 10 sec。

**你问**：multi-tenant 还是单内部？  
**典型答**：先做内部多 team，未来扩 SaaS。

### 2.3 需求清单

```
功能：
- 多类型 log ingest
- 全文 + filter + 聚合 query
- Alert rules
- Hot 30d / Warm 90d / Cold 1y

非功能：
- 1M events/sec peak
- < 10s ingest-to-queryable
- 1 PB+/day raw
- < $200k/month total cost (假设)
```

> [!key]
> 关键观察：**写远大于读**（1M writes/sec vs 几千 reads/sec）。Log 系统是 write-heavy。优化写入 + 控存储成本是核心。

---

## 3. 容量估算

### 3.1 写入

```
1M events/sec × 500 byte = 500 MB/sec = 4 Gbps
× 86400 sec/day = 43 TB/day raw
```

→ **每天 43 TB 日志**。一年 16 PB。

### 3.2 ES 存储成本

ES 节点 SSD 16 TB 一个 ~$1k/month。如果存 30 天 raw：

```
43 TB × 30 = 1.3 PB → 80 ES nodes × $1k = $80k/month
```

→ 太贵。**必须 sample + tier**。

### 3.3 Sampling 之后

```
ERROR / FATAL 100% sample → 5% of total = 2 PB → 几千$
WARN 50% → 5% of total → 几千$
INFO 5% → 10% of total → 几千$
DEBUG 1% → 5% of total → 1k$
Total ~70-80% reduction → 1 PB hot/month → 30 ES nodes
```

### 3.4 Cold tier (S3 Parquet)

冷数据存 S3 Parquet (列存，压缩 5x)：

```
1 PB compressed → 200 TB on S3 = $5k/month storage
```

便宜 50x。代价：query 需要 Athena / Presto，分钟级响应。

### 3.5 估算清单

```
Ingest: 1M events/sec = 4 Gbps
Storage: 43 TB/day raw → sample to 10 TB/day to ES
Total cost: ~$50k/month (sampled hot + cold archive)
Naive (全 hot): $1M+/month
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：朴素方案

```ascii
   App → write directly to ES
```

**问题**：
- ES 写入有 burst 时 throttle → app sync write 慢
- ES 挂了 → app log 写丢
- 1M apps 都连 ES → connection overload

### 4.2 第 1 步：Agent + Kafka 解耦

```ascii
   App stdout/stderr / file write
        │
        ▼
   ┌──────────────┐
   │ Log Agent    │  收集 + batch + ship
   │ (Fluent Bit) │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Kafka        │  buffer，按 service 分 partition
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Indexer      │  写入 ES
   └──────────────┘
```

**为什么这条链**：
- **Agent local file tail** → app 不 sync block log write
- **Kafka buffer** → indexer 慢或 ES 慢时不丢 log
- **Partition by service** → 同 service log 顺序保留

### 4.3 第 2 步：Sampling + Parse

Indexer 在写 ES 前做：

```python
def process(event):
    # 1. Parse: JSON 直接，plain text 用 grok regex
    parsed = parse(event)
    
    # 2. Enrich: 加 server geo, user_id resolve from session
    parsed['geo'] = geoip(parsed.get('ip'))
    
    # 3. Sample by level
    if parsed['level'] == 'ERROR':
        keep = True
    elif parsed['level'] == 'INFO':
        keep = random.random() < 0.05  # 5% sample
    else:
        keep = random.random() < 0.01  # 1% DEBUG
    
    # 4. PII redact
    parsed = pii_redact(parsed)
    
    if keep:
        es_write(parsed)
    
    # 5. ALL events 都进 cold S3 (满足 audit 需求)
    s3_archive(event)
```

**Sampling 是 cost 控制关键**。即使 INFO sample 5%，DEBUG sample 1%，依然能 debug —— 用 trace_id 关联其他相关 events。

### 4.4 第 3 步：Tier 化存储

```ascii
   Hot (ES, last 30d):
     - 索引齐全，秒级 query
     - 适合 debugging、recent alert
     
   Warm (S3 Parquet, 30-90d):
     - 列存压缩 5x
     - 通过 Athena query，分钟级
     - 适合趋势分析
     
   Cold (S3 Glacier, 90d-1y):
     - 极便宜
     - Retrieve 几小时
     - 合规审计用
```

每天定时 job：30 天前数据从 ES export → S3 Parquet + delete ES index。

### 4.5 第 4 步：Alert + 实时分析

```ascii
   Kafka topic logs.raw
          │
          ▼
   ┌──────────────┐
   │ Stream       │  Flink job
   │ Processor    │  实时跑 alert rules + aggregation
   └──┬───────────┘
      │
   ┌──┼─────────┬──────────┐
   ▼  ▼         ▼          ▼
  ES  Alert    Real-time  Anomaly
      Engine   Dashboard  Detection (ML)
```

Alert rule 例：

```yaml
- name: high_error_rate
  query: level:ERROR
  group_by: service
  threshold: count > 100 per 5min
  action: pagerduty + slack
```

实时 Flink job 维护 sliding window count，超阈值触发。

### 4.6 第 5 步：完整架构

```ascii
   Apps (1M instances)
       │ write log (stdout, file)
       ▼
   ┌──────────────┐
   │ Log Agent    │  (per host, Fluent Bit)
   └──────┬───────┘
          │ batched, compressed
          ▼
   ┌──────────────┐
   │ Kafka        │  per-service partition, retention 7d
   └──┬───────┬───┘
      │       │
      ▼       ▼
  ┌────────┐ ┌──────────────────┐
  │ Indexer│ │ Stream Processor │ Flink: alerts + agg
  │ Pool   │ │                  │
  └────┬───┘ └──────────────────┘
       │
       ▼
   ┌──────────────┐
   │ ES Cluster   │  ← hot tier 30d
   │ (30 nodes)   │
   └──────┬───────┘
          │ daily export
          ▼
   ┌──────────────┐
   │ S3 Parquet   │  ← warm 90d / cold 1y
   └──────────────┘

   Query UI (Kibana / custom):
       - <30 day: ES
       - >30 day: Athena → S3 Parquet
```

---

## 5. 每个组件深挖

### 5.1 Log Agent 详细

```yaml
# fluent-bit.conf
[INPUT]
    Name tail
    Path /var/log/app/*.log
    Tag app.*
    Multiline.parser python  # 多行 stack trace 合一条

[FILTER]
    Name parser
    Match app.*
    Parser json
    Reserve_Data On

[FILTER]
    Name modify
    Match app.*
    Add hostname ${HOSTNAME}
    Add region ${AWS_REGION}

[OUTPUT]
    Name kafka
    Match app.*
    Brokers kafka-cluster.internal:9092
    Topics logs.raw
    Format json
    Compression gzip
```

**关键 features**：
- **Tail file** 不 block app（async）
- **Multiline parser** 把 Python stack trace 合一条
- **Batch + compress** → 网络成本降 5x
- **Buffer to disk** 当 Kafka 不可用时

### 5.2 Schema (ES mapping)

```json
{
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "service":    {"type": "keyword"},        // 不分词
      "host":       {"type": "keyword"},
      "level":      {"type": "keyword"},
      "trace_id":   {"type": "keyword"},
      "user_id":    {"type": "keyword"},
      "message":    {"type": "text"},           // 全文搜索
      "fields":     {"type": "object"},
      "duration_ms":{"type": "long"},
      "geo":        {"type": "object"}
    }
  }
}
```

**新手 question**：

❓ **`keyword` vs `text` 什么区别？**  
`keyword` 不分词，整字段做 exact match (filter by service=foo)。`text` 分词，做 full-text search ("connection refused")。**service / host / level 必须 keyword**，message 必须 text。

❓ **Time-based index（daily）vs 单一大 index？**  
按 day 建 index：`logs-2026-05-16`。优点：(1) delete 老数据只 drop index，比 delete by query 快 1000x；(2) query 跨日期可 parallel；(3) 单 index 大小可控。

### 5.3 ES 配置

```
Cluster: 30 nodes
  - 10 master-eligible
  - 20 data nodes (SSD 16 TB each)
  
Shard strategy:
  - 1 day = 1 index
  - 1 index = 10 primary shards × 1 replica
  - 总 shard 数 30d × 10 = 300 → manageable

Refresh interval: 5 sec
  (vs default 1 sec; tradeoff: 5s search lag for 5x indexing throughput)
```

**Refresh interval** 是 log 系统的关键 tuning：1s 实时但写慢；5-30s 写快但 query lag。

### 5.4 Cold Tier (S3 Parquet)

```python
# Daily export job
def archive_day(date):
    index = f"logs-{date}"
    # Stream from ES, write Parquet to S3
    for batch in es.scroll(index):
        write_parquet(batch, f"s3://logs-archive/{date}.parquet")
    # Delete ES index
    es.indices.delete(index)
```

**为什么 Parquet**：
- 列存：query "all errors in service=X" 只读相关列，不扫全行
- Compression：5-10x vs raw JSON
- Athena / Presto 原生支持

Query cold tier：

```sql
SELECT service, COUNT(*)
FROM "logs"."archive"
WHERE date = '2026-05-01' AND level = 'ERROR'
GROUP BY service;
```

Athena 跑分钟级，但成本 $5/TB scanned。

### 5.5 PII Redaction

```python
PII_PATTERNS = {
    'email':       r'\b[\w.-]+@[\w.-]+\.\w+\b',
    'phone':       r'\b\d{3}-\d{3}-\d{4}\b',
    'ssn':         r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b',
    'ip':          r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
}

def redact(event):
    msg = event['message']
    for name, pattern in PII_PATTERNS.items():
        msg = re.sub(pattern, f'<{name}_redacted>', msg)
    event['message'] = msg
    return event
```

GDPR / HIPAA / PCI 都要求。Indexer 处理时统一过滤。

### 5.6 Alert Pipeline

```python
# Flink job
events.key_by('service')\
      .window(SlidingWindow(5min, 1min))\
      .process(lambda window: {
          'service': window.key,
          'error_count': window.count_where(level='ERROR'),
          'warn_count': window.count_where(level='WARN'),
      })\
      .filter(lambda agg: agg['error_count'] > 100)\
      .sink(PagerDutyAlert)
```

**Anti-flapping**：alert 必须持续 N 分钟才触发，避免一过性 spike。`for: 5m` 在 PromQL alert rule。

### 5.7 实时 vs 历史 query 路由

```python
def query(filter, time_range):
    now = current_time()
    start, end = time_range
    
    if end > now - 30_days:
        # 至少部分在 hot tier
        result_hot = es.search(filter, [max(start, now-30d), end])
    
    if start < now - 30_days:
        # 至少部分在 cold tier
        result_cold = athena.query(filter, [start, min(end, now-30d)])
    
    return merge(result_hot, result_cold)
```

UI 显示"超过 30 天的数据查询可能需要 1-5 分钟"提醒用户。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 日志类型 / 数量
  - Query 模式
  - 保留时间
  - PII？

0:05 - 0:10  Capacity Estimation
  - 1M events/sec, 43 TB/day raw
  - Sample / tier 大幅压缩
  - Cost target

0:10 - 0:15  High-Level Architecture
  - Agent → Kafka → Indexer → ES
  - Stream processor for alerts
  - S3 cold tier

0:15 - 0:30  Deep Dive
  ★ Agent (Fluent Bit), sampling
  ★ ES schema + sharding
  ★ Hot/cold tier
  ★ Alert pipeline

0:30 - 0:38  Follow-ups
  - PII
  - Multi-tenant
  - Cardinality 问题
  - Trace 关联

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK 这是 logger system。先估算：1M events/sec × 500 byte = 4 Gbps，每天 43 TB raw。30 天全 ES 存 1 PB 是 $1M/month —— **不可行**，必须 sample + tier。
> 
> 整体设计：每 host 装 Log Agent (Fluent Bit) → Kafka buffer → indexer → ES (hot 30 day) → S3 Parquet (cold)。
> 
> Agent 是关键 —— **不能同步阻塞 app log call**。Agent tail 本地文件，async batch + compress 推 Kafka。Kafka buffer 让下游慢或挂时不丢 log。
> 
> Indexer 做三件：parse / sample / PII redact。Sampling：ERROR 100%，INFO 5%，DEBUG 1%。这样压缩 70-80% 存储成本，但 debug 时 ERROR 完整 + trace_id 能 join 其他 sampled events 找到关联 INFO。
> 
> ES：每天一个 index `logs-YYYY-MM-DD`，10 primary shard × 1 replica。Refresh interval 5 秒（trade search lag for indexing throughput）。Field type keyword (service/host/level) vs text (message)。
> 
> Cold tier：每天 export 30 天前数据到 S3 Parquet。Athena query。比 ES 便宜 50x。
> 
> Alert：Flink job 实时 sliding window，超阈值触发 PagerDuty。`for: 5m` 防 spike 误报。
> 
> 想 deep dive multi-tenant 隔离还是 cardinality 问题？"

---

## 8. Follow-up 演练

### Q1: 同一个 user 的请求跨多 service，怎么关联？

**答**：Trace ID。请求进入 system 时分配一个 (OpenTelemetry context propagation)，每 service 处理时把 trace_id 加到自己 log。Query 时按 trace_id filter。

### Q2: Cardinality 爆炸（如有人加 user_id 当 ES field）？

**答**：
- 限制 high-cardinality field 必须用 `_source` keep 而非 index
- 强制 schema review for new fields
- 监控 ES heap usage：fielddata cache + doc values 占用过高 alert

### Q3: 怎么 ensure no log loss?

**答**：
- Agent 本地 disk buffer（Kafka 不可用时缓冲）
- Kafka replication factor = 3
- Indexer ack only after ES bulk insert success
- 周期 sample 对账（agent emit count vs ES indexed count）

### Q4: 多 tenant 隔离？

**答**：
- ES index 按 tenant 分（`logs-{tenant}-{date}`）
- RBAC 限 user 只查自家 index
- Resource quota per tenant (CPU / disk / QPS)

### Q5: 如何防止某 tenant 噪声 log 影响其他？

**答**：Kafka 也按 tenant 分 partition。Indexer 用单独 worker pool per tenant（或 weighted scheduling）。

### Q6: 全文搜索性能 vs filter 性能？

**答**：filter (keyword) O(log N) inverted index，超快。Full-text (text) 需要分词 + scoring，慢 10x。所以 design schema 时把"过滤"字段（service/host/level）设 keyword，content 设 text。

### Q7: GDPR 删除 user 数据？

**答**：用 trace_id 找 user 所有 log → ES `_delete_by_query` (慢) 或下次 reindex 时 strip。S3 Parquet 用 partition rewrite。**最佳实践**：log 不直接存 user_id，存 hash 或 reference id。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **App 同步写 ES** —— app 卡 + ES 慢；用 agent + Kafka；  
> ❌ **不 sample** —— $1M+/month；INFO/DEBUG 必须 sample；  
> ❌ **ES 全做 hot tier** —— 30 天 1 PB，成本爆；30+ 天必须 cold；  
> ❌ **High-cardinality field 当 keyword index** —— ES heap 爆 (user_id, request_id)；  
> ❌ **不做 PII redact** —— GDPR/HIPAA 巨额罚款；  
> ❌ **Refresh interval 1s** —— write throughput 限制 5x；调到 5-30s；  
> ❌ **Per-event ES insert** —— write 不批量，10x 慢；用 bulk API；  
> ❌ **Alert 无 anti-flapping** —— 1 个 spike 触发 100 条 page。

---

## 10. 加分项

- **Distributed tracing 集成**：log + trace + metric (Three Pillars of Observability)
- **AI log analysis**：异常 pattern detection (Drain algorithm，log clustering)
- **Auto schema discovery**：第一次见到的 field 自动加 mapping
- **GraphQL query**：let user 灵活组合 filter
- **Cost dashboard**：per-service cost breakdown 鼓励团队 optimize log volume
- **Log replay**：能 "回放" 历史 log 到 dev 环境 reproduce bug
- **Compliance archive**：WORM (Write-Once-Read-Many) storage for legal hold

---

## 11. 总结：你应该记住的 3 件事

1. **Write-heavy system 的核心 = ingest 解耦 + tier 化**。Agent + Kafka 让 app 不 block；hot/warm/cold tier 让成本可控。

2. **Sampling 不是 weakness，是 feature**。 Production log 99% 是 noise。聪明 sample + trace_id 关联，能保留 debug 能力同时省 80% 成本。

3. **High-cardinality 是 ES 杀手**。任何 unique-per-request 的字段（trace_id, request_id）不要 index 当 keyword。

> [!followup]
> **学习推荐**：(a) 跑通本机 ELK stack quickstart；(b) 读 Drain 算法 paper（log template extraction）；(c) 看 Datadog / Honeycomb 工程博客；(d) 思考"如果不用 ES，能用什么替代"（Loki + S3 + chunk index 也是新趋势）；(e) 学 OpenTelemetry 标准。
