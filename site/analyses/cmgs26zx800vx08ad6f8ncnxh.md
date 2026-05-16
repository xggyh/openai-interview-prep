## 题目本质

设计 **Global VM Monitoring System**：监控全球数据中心 100k+ VMs 的健康（CPU / mem / disk / network / 服务状态）。Hyperscale cloud 必备。

类似 [[cm6jwhimp0093dar9n0eo4lvt]] (Server Health Monitoring) 但更大规模 + 跨 region。

## 需求

- 100k+ VMs across multiple regions/DCs
- 10 sec metric resolution
- Real-time anomaly alerts < 1 min
- Historical trend 1 year+
- Multi-tenant (per customer)

## Key differences vs single-region server monitoring

### 1. 跨 region 数据收集

每 region 独立 collector + TSDB。Global aggregation via federation。
- Local: low-latency, region-isolation
- Global: cross-region view via Thanos / Cortex

### 2. Multi-tenant isolation

每 customer / VM tag 自己 visibility。RBAC:
- Customer A 只看 own VM metrics
- Cloud operator 看 all
- Per-tag dashboard, per-tag alert rules

### 3. Auto-discovery

VMs 启动 / 终止动态。Monitoring agent 自动 register / deregister。Service discovery 用 K8s service or cloud API。

### 4. VM-specific metrics

不只是 generic CPU / mem，还有：
- Hypervisor metrics (vCPU steal time，noisy neighbor detect)
- Guest OS metrics (process list, file system)
- Network: per-VM bandwidth, packet loss
- Cloud-specific: instance type, AZ, billing tier

### 5. Anomaly detection

100k VM × 30 metrics × 24/7 → 不可能 manual baseline。ML:
- Per-VM baseline (1 周训练 + 滑动更新)
- Group baseline (instance type 集群)
- Anomaly = current vs baseline > 3σ

### 6. Capacity planning

不仅 monitoring，还 forecast：
- VM 增长趋势
- 哪些 region capacity 紧张
- 推动 capacity allocation 决策

### 7. Cost monitoring

跨 region cost dashboard。Per-VM hourly cost based on instance type × region。Detect cost waste（idle VMs, oversized instances）。

### 8. Failure escalation

层级 escalation:
1. Auto-remediation (restart VM, scale up)
2. Auto-alert on-call engineer
3. Auto-page senior on-call after 15 min
4. Customer notification for major outage

## 架构

参考 [[cm6jwhimp0093dar9n0eo4lvt]] 整体架构 + 加：
- Per-region collector + TSDB cluster
- Global federation layer (Thanos)
- Multi-tenant access layer
- ML anomaly engine
- Auto-remediation engine

## 易错点

> [!pitfall]
> ❌ Single global TSDB → 跨洋延迟；
> ❌ 不 RBAC → customer A 看到 B 的 metrics；
> ❌ Static threshold → ML 异常 missing；
> ❌ Capacity planning 只看现状 → forecasting 缺；
> ❌ Auto-remediation 不限制 → 错误 fix 放大问题。

> [!key]
> 单 region monitoring + (federation, multi-tenancy, auto-discovery, ML anomaly, auto-remediation) = enterprise hyperscale monitoring。

> [!followup]
> "如何 detect noisy neighbor on hypervisor？" → 监控 steal time + ML correlation per-VM；"customer 自定义 metric？" → user-pushed metric endpoint + namespace；"VM live migration 时如何 maintain monitoring？" → metric stream resume by VM UUID not by IP。
