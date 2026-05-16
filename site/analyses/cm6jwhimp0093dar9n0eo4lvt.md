## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Metric** | 数字型时序数据（CPU 80%, mem 4GB）| 体温 / 血压 |
| **TSDB (Time-Series DB)** | 专门存时序数据的数据库 | 病历表（按时间排） |
| **Prometheus** | 业界最主流开源 TSDB，pull-based | 自动测体温的医院 |
| **VictoriaMetrics / Thanos** | Prometheus 的 scale 化版本 | 多家医院联网 |
| **Grafana** | 时序数据可视化工具，看 dashboard | 体检报告 |
| **Pull vs Push** | Server pull (Prometheus 主动来取) vs Agent push (Server 主动发) | 主动问诊 vs 主动汇报 |
| **OpenTelemetry (OTel)** | 业界 metric/log/trace 三合一标准 | 通用医疗记录格式 |
| **Cardinality** | 不同 series 的数量（label 组合越多 cardinality 越高）| 一个抽屉多少种纽扣 |
| **SLO / Error Budget** | Service Level Objective + 还能容忍多少 outage | "99.9% 在线 = 一年最多 8.7 小时挂" |
| **Anomaly detection** | 检测"指标突然异常"，比阈值更智能 | 体温微微反常的提醒 |
| **Downsampling** | 时序数据从精细粒度合并到粗粒度（1s → 1min → 1h） | 高清照片转缩略图 |
| **PagerDuty** | 业界 on-call alert 工具 | 自动喊医生 |
| **High Cardinality 警告** | label 含 user_id 这种 → series 爆炸 | 每个病人写一份独立病历 |

---

## 1. 题目本质 — 这是什么问题

**Server Health Monitoring** = 把成千上万服务器的 CPU / mem / disk / network / 服务状态**实时收集 + 存储 + alert + 可视化**。

**典型场景**：
- Google SRE 监控自家数据中心所有服务器
- AWS / GCP 给客户提供 EC2 / VM 监控
- 自建私有云的运维团队

**为什么这道题区别于 Logger System**：

| 维度 | Logger | Metric Monitoring |
|---|---|---|
| 数据形式 | 文本事件 | 数字时序 |
| 主要用途 | Debug / audit | Health / alert |
| Query | 全文 + filter | Aggregation (avg, sum, p99) |
| 保留 | 30 天热 + 1 年冷 | 1 day fine + 1 year downsampled |
| Cardinality 痛 | 中等 | 极痛 |
| 数据量 | 大（文本）| 中等（数字）|

考点：**TSDB 存储 + cardinality 控制 + alert engine + SLO**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：监控哪类指标？  
**典型答**：(a) System: CPU / mem / disk I/O / network；(b) Process: count, fd usage；(c) Custom app: request_count, error_rate, latency。

**你问**：采集频率？  
**典型答**：System 10 秒；custom app metric 可低至 1 秒（high freq alert 用）。

**你问**：要 alert 哪些？  
**典型答**：CPU > 90% 持续 5 min、disk full < 10%、error rate spike、custom rule。

**你问**：用户查询模式？  
**典型答**：Grafana dashboard 看实时 + 历史 trend；oncall 看具体 incident。

### 2.2 非功能性

**你问**：多少 server？  
**典型答**：50k servers。

**你问**：每 server 多少 metric？  
**典型答**：avg 50 个 (CPU/mem/disk/各 service status)。

**你问**：保留多久？  
**典型答**：10 sec resolution 1 day；1 min 7 day；5 min 1 month；1h 1 year。

**你问**：Alert 多久要响应？  
**典型答**：从指标超阈值到 PagerDuty 触发 < 60 sec。

### 2.3 需求清单

```
功能：
- System + process + custom metric 采集
- Dashboard (Grafana)
- Alert rule
- Anomaly detection (ML 加分)
- SLO + error budget

非功能：
- 50k servers × 50 metric × 0.1 Hz = 250k samples/sec
- 端到端 60 sec
- 1 month 5 min resolution + 1 year hourly
```

> [!key]
> 关键点：**high cardinality 是 monitoring 的"杀手"**。每加一个 label (如 user_id) series 数指数增加。Design 时必须严格控制 label。

---

## 3. 容量估算

### 3.1 写入

```
50k server × 50 metric = 2.5M unique series
× 1 sample / 10s = 250k samples/sec
```

每 sample ≈ 16 bytes (timestamp 8 + value 8) → 4 MB/sec。

### 3.2 存储

```
250k samples/sec × 86400 = 21.6B samples/day
× 16 bytes / 8 (TSDB 压缩比) = 43 GB/day raw → 5 GB compressed/day
```

下采样后：

```
10s raw 1 day = 5 GB
1min 7 day = 5 × 7 / 6 ≈ 6 GB
5min 1 month = 6 × 30 / 5 ≈ 36 GB
1h 1 year = 36 × 365 / 60 ≈ 220 GB

总 ~270 GB / cluster
```

→ 单 TSDB cluster (3 节点) 装得下。

### 3.3 查询

Grafana dashboard 每 dashboard 5-20 query，每 30s refresh。100 oncall × 1 dashboard = 几十 QPS。**不是瓶颈**。

### 3.4 估算清单

```
Write: 250k samples/sec
Storage: ~270 GB total (downsampled)
Query: 几十 QPS (低)
Cost: 3 TSDB nodes + Grafana → $5k/月 (vs 几十 k for Logger)
```

→ 比 logger 便宜得多。监控是相对 cheap 的 observability。

---

## 4. 整体架构 step by step

### 4.1 第 0 步：朴素方案

```ascii
   Each server: 写本地 file → 人 ssh 进去看
```

**问题**：50k server 怎么找问题？没法 alert，没有 trend。**没法 scale**。

### 4.2 第 1 步：中心收集

```ascii
   Server → Push metric → TSDB ← Grafana
```

但 push vs pull 怎么选？

**Pull (Prometheus 模式)**：
- Prometheus 主动 scrape 每 server `/metrics` 端点
- 每 15 秒 pull 一次
- ✅ 发现 dead server 容易 (scrape failed)
- ✅ TSDB 控制 rate
- ❌ Firewall / NAT 后的 server 难

**Push (StatsD / OpenTelemetry 模式)**：
- Agent 主动 push 到 collector
- ✅ 穿透 NAT
- ✅ 短生命周期（如 batch job）也能 emit
- ❌ Dead server 不知道是 dead 还是 silent
- ❌ 容易被 spam

**实战**：**Hybrid** —— 内网用 pull (Prometheus), edge / mobile / serverless 用 push (OpenTelemetry collector)。

### 4.3 第 2 步：多分辨率存储 (downsampling)

实时只需精细数据，老数据用粗粒度就够（看 1 年 trend 不需要每 10 秒一个点）。

```ascii
Recent 1 day:   10s resolution (raw)
1-7 day:        1min resolution
7-30 day:       5min resolution
30-365 day:     1h resolution
> 1 year:       1d resolution (cold archive)
```

Downsampling job 每分钟 / 每小时 / 每天跑，把数据 roll up。

**关键 trade-off**：精度 vs 成本。Engineering team 实战调，10s/1m/5m/1h 是 sweet spot。

### 4.4 第 3 步：Alert Engine

```ascii
   TSDB
     │ (rules engine query 周期)
     ▼
   ┌──────────────┐
   │ Rule         │  Eval every 30s:
   │ Evaluator    │    avg_over_time(cpu[5m]) > 0.9
   └──────┬───────┘
          │ if true and for > 5 min
          ▼
   ┌──────────────┐
   │ Alert        │  PagerDuty / Slack / email
   │ Manager      │
   └──────────────┘
```

**Anti-flapping**：`for: 5m` 必须持续 5 分钟才 fire，避免抖动。

### 4.5 第 4 步：完整架构

```ascii
                  Servers (50k)
   ┌──────────────────┴──────────────────┐
   │                                     │
   ▼ (pull /metrics)                     ▼ (push - 边缘 / 移动)
┌─────────────────┐               ┌──────────────────┐
│ Prometheus      │               │ OpenTelemetry    │
│ (per region)    │               │ Collector        │
└────────┬────────┘               └─────────┬────────┘
         │                                  │
         └──────────────┬───────────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ TSDB         │  VictoriaMetrics / Thanos
                 │ (federated)  │  分 hot (recent) / cold (archive)
                 └──┬───────┬───┘
                    │       │
                    ▼       ▼
            ┌─────────┐ ┌─────────────┐
            │ Grafana │ │ Alert       │
            │         │ │ Manager     │
            └─────────┘ └──────┬──────┘
                               │
                               ▼
                          PagerDuty / Slack
```

---

## 5. 每个组件深挖

### 5.1 Metric 格式 (Prometheus exposition)

```
# HELP http_request_count Total HTTP requests
# TYPE http_request_count counter
http_request_count{method="GET", endpoint="/api", status="200"} 1234567
http_request_count{method="POST", endpoint="/api", status="200"} 567890
http_request_count{method="GET", endpoint="/api", status="500"} 42
```

**Series = metric_name + label set**。同一个 metric 可以有多 series（每个 label 组合一个）。

**Cardinality 计算**：

```
http_request_count{method, endpoint, status}
 method: 5 (GET/POST/PUT/DELETE/PATCH)
 endpoint: 100
 status: 20

Series 数 = 5 × 100 × 20 = 10,000
```

如果不小心加上 `user_id` 这种 high-cardinality label：

```
user_id: 1B
Series 数 = 5 × 100 × 20 × 1B = 10^13 → TSDB 崩溃
```

→ **never put user_id / request_id 当 label！**

### 5.2 TSDB 选型

| 选项 | 优势 | 劣势 |
|---|---|---|
| **Prometheus** (单机) | 标准、简单 | scale 不到 100k+ series |
| **VictoriaMetrics** | 高写入 / 低存储 / Prom-compat | 较新 |
| **Thanos** | Prometheus + S3 长期存储 | 复杂 |
| **InfluxDB** | SQL-like，商业版强 | open source 写慢 |
| **TimescaleDB** | Postgres extension，SQL 友好 | scale 受 Postgres 限 |
| **Datadog / 商业 SaaS** | 不操心，包邮 | $$$$ |

**面试推荐**：先讲 Prometheus / VictoriaMetrics + Thanos for long-term。

### 5.3 Multi-resolution

```python
# Continuous Aggregation (downsampling job)
# 每分钟跑一次
INSERT INTO metrics_1min (series_id, ts_minute, avg, max, min)
SELECT 
  series_id,
  date_trunc('minute', ts) as ts_minute,
  avg(value), max(value), min(value)
FROM metrics_raw
WHERE ts >= NOW() - INTERVAL '2 min'
  AND ts < NOW() - INTERVAL '1 min'
GROUP BY series_id, ts_minute;

-- Old raw data > 1 day → DELETE
```

Query 时按时间范围选 resolution：

```python
def query(series, start, end):
    span = end - start
    if span < 1.day:
        return query_raw_10s(series, start, end)
    elif span < 7.day:
        return query_1min(series, start, end)
    elif span < 30.day:
        return query_5min(series, start, end)
    else:
        return query_1h(series, start, end)
```

### 5.4 Alert Rules

```yaml
groups:
- name: server_health
  rules:
  - alert: HighCPU
    expr: avg_over_time(cpu_usage_percent{job="prod"}[5m]) > 90
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU on {{ $labels.instance }}"
      description: "CPU has been > 90% for 5 minutes"
  
  - alert: DiskAlmostFull
    expr: disk_used_percent > 95
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "Disk almost full on {{ $labels.instance }}"
```

**关键字段**：
- `expr`：PromQL query，结果非空就 considered firing
- `for`：必须持续多久才真 fire（anti-flapping）
- `labels.severity`：决定 routing (warning vs page)
- `annotations`：人类可读消息，用模板变量

### 5.5 Anomaly Detection (ML 加分)

Static threshold (CPU > 90%) 不够：周末 vs 工作日 baseline 不同，"CPU 30% 但平时是 5%" 也是异常。

**Method 1: Statistical baseline**

```python
# 每 metric × hour-of-day × day-of-week 算 baseline (mean, stddev)
# 持续 4 周 training
baseline[metric][hour][day] = (mean, std)

# 实时检测
current = ...
if abs(current - baseline.mean) > 3 * baseline.std:
    alert("anomaly")
```

**Method 2: ML model** (Prophet / ARIMA / LSTM)

预测 next value + interval，超出 interval = anomaly。

**Method 3: Change point detection**

检测"指标 distribution 突然变化"（如 latency 从 100ms 跳到 200ms 突然）。

### 5.6 SLO + Error Budget

**SLO = Service Level Objective**：定义"我的服务在多大程度上算可用"。

```
SLO: 99.9% successful HTTP requests in 30-day rolling window
Error budget = 0.1% = 43.8 minutes/month
```

Burn rate alert：

```
快 burn：1h 内 burned 5% error budget → 立即 page
慢 burn：6h 内 burned 10% → warn
```

避免：单纯 "error rate > 0.1%" alert 触发太频繁（自然抖动）。Burn rate 让 alert 与 budget 长期可持续对齐。

### 5.7 Multi-region 部署

```
   每 region (us-east, eu, apac):
     Local Prometheus + VictoriaMetrics
   
   Global:
     Thanos / federation
     Global Grafana
```

Pull 模式天然适合 local —— 每 region Prometheus 只 scrape 本 region server，跨洋 latency 不存在。Long-term storage via S3 (Thanos)。

### 5.8 Cardinality 控制

```python
# Bad
http_requests{user_id="abc123", request_id="xyz"} 1
→ user_id, request_id 是 unbounded → series 爆

# Good
http_requests{endpoint="/api", method="GET", status="200"} 1234567
→ 这些 label 都有 fixed cardinality
```

**Pre-flight check**：CI 中加 linter 扫描代码，检测可疑 high-card label。

**Runtime alarm**：监控自己的 TSDB cardinality，超阈值 alert dev。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 服务器规模 / metric 数 / 频率
  - 保留期 / SLO
  - Alert 渠道

0:05 - 0:10  Capacity Estimation
  - 250k samples/sec
  - 1 PB? No, only ~270 GB（强调 monitoring 比 log 便宜）
  - Cardinality 警告

0:10 - 0:15  High-Level Architecture
  - Pull (Prometheus) + Push (OTel) hybrid
  - TSDB + downsampling
  - Alert manager

0:15 - 0:30  Deep Dive
  ★ Cardinality 控制
  ★ Multi-resolution storage
  ★ Alert rules + anti-flapping
  ★ SLO / error budget

0:30 - 0:38  Follow-ups
  - Anomaly detection
  - Multi-region
  - VS Logger 区别

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK 这是 server monitoring。先估算：50k server × 50 metric / 10s = 250k samples/sec，每 sample 16 byte。Raw 43 GB/day，downsample 后 270 GB total。**比 logger 便宜得多** —— 这是观察 1。
> 
> 观察 2：**Cardinality 是 monitoring 的杀手**。每加一个 label，series 数乘 cardinality。`user_id` 当 label = 1B series = TSDB 死。Design 时严控 label。
> 
> 整体：Server agents → pull (Prometheus 主) + push (OTel for NAT-后) → TSDB (VictoriaMetrics / Thanos) → Grafana / Alert Manager → PagerDuty。
> 
> Pull vs push: 内网用 pull，dead server 立刻发现 (scrape fail)；edge / mobile / serverless 用 push。
> 
> Storage 用 multi-resolution：10s/1m/5m/1h 四级 downsample。看 1 年 trend 不需要每 10s 一个点，5 min 足够。这把存储压到 270 GB，单 cluster 装下。
> 
> Alert：rule 用 PromQL，`for: 5m` 防 spike 误报。SLO 用 burn rate 而非 raw error rate —— 让 alert 与 error budget 对齐。
> 
> Anomaly: 静态 threshold 加 statistical baseline (per metric × hour × weekday)。CPU 30% 在周末是 normal，工作日早上 9 点是 unusual → ML 检测。
> 
> 想 deep dive cardinality 控制还是 SLO？"

---

## 8. Follow-up 演练

### Q1: 怎么减少 alert fatigue?

**答**：
- 严格 anti-flapping (for >= 5min)
- Group alert: 同 service / 同 region multi-instance 触发 → 合并一条
- Silence during deploy (maintenance window)
- Severity tier (warning vs page)
- On-call rotation 不超过 5 page/周

### Q2: Cardinality 不小心爆了怎么办?

**答**：
- 紧急：drop 那些 high-card series (TSDB rule)
- 长期：fix code 不再 emit 那个 label
- Pre-flight：CI lint metric definitions

### Q3: Distributed tracing 集成?

**答**：Three Pillars: metric / log / trace。统一 OpenTelemetry SDK emit 三种数据，用 trace_id 作公共关联键。Metric 看"99 percentile latency 涨"，trace 看"具体哪条 request 慢"。

### Q4: Auto-remediation?

**答**：Alert 触发 webhook → automation script。例：
- CPU 高 → 自动 scale up
- Disk 满 → 自动 clear old log / rotate
- Service down → restart container

**Risk**：错误 fix 放大问题。最好 human-in-loop 重要 action。

### Q5: 跨 cloud (AWS + GCP + on-prem)?

**答**：每 region 各自 monitoring agent；OTel 标准 schema；中心 federation layer 跨 cloud 聚合 Grafana。

### Q6: 监控自己的 monitoring system?

**答**：典型 "who watches the watcher"。
- Self-monitoring：TSDB 自己也 emit metric 给另一个 TSDB
- External canary：第三方服务 ping monitoring API，挂了从外部 alert

---

## 9. 常见易错点

> [!pitfall]
> ❌ **label 含 user_id / request_id** —— series 爆，TSDB OOM；  
> ❌ **不 downsampling** —— 1 PB 存储，成本爆；  
> ❌ **静态 threshold 无 baseline** —— 工作日早上 CPU 50% 是 normal 也被 alert；  
> ❌ **无 anti-flapping** —— 1 spike = 100 page，oncall fatigue；  
> ❌ **不区分 severity** —— warning 和 page 混淆，重要 alert 被淹没；  
> ❌ **跨 cloud 单 cluster** —— 跨洋延迟，单点失败；  
> ❌ **Pull 模式无 alternative** —— NAT 后服务无 metric；  
> ❌ **SLO 没 burn rate** —— 太多 false alarm。

---

## 10. 加分项

- **Distributed tracing**：metric/log/trace 三合一 (OpenTelemetry)
- **Cost dashboard**：team-level metric volume + cost
- **AIOps**：ML detect correlation (CPU 涨 + memory 涨 + 用户报错 → 关联 root cause)
- **Synthetic monitoring**：模拟用户请求 (canary)
- **Chaos engineering hooks**：故意注入故障 + 监控 alert 是否触发
- **Real User Monitoring (RUM)**：客户端浏览器 metric (page load time, JS error)
- **Pyroscope / continuous profiling**：CPU / memory profile 而非只是 metric

---

## 11. 总结：你应该记住的 3 件事

1. **Cardinality 是 monitoring 的死穴**。任何 unique-per-request 字段都不能作 label。Design metric 时**先想清楚 label 维度的 cardinality 上限**。

2. **Multi-resolution storage** 让 monitoring 成本远低于 logger。10s/1m/5m/1h 四级 downsample 是工业 sweet spot。

3. **Alert 不是越多越好**。`for: 5min` + grouping + severity tier + burn-rate SLO，让 page 收敛到真正紧急的事件。Alert fatigue 比 missed alert 还危险。

> [!followup]
> **学习推荐**：(a) 跑通本机 Prometheus + Grafana quickstart；(b) 读 Google SRE Book 第 4-6 章 (SLO)；(c) 学 PromQL；(d) 看 Datadog / Honeycomb 工程博客；(e) 思考"如果你的 alert system 自己挂了，谁告诉你？"。
