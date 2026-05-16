## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **VM (Virtual Machine)** | 虚拟机，跑在 hypervisor 上的虚拟服务器 | 一栋楼里隔出的多间公寓 |
| **Hypervisor** | 管 VM 的底层软件（KVM / Xen / Hyper-V） | 公寓楼的管理处 |
| **AZ / Region** | 可用区 / 区域。AWS / GCP 把全球分成几十个 region，每 region 内几个 AZ | 同城多分店 |
| **Multi-tenant** | 一套系统多客户共用，但数据/权限隔离 | 写字楼里多家公司 |
| **OTel (OpenTelemetry)** | metric/log/trace 统一标准 | 通用医疗记录格式 |
| **Federation** | 多 region 各自跑 monitoring，中心层聚合 | 联邦制 |
| **Cardinality** | 不同 series 数。Label 多 → 爆炸 | 颜色板上多少色 |
| **RBAC** | Role-Based Access Control，按角色赋权 | 不同等级钥匙开不同门 |
| **Steal time** | hypervisor 不让你 vCPU 用足时间，被"偷"了 | 你订座但被别人挤了 |
| **Noisy neighbor** | 同 hypervisor 上另一 VM 抢资源，让你慢 | 楼上邻居半夜跳广场舞 |
| **Self-service** | 客户自己 onboarding 不需要 ops 帮 | 自助办理 |
| **AIOps** | AI for IT operations，用 ML 自动找 root cause / detect anomaly | 智能助手 |

---

## 1. 题目本质 — 这是什么问题

**Global VM Monitoring System** = hyperscale cloud（AWS / GCP / Azure / 阿里云）给客户提供"我所有 VM 健康状况"的 service。

**典型场景**：
- AWS CloudWatch 监控你 EC2 instances
- GCP Cloud Monitoring 看 GCE VMs
- 阿里云监控看 ECS
- 自建 OpenStack 私有云的运维 dashboard

**与基础 Server Health Monitoring 区别**：

| 维度 | Server Health (内部) | Global VM Monitoring |
|---|---|---|
| 用户 | 自家 ops team | 外部 customer (多租户) |
| Scale | 50k 服务器 | 100k+ VMs，几千客户 |
| 隔离 | 不需要 | 必须（cross-customer leak = breach） |
| 计费 | 不需要 | 需要（charge by data volume / retention） |
| 特性 | metric only | metric + log + alarm + dashboard |
| Hypervisor metric | 不必 | 必备（noisy neighbor 等） |
| 自服务 | ops 直接 config | customer self-serve UI / API |

考点：**multi-tenancy + federation + hypervisor-aware + cost / billing**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：监控哪些 metric？  
**典型答**：(a) Guest OS: CPU / mem / disk / network；(b) Hypervisor: steal time / vCPU throttling；(c) 网络 / 磁盘 latency；(d) Custom app metric。

**你问**：自服务用户能做什么？  
**典型答**：(a) 看 dashboard；(b) 设 alarm rule；(c) 配 channel (email / webhook)；(d) 跨 VM aggregate。

**你问**：要不要 cost monitoring？  
**典型答**：要。客户想知道哪些 VM 浪费钱（idle）+ 哪些超资源。

**你问**：要不要 anomaly detection？  
**典型答**：基础 threshold alarm 必须。ML anomaly 是加分项。

### 2.2 非功能性

**你问**：规模？  
**典型答**：100k+ VMs，几千 customer。

**你问**：metric resolution？  
**典型答**：默认 1 min（free tier），customer pay 可 10s / 1s (high freq)。

**你问**：保留？  
**典型答**：1 min × 15 day free；5 min × 3 month；1 h × 1 year (long-term cold)。

**你问**：跨 region？  
**典型答**：所有 region 都要 cover，customer 可看 cross-region 视图。

### 2.3 需求清单

```
功能：
- Multi-tenant metric / log / alarm
- 跨 region dashboard
- Cost monitoring
- Hypervisor metric (steal time, noisy neighbor)
- Self-service onboarding

非功能：
- 100k+ VMs (3 倍冗余 → 300k entity monitor)
- Strict per-customer isolation
- 15min 内 alarm 触发
- 多 region federation
```

---

## 3. 容量估算

### 3.1 数据量

```
100k VMs × 50 metric × 1 sample/min = 5M samples/min = 83k samples/sec
```

5x peak buffer → ~400k samples/sec write。

### 3.2 跨 region 划分

```
Region 1 (US-East):  30k VMs → local cluster 处理
Region 2 (EU-West):  20k VMs
Region 3 (APAC):     30k VMs
Region 4 (US-West):  20k VMs
```

每 region 独立 TSDB；global federation 跨 region query。

### 3.3 存储

类似 [[cm6jwhimp0093dar9n0eo4lvt]] (Server Health) — multi-resolution 后 ~270 GB total / region。

### 3.4 估算清单

```
Write: 400k samples/sec aggregate
Per region: 100k samples/sec
Storage: ~1 TB total (across 4 regions, multi-resolution)
Read: customer dashboard / alarm eval ~k QPS
```

---

## 4. 整体架构 step by step

### 4.1 第 1 步：单 region 单租户

参考 [[cm6jwhimp0093dar9n0eo4lvt]] (Server Health Monitoring) 架构。Agent → Kafka → indexer → TSDB → Grafana / Alert manager。

### 4.2 第 2 步：Multi-tenant 隔离

```ascii
                Customer A's VMs (~1000)         Customer B's VMs (~50000)
                       │                                    │
                       ▼                                    ▼
                   ┌────────────────────────────────────────┐
                   │ Ingest Endpoint                        │
                   │  Auth → assign tenant_id               │
                   │  Quota check                           │
                   └─────────────────┬──────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ Kafka        │  partition by tenant_id
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ TSDB         │  per-tenant index/namespace
                              │              │  data physically isolated
                              └──────┬───────┘
                                     │
            ┌────────────────────────┼──────────────────────┐
            ▼                        ▼                      ▼
       Customer A's              Customer B's          Internal ops
       Grafana                   Grafana               (sees all,
       (only Customer A          (only Customer B       privileged)
        VMs)                     VMs)
```

**Tenant isolation 的多层防御**：

1. **Auth**：每 metric push 必带 customer API token
2. **Partition**：Kafka by tenant_id，consumer 不会混
3. **TSDB namespace**：每 customer 独立 prefix (`customer:abc/metrics`)
4. **Query RBAC**：dashboard query 必带 tenant_id filter，service 强制 inject
5. **Network isolation**：customer VM 不能直接访问其他 customer 的 ingest endpoint

### 4.3 第 3 步：Multi-region Federation

```ascii
   per-region monitoring:
   
   US-East          EU-West          APAC          US-West
   ┌──────┐         ┌──────┐         ┌──────┐      ┌──────┐
   │ TSDB │         │ TSDB │         │ TSDB │      │ TSDB │
   └───┬──┘         └───┬──┘         └───┬──┘      └───┬──┘
       │                │                 │             │
       └────────┬───────┴────────┬────────┴─────────────┘
                │                │
                ▼                ▼
          ┌──────────────────────────┐
          │ Federation Layer         │  Thanos / Cortex / VictoriaMetrics cluster
          │ (global query API)       │
          └──────────────────────────┘
                       │
                       ▼
                  Customer dashboard
                  (cross-region query)
```

**为什么这样**：
- ✅ Region 故障不影响其他
- ✅ 数据 local 处理，跨洋少
- ✅ 客户可自选 region（合规 / 数据驻留法）
- ✅ Global view 通过 federation 提供（query-time aggregate）

### 4.4 第 4 步：Hypervisor-aware Metrics

cloud-specific：除了 guest OS metric，还看 hypervisor 层：

```
- vCPU steal time     (hypervisor 调度让你的 vCPU 等待)
- IO wait %           (磁盘瓶颈)
- Network packets dropped at hypervisor
- Memory ballooning   (hypervisor 把 host memory 还来)
```

**为什么这些重要**：客户 VM CPU 100% 可能不是 app bug，是 noisy neighbor 抢资源。Cloud 厂商 dashboard 能告诉客户"你的慢是 neighbor 引起的，我们会 migrate 你的 VM"。

### 4.5 第 5 步：完整架构

```ascii
┌───────────────────────────────────────────────────────────┐
│ Per-region (US-E, EU-W, APAC, US-W)                       │
│                                                           │
│  Customer VMs / Hypervisors                               │
│       │                                                   │
│       ▼ (push metric, auth+tenant_id)                     │
│  ┌──────────────────┐                                     │
│  │ Ingest GW        │                                     │
│  └──────┬───────────┘                                     │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐                                     │
│  │ Kafka            │  partition by tenant                │
│  └──────┬───────────┘                                     │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ Indexer          │    │ Stream Proc      │             │
│  │ (pii_redact +    │    │ (alerts +        │             │
│  │  enrich)         │    │  anomaly ML)     │             │
│  └──────┬───────────┘    └──────┬───────────┘             │
│         │                       │                         │
│         ▼                       ▼                         │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ TSDB             │    │ Alert Manager    │             │
│  │ (tenant         │    │ (per-tenant      │             │
│  │  namespaces)     │    │  channels)       │             │
│  └──────┬───────────┘    └──────────────────┘             │
└─────────┼─────────────────────────────────────────────────┘
          │
          ▼ (global federation)
   ┌──────────────────┐
   │ Thanos / Cortex  │  cross-region aggregation
   └──────┬───────────┘
          │
          ▼
   Customer dashboard (multi-region view)
```

---

## 5. 每个组件深挖

### 5.1 Tenant isolation 详细

```python
# 1. Push with auth
POST /v1/metrics
Headers:
  Authorization: Bearer <customer_token>
Body:
  {timestamp, metric, value, labels, vm_id}

# 2. Backend extract tenant
def ingest(request):
    tenant_id = auth_resolve(request.headers['Authorization'])
    if not tenant_id:
        return 401
    
    # Inject tenant_id as label
    request.body.labels['tenant_id'] = tenant_id
    
    # Rate limit
    if exceeded(tenant_id):
        return 429
    
    kafka.produce('metrics', request.body, partition_key=tenant_id)

# 3. Query enforces tenant filter
def query(user_id, promql):
    tenant_id = get_tenant(user_id)
    # 强制 inject tenant_id filter
    parsed = parse_promql(promql)
    parsed.add_label_filter('tenant_id', tenant_id)
    return tsdb.query(str(parsed))
```

**关键**：query path 强制 inject filter，**用户写 promql 不能跳过**。这是 multi-tenant 的灵魂。

### 5.2 RBAC 细化

```yaml
roles:
  customer_admin:
    - read: own_tenant_metrics
    - write: alarm_rules (own tenant)
    - write: dashboards (own tenant)
  
  customer_developer:
    - read: own_tenant_metrics (subset by tag)
    - read: dashboards
  
  cloud_operator:
    - read: ALL tenants (audit logged)
    - write: ALL (危险，需双重 approval)
```

**Audit**：cloud operator 看 customer metric 必须留 audit log（who saw what when why）。

### 5.3 Auto-discovery

VM 数量 dynamic（auto scale / 创建删除）。Monitoring 自动 register / deregister：

```python
# K8s / cloud API watch
on_vm_created(vm):
    # 自动 deploy agent 到 VM (via cloud-init script)
    config = generate_agent_config(tenant_id, vm.id)
    inject_to_vm(vm, config)

on_vm_terminated(vm):
    # 标记 metric series 为 inactive
    # TSDB 周期清理 30 day 没数据的 series
    pass
```

不需要 customer 手动 register。

### 5.4 Hypervisor Metric

```
metric_name                       label                    description
─────────────────────────────────────────────────────────────────────
vcpu_steal_time_seconds_total    vm_id, hypervisor_id    被 hypervisor 抢走的时间
hypervisor_cpu_pressure_score    hypervisor_id            host 整体压力
network_packets_dropped_total    vm_id, direction         hypervisor 丢包
memory_balloon_pages             vm_id                    被 hypervisor 收回的 page
io_wait_ratio                    vm_id                    等磁盘的时间比
```

**对客户的价值**：客户看到 "你的 VM 慢是因为 noisy neighbor"，可以申请 migrate 或 upgrade dedicated host。

### 5.5 Cost Monitoring

```
Per VM cost / hour = base + storage + network + custom_metric_volume

Dashboard:
  - VM cost by tag / project / region
  - "Top 10 most expensive idle VMs" (低 util)
  - Trend over time
  - Forecast (model 学 monthly bill 预测)
```

帮客户 optimize cost (rightsize VM, terminate idle)。**Cloud 公司 incentive 反过来**？看似——但实际良好 cost mgmt = customer retention + 长期收入。

### 5.6 Anomaly Detection (ML)

Per metric × per VM 学 baseline：

```python
class MLAnomalyDetector:
    def train(self, metric, vm_id):
        history = load_4_weeks(metric, vm_id)
        # per (hour, weekday) compute baseline
        baseline = history.groupby([hour, weekday]).agg(['mean', 'std'])
        return baseline
    
    def detect(self, value, metric, vm_id, t):
        baseline = get_baseline(metric, vm_id)
        expected = baseline[t.hour][t.weekday]
        if abs(value - expected.mean) > 3 * expected.std:
            return 'anomaly'
        return 'normal'
```

每 VM 独立 baseline → 个性化。例：vm1 在每天 8AM CPU 50% 是 normal（cron job），vm2 是 anomaly。

### 5.7 Auto-remediation

```
Alarm: disk usage > 90% on vm-123
  → Automation runbook:
    1. Detect log files / temp files
    2. Auto-clear < 30 day log files
    3. Re-evaluate after 5 min
    4. If still > 90%, alert human
```

**Risk**：自动 fix 错的话放大问题。所以仅对**well-understood, low-blast-radius** 操作 (clear log, restart service)，重要 ops 不自动化。

### 5.8 Failure isolation

```
US-East region 故障 → 
  - 其他 region 仍 work
  - US-East customers 暂时无 monitoring
  - 全球 dashboard 显示 "US-East region degraded"

避免：单 global TSDB 挂了全公司 monitoring 没了
```

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - Scale, multi-tenant?
  - Hypervisor metric?
  - Self-service?
  - Region coverage?

0:05 - 0:10  Capacity Estimation
  - 100k VMs, 400k samples/sec
  - Federation 跨 region

0:10 - 0:15  High-Level Architecture
  - Per-region pipeline
  - Federation layer
  - Multi-tenant isolation

0:15 - 0:30  Deep Dive
  ★ Multi-tenant isolation (auth, RBAC, query injection)
  ★ Hypervisor metric (steal time, noisy neighbor)
  ★ Federation cross-region
  ★ Cost monitoring + anomaly ML

0:30 - 0:38  Follow-ups
  - Auto-remediation
  - Multi-cloud?
  - VM live migration 监控？

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK 这是 cloud-scale VM monitoring。与单内部 server monitoring 关键区别：(1) **multi-tenant** 必须 strict isolation；(2) **hypervisor metric** —— customer 看 'noisy neighbor' 这种；(3) **federation** —— global view 跨 region。
> 
> 估算：100k VMs × 50 metric / min = 83k samples/sec, peak 400k aggregate。分 4 region 处理。
> 
> 整体：per-region pipeline (ingest → Kafka → TSDB)，cross-region 用 Thanos / Cortex federation。Customer 写 promql 时 query layer 自动 inject `tenant_id` filter —— 这是 isolation 的灵魂。
> 
> Multi-tenant 多层防御：(1) auth 拿 tenant_id；(2) Kafka partition；(3) TSDB namespace；(4) query RBAC 强制 inject filter；(5) network isolation。
> 
> Hypervisor metric 是 cloud-specific 价值：vCPU steal time / packets dropped at hypervisor / memory balloon。客户看 'CPU 100% 是因为 noisy neighbor' → 申请 migrate。
> 
> Cost monitoring：per-VM cost dashboard + 'top idle VMs' helper → customer 自己优化成本。
> 
> Anomaly：per VM × per metric × hour-of-day-baseline。VM A 早 8AM CPU 50% normal，VM B 异常 → ML 区分。
> 
> Auto-remediation：仅限低风险（clear log，restart service），重大 ops 不自动。
> 
> Deep dive multi-tenant isolation 还是 hypervisor metric？"

---

## 8. Follow-up 演练

### Q1: Customer 突然 push 大量 metric，怎么防止它影响其他 customer？

**答**：
- Per-tenant rate limit at ingest GW
- Kafka partition by tenant_id → noisy tenant 不影响其他 partition consumer
- Per-tenant resource quota (TSDB cardinality, query QPS)
- 超额 alert + 限流

### Q2: VM live migration（VM 从 host A 搬到 host B）时怎么 maintain monitoring？

**答**：Metric stream resume by **VM UUID**, not IP。VM IP 可能变，UUID 不变。Agent restart 后继续 push，series 不间断。

### Q3: Multi-cloud (customer 用 AWS + GCP + Azure)?

**答**：Each cloud 各自 agent + OTel 标准格式 → 数据汇到中心 federation。Customer dashboard 看 cross-cloud aggregated view。

### Q4: 客户报"我 dashboard 数据不对 / 看到别人数据"怎么处理?

**答**：极高优 incident。立即：
- Audit log: 客户最近 query / who has access to that view
- Check tenant_id injection logic
- Page security team

预防：query path 全 unit test + integration test，bug bounty。

### Q5: Hypervisor metric 客户拿不到自家 hypervisor 物理详情怎么办（合规要求）？

**答**：抽象成 "noisy neighbor score" 这种 derived metric，不暴露 hypervisor ID。Customer 知道 "你的 VM 同 host 有压力"，但不知道具体 host 信息。

### Q6: 全 region 数据汇总到 federation，跨洋延迟大怎么办?

**答**：Federation 只查近 1 hour 实时；老数据每 region 各自 cold storage，cross-region query 用 async batch (Athena over S3 Parquet)。

### Q7: 客户怎么 onboard 自己的 VM?

**答**：
1. Customer 在 console 启用 monitoring (1 click)
2. 系统给 API token
3. VM image / cloud-init 自动安装 agent + config token
4. 5 分钟后 dashboard 看到数据

完全 self-service，无 ops involve。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **Tenant id 不强制 inject** —— customer A 查到 customer B 数据 → 巨大 incident；  
> ❌ **Single global TSDB** —— 跨洋慢 + 单点故障；  
> ❌ **不监控 hypervisor metric** —— 客户无法 diagnose noisy neighbor；  
> ❌ **不做 per-tenant rate limit** —— noisy tenant 拖垮整个 ingest；  
> ❌ **Cost monitoring 缺失** —— customer 用 invisible spend，churn；  
> ❌ **Audit log 不全** —— compliance fail；  
> ❌ **Auto-remediation 范围过大** —— 错误 fix 放大；  
> ❌ **不支持 VM live migration** —— migrate 后 monitor 断 → false outage alarm。

---

## 10. 加分项

- **AIOps**：correlation analysis 自动找 root cause
- **Synthetic monitoring**：模拟用户请求 (canary)
- **Distributed tracing 集成**：metric + log + trace 三合一
- **Capacity forecasting**：ML 预测 VM 何时需 upsize
- **Custom metric**：客户自定义 metric 名 + 维度
- **Marketplace integration**：第三方监控插件 plug-in
- **Compliance pack**：HIPAA / PCI 预设 alarm + audit
- **Cost optimization recommendations**：ML rightsizing

---

## 11. 总结：你应该记住的 3 件事

1. **Multi-tenant isolation 是 cloud monitoring 的灵魂**。Auth → tenant_id → 各层强制 inject filter → audit log。任何一层漏洞 = customer data leak = 公司公关灾难。

2. **Federation 比 single global cluster 好**。每 region 独立 + global aggregate。Region 故障局部化，跨洋延迟规避。

3. **Hypervisor-aware monitoring 是 cloud value-add**。客户自己装的 monitoring 只能看 guest OS，cloud 厂商能 expose hypervisor 层（noisy neighbor / steal time）。这是客户为啥用 native monitoring 而非第三方的理由。

> [!followup]
> **学习推荐**：(a) 试 AWS CloudWatch / GCP Cloud Monitoring 实际操作；(b) 读 Thanos / Cortex 架构；(c) 看 Datadog multi-tenant talk；(d) 学 Prometheus exposition + relabeling；(e) 思考 "cloud monitoring 怎么不竞争自己的 customer SaaS biz" (AWS 自己卖 CloudWatch，但 Datadog 也跑在 AWS 上)。
