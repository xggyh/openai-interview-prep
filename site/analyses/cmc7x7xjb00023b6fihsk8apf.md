## 题目本质

设计 GitHub Actions —— 当代码 push 时自动触发 workflow 执行，含**workflow 调度、worker（runner）执行隔离、实时日志监控、可观测性**。规模：1000 万 repos × 平均 10 pushes/s = 1M+ workflow run/s（峰值）。

OpenAI 报告 63 次，是这个数据集里最热的 SD 题。考点与 `Design a Ci/Cd Pipeline` 高度重合 —— 重点是**规模**和**多租户隔离**。

## 需求拆解

**功能性：**
- 解析 `.github/workflows/*.yml` 触发条件（push, PR, schedule, manual）
- workflow 由多个 job 组成，job 由多个 step 组成
- runner 在隔离环境（Linux/macOS/Windows VM）执行 step
- 实时日志推送 + 持久化
- artifact 上传下载 + 在 job 间传递
- self-hosted runner 支持

**非功能性：**
- 1M+ workflow run/s 峰值
- runner 启动延迟 < 30s
- 日志延迟 < 2s
- 99.95% 可用

## 整体架构

```ascii
   GitHub Webhook (push, PR, manual)
              │
              ▼
       ┌──────────────┐
       │ Event Router │  -- 解析事件，匹配 workflow yml
       └──────┬───────┘
              │
              ▼
       ┌──────────────────────┐
       │ Workflow Orchestrator│  -- DAG 调度
       │  (per workflow run)  │
       └──────┬───────────────┘
              │
              ▼ enqueue jobs
       ┌──────────────┐
       │ Job Queue    │  Kafka, partition by runner_label
       │ (sharded)    │
       └──────┬───────┘
              │
              ▼ pull
       ┌──────────────────────────┐
       │   Runner Fleet           │
       │  - GitHub-hosted (Azure VMs)
       │  - Self-hosted (customer infra)
       └──────┬───────────────────┘
              │
       ┌──────┼──────────────────────┐
       ▼      ▼                      ▼
  ┌──────┐ ┌─────────┐         ┌────────────┐
  │ Log  │ │ Artifact│         │ Workflow   │
  │ Pipe │ │ Store   │         │ State DB   │
  │ (Kafka)│ (S3)   │          │ (Postgres) │
  └──────┘ └─────────┘          └────────────┘
       │
       ▼
  ┌──────────┐
  │ Live tail│  SSE 实时
  │ + S3 cold│  归档
  └──────────┘
```

## 核心组件设计

### 1. Event Router

- 接 GitHub Webhook（每次 push、PR 都会调）
- 拉取该 repo 的 `.github/workflows/*.yml`（可缓存 by commit_sha）
- 按事件类型匹配 trigger（`on: push: branches: [main]`）
- 命中后构造 `WorkflowRun` 入库 + 发起 orchestration

### 2. Workflow Orchestrator

每个 workflow run 是一个状态机：

```python
states: queued → in_progress → success/failure/cancelled
jobs: 是 workflow run 内的子单位
    - 按 needs: 依赖图调度
    - 不同 job 可并行
    - 同 job 内 steps 顺序执行
```

实现：用 Postgres 持久化 state，orchestrator 是无状态服务，按事件驱动（job done event → 检查依赖 → 启动 next job）。

### 3. Runner Pool（最复杂）

**GitHub-hosted runners**：
- Azure VM pool，每 run 一台新 VM（绝对隔离）
- VM 启动时拉镜像 + 注册到 job queue
- run 完即销毁
- 启动慢（VM cold boot 30s+）—— 用 **warm pool** 预热

**Self-hosted runners**：
- 客户在自己 infra 跑 runner agent，长 poll job queue
- 客户标 `labels: [linux, gpu, custom]`，job 在 yml 写 `runs-on: [self-hosted, gpu]` 匹配
- 比 GitHub-hosted 启动快（机器常在）

**Queue 路由**：job 按 `runs-on` label 路由到对应队列；GitHub-hosted 走中央队列，self-hosted 走客户专属队列。

### 4. 隔离 / 多租户

- VM 级隔离（不是 container），防止容器逃逸
- Network egress allowlist（防止 runner 当 proxy）
- 每 job 临时 token，scoped to 这一个 run，过期失效
- Secrets：从 KMS 拉密文，注入环境变量，job 结束 zero out

### 5. 日志管道

```ascii
runner stdout/stderr
    │
    ▼ fluent-bit
    │
    ▼ Kafka topic: logs.{runId}.{jobId}
    │
    ├── SSE 实时推前端
    │
    └── 异步归档 S3 (Parquet 压缩，30 天后冷归档)
```

前端 `GET /runs/{id}/jobs/{jid}/logs/stream` → SSE 实时 tail。结束后切到 S3 静态 GET。

### 6. Artifact

- 用户在 yml `actions/upload-artifact` → runner POST → API GW → S3 multipart upload
- 下载 actions/download-artifact 同样走 API + S3 presigned URL
- 默认 90 天 expire

### 7. 计费

每 run 写一条 metric：
- runner_minutes（按 OS / 实例规格分别计价）
- artifact_storage_gb_days
- log_storage_gb_days

定期跑 ETL 出账。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 隔离 | VM per job | Container：被 escape 风险 |
| 队列 | Kafka 按 label 分 topic | 单大队列：路由难 |
| Orchestrator | Stateless service + Postgres | Temporal：可以但增加依赖 |
| 日志 | Kafka 实时 + S3 归档 | 直接 DB：吞吐撑不住 |
| Runner 启动 | warm pool 30 秒 P99 | Cold start：用户骂 |

## 容量估算

- 1M runs/s × 平均 3 jobs/run × 2 分钟/job = 360M runner-minutes/s
- 假设 GitHub-hosted 占 80% → 290M minute/s = 4.8M concurrent VMs
- → 数百万 VM 同时在跑，云成本巨大；GitHub 实际通过 warm pool + 任务批处理把利用率做到接近 100%

## 关键技术细节

- **DAG 调度**：yml 解析时检查环；运行时按拓扑序触发；同层 job 并行；matrix 展开
- **失败处理**：fail-fast on critical job；continue-on-error 标签允许 best-effort
- **重试**：单 job 失败上限 retry（用户 yml 控制）；orchestrator 退避重新入队
- **取消**：用户点 cancel → orchestrator 发 cancel event → 各 runner 检测到 → 优雅 shutdown

> [!key]
> 与 CI/CD Pipeline 题相比，GitHub Actions 的难点：(1) **多租户隔离**（runner 不能给客户当跳板）；(2) **规模**（1M run/s）；(3) **Self-hosted runner**（pull 模型）；(4) **Webhook → workflow yml 解析**这条链路。

> [!pitfall]
> ❌ Runner 不做 token scope —— 一个 run 偷别的 secret；
> ❌ Self-hosted runner push 模型 —— NAT 后客户跑不了；必须 pull；
> ❌ workflow yml 用户改一次重 schedule —— 必须按 commit_sha 缓存；
> ❌ 单大 job queue —— GitHub-hosted 抢占 self-hosted 资源；
> ❌ artifact 走 API 主流量 —— 应直传 S3。

> [!followup]
> "Schedule cron 怎么实现？" → 单独 cron service 按 yml 注册 cron 表达式，到点触发。"Workflow approval（人审批）？" → orchestrator 在该 job 之前进入 `waiting` 状态，等 webhook。"Reusable workflow？" → yml 里 `uses: other/workflow.yml`，orchestrator 解析时递归展开。
