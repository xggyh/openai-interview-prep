## 题目本质

设计一个 CI/CD pipeline 系统：每次 deployment 事件触发一组**有依赖的任务（DAG）按 stage 顺序执行**。任务长度变化（几秒到几小时），需要分布式执行 + 重试 + 实时日志 + 观测。

参考：CircleCI / Jenkins / GitHub Actions / OpenAI 内部 deploy 系统。

## 需求拆解

**功能性：**
- 用户在 yaml 定义 pipeline（stages + tasks + dependencies）
- Push event 触发 pipeline 执行
- 任务在 worker 上跑，输出 log 实时推到前端
- 失败可手动重试某个 stage 或整 pipeline
- artifacts 在 stage 间传递

**非功能性：**
- 1k 并发 pipeline 起步
- 任务调度延迟 < 5s
- 日志可追溯 30 天

## 整体架构

```ascii
   GitHub Webhook
        │
        ▼
   ┌─────────────┐
   │ Trigger     │  → 解析 .pipeline.yml，提交 Pipeline Run
   │  Service    │
   └──────┬──────┘
          │
          ▼
   ┌─────────────────────┐
   │ Pipeline Orchestrator│  → 计算 DAG，按 stage 入队
   │  (state machine)     │
   └──────┬──────────────┘
          │
          ▼
   ┌─────────────────────┐
   │  Task Queue          │  ◀── Redis Stream / NATS
   │  (per stage)         │
   └──────┬──────────────┘
          │
          ▼
   ┌──────────────────────────────┐
   │  Worker Fleet                │
   │  (Docker / K8s pods,         │
   │   isolated per task)         │
   └──────┬─────────┬─────────────┘
          │         │
          ▼         ▼
   ┌──────────┐  ┌──────────────┐
   │ Log      │  │ Artifact     │
   │ Stream   │  │ Store (S3)   │
   │ (Kafka)  │  │              │
   └────┬─────┘  └──────────────┘
        │
        ▼
   ┌─────────────┐
   │  Frontend   │  → live tail via SSE
   └─────────────┘
```

## 核心组件设计

### 1. Pipeline 定义（DAG）

```yaml
stages:
  - name: build
    tasks:
      - name: compile
        image: python:3.12
        cmd: pip install . && pytest --collect-only
      - name: lint
        image: alpine
        cmd: ruff check
  - name: test
    needs: [build]
    tasks:
      - name: unit-tests
        image: python:3.12
        cmd: pytest
      - name: integration
        image: postgres-test
        cmd: pytest tests/integration
  - name: deploy
    needs: [test]
    when: branch == 'main'
    tasks:
      - name: deploy-prod
        image: deployer
        cmd: kubectl apply -f k8s/
```

Orchestrator 解析 yml → 构造 `(task, deps, image, cmd)` DAG → 拓扑序入队。

### 2. State Machine

每个 task 状态：`pending → queued → running → success / failed / skipped / cancelled`
每个 stage 状态：所有 task done → next stage triggered

```python
class TaskState(Enum):
    PENDING, QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED, CANCELLED = range(7)

class PipelineRun:
    id: UUID
    pipeline_id: UUID
    commit_sha: str
    triggered_by: str
    state: str
    started_at: datetime
    completed_at: datetime | None
    stages: list['StageRun']

class StageRun:
    state: TaskState
    tasks: list['TaskRun']

class TaskRun:
    id: UUID
    name: str
    image: str
    cmd: list[str]
    state: TaskState
    started_at: datetime | None
    completed_at: datetime | None
    exit_code: int | None
    log_url: str  # S3 / Kafka topic ref
```

Orchestrator 维护 finite state machine —— task done 事件触发"是否本 stage 都好了 → 启动下 stage"。

### 3. Worker 隔离

每个 task **独立容器** —— 隔离 + image 自由 + 失败自愈。K8s pod 是最佳选择：
- 启动 worker → mount artifact volume → docker run task image → 退出后清理
- 资源限制 via K8s ResourceQuota

冷启动慢可以通过 **worker pool 预热** 缓解（保留 N 个空 pod 等任务）。

### 4. 日志流式

```ascii
worker stdout/stderr
    │
    ▼
fluent-bit sidecar
    │
    ▼
Kafka topic: pipeline.{runId}.{taskId}
    │
    ├── 实时推送 → SSE → frontend
    └── 归档 → S3 (cold storage 30d)
```

前端调 `GET /runs/{id}/tasks/{tid}/logs/stream` → SSE 持续 push。完成后切到 S3 静态。

### 5. Artifact 在 stage 间传递

每个 task 声明 `outputs: [./dist, target/release]` → worker 把目录 tar + 上传 S3 → 下个 task 启动前 worker 拉对应 artifact 解压到 `./inputs/`。

### 6. 重试 / 重启

- 单 task 失败：自动 retry 上限 3 次（exponential backoff）
- 手动重启：用户点 "Retry this stage" → orchestrator 创建该 stage 的新 TaskRun（保留旧记录），从该 stage 开始重跑下游

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 调度单位 | Pod per task | Long-running worker：状态污染 |
| 队列 | Redis Stream（per stage） | RabbitMQ：太重 |
| 日志 | Kafka 实时 + S3 归档 | 直接 DB：写吞吐撑不住 |
| Orchestrator | Stateful service + Postgres | Workflow engine（Temporal）：可作为替代，免费版功能受限 |

## 关键技术细节

- **DAG 调度避免环**：yaml 解析时检测 cycle
- **并行限制**：用户 yml 可以指定 `parallelism: 4`，超出排队
- **缓存**：相同 commit + cmd hash → 命中缓存跳过任务
- **secrets 注入**：worker 启动前从 Vault 拉，环境变量注入，task 结束销毁

> [!key]
> 这题核心是**DAG + 分布式 worker + 状态机**。亮点：(1) per-task 容器隔离；(2) 日志走 Kafka 流；(3) artifact 用 S3 中转；(4) state machine 驱动 stage 切换。

> [!pitfall]
> ❌ 一个 long-running worker 跑多 task —— 状态污染、清理麻烦；
> ❌ 日志直写 DB —— 写吞吐瓶颈；
> ❌ 不做 secrets 隔离 —— 大事故；
> ❌ 没有 idempotency —— webhook 重发导致 pipeline 跑两遍。

> [!followup]
> "如何支持 matrix build（多 OS / 多 Python 版本）？" → 每行 matrix 展开成独立 task。"如何做 fan-out / fan-in（map-reduce 风格）？" → DSL 支持 `parallel: [...]` 节点。"如何防止恶意 yml 跑挖矿？" → resource quota + 白名单 image registry + 监控异常 CPU 模式。
