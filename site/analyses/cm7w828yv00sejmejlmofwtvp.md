## 题目本质

设计 **Job Scheduler**：accept job 定义（func + schedule） → 按时执行 → handle failure / retry。如 cron at scale, Airflow, Kubernetes Jobs.

## 需求

- Cron-style + one-shot schedules
- Million+ jobs
- Distributed execution
- Failure retry + alerting
- Job dependencies (DAG)
- Idempotency guarantee

## 整体架构

```ascii
   Job definition (API/UI)
       │
       ▼
  ┌──────────────┐
  │ Scheduler    │  parse cron, compute next fire times
  │ Service      │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Schedule     │  upcoming-fire heap (next 1 hour)
  │ Wheel/Heap   │
  └──────┬───────┘
         │ fire
         ▼
  ┌──────────────┐
  │ Job Queue    │  Kafka / SQS
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Worker Pool  │  execute, retry on fail
  └──────┬───────┘
         │ done
         ▼
  ┌──────────────┐
  │ Job Status   │  DB + audit
  └──────────────┘
```

## 核心组件

### 1. Schedule parsing

- Cron format: `0 9 * * 1` (Mondays at 9am)
- Custom: every N hours, every Friday after 5pm
- Use library: cronexpr / croniter

### 2. Schedule wheel / heap

Min-heap of (next_fire_ts, job_id)。Scheduler:
- Pop fired jobs → enqueue to job queue
- Compute next fire time (cron) → push back

每秒 wake 一次，process expired heap entries。

For million jobs: shard heap by hash(job_id) across multiple scheduler instances。每 instance own subset。

### 3. Distributed scheduler (leader-based)

Multiple scheduler instances 通过 Zookeeper / etcd leader 选举。Leader own job assignment。Non-leader hot standby。

Or: partitioned ownership —— 每 instance own 一段 hash range（类似 Kafka consumer group）。

### 4. Job queue → workers

Worker pull job from queue → execute → ack。
- Retry on fail (exponential backoff, max 3-5 retries)
- Move to dead letter after max retry
- Alert owner

### 5. Job 执行模型

- **Direct call**: simple HTTP / RPC call
- **Container**: spawn ephemeral container with code
- **Lambda function**: invoke serverless
- **Workflow**: trigger DAG of sub-jobs (Airflow-style)

### 6. Idempotency

Job 可能被 fire 多次（network retry, scheduler failover）。每 firing 有 unique execution_id。Worker check：if execution_id already processed (look DB), skip。Side effects 用 idempotency key。

### 7. Dependencies (DAG)

Job B depends on A success → trigger only after A done。

Implementation: store dependency edges。On job complete, check downstream jobs whose deps all done → enqueue。

Airflow uses this model。

### 8. Resource limits

Per-tenant / per-job:
- Max parallel concurrent runs
- Max execution time (timeout)
- CPU / memory quota

### 9. Manual trigger / pause

Admin pause job (skip scheduling) / trigger now / re-run failed。

### 10. Audit + history

每 execution record: started_at, finished_at, status, output, error. Last N days searchable。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Schedule store | Heap / wheel | DB scan：慢 |
| Distribution | Leader / shard ownership | Single instance：bottleneck |
| Execution | Container / serverless | In-process：noisy neighbor |
| Idempotency | execution_id + dedup | None：double execute |

## 容量估算

- 1M jobs × avg 1 fire/hour = 277 firings/sec
- Worker pool: avg job 30s → ~8000 workers
- Storage: 1M × 10 history × 5KB = 50 GB

## 易错点

> [!pitfall]
> ❌ 单 scheduler → single point of failure；
> ❌ Naïve heap polling per second × 1M jobs → CPU 爆；
> ❌ 不 idempotent → side effects 重复；
> ❌ Retry forever → 死循环；
> ❌ 不限 concurrent runs → 同 job 100 个并行 race。

> [!key]
> 三大要点：(1) **Heap / time wheel + sharded ownership**；(2) **Queue + worker pool + idempotency**；(3) **DAG dependencies + retry policy**。

> [!followup]
> "如何 trigger by event (file uploaded → run job)？" → event-driven scheduler subscribe Kafka；"如何 graceful shutdown worker？" → SIGTERM → finish current job → die；"Cross-region job？" → 中心 scheduler 但执行在最近 region worker。
