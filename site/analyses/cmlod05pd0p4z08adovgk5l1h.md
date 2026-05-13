## 题目本质

设计一个**大规模分布式 crossword puzzle 求解服务**：用户提交一个 puzzle（含字典 + 空格 grid），服务并发处理多个 puzzle，每个 puzzle 高效求解。

考点：**回溯搜索 + 任务队列分发 + GPU/CPU 工作池** + **结果缓存**。

## 需求拆解

**功能性：**
- POST `/solve` 提交 puzzle（grid + word list）→ 返回 jobId
- GET `/solve/{jobId}` 轮询结果（或 webhook 推送）
- 单 puzzle 平均求解时间 < 30s，大 puzzle < 5 min
- 同时支持 1000+ 并发 puzzle

**非功能性：**
- worker pool 横向扩展
- 同样的 puzzle 应该有缓存（去重）
- 任务可优先级（付费用户优先）

## 整体架构

```ascii
   Client ─▶ API GW ─▶ /solve POST
                          │
                          ▼
                  ┌─────────────┐
                  │ Solver API  │
                  │  (lookup    │
                  │   cache)    │
                  └──────┬──────┘
                         │
                  ┌──────┼────────┐
                  ▼      ▼        ▼
            ┌─────────┐ ┌──────────────┐
            │ Result  │ │ Job Queue    │  ◀── Redis Stream / SQS
            │ Cache   │ │ (priority)   │
            │ (Redis  │ └──────┬───────┘
            │  +S3)   │        │
            └─────────┘        ▼
                       ┌──────────────┐
                       │ Worker Pool  │  K8s deployment
                       │ (CPU heavy)  │  autoscale by queue depth
                       └──────┬───────┘
                              │
                              ▼ result
                       ┌──────────────┐
                       │ Result Store │
                       │ (Postgres)   │
                       └──────────────┘
```

## 核心算法（Worker 上跑的）

经典 crossword 求解：**约束传播 + 回溯（DFS with constraint propagation）**。

```python
def solve_crossword(grid, words):
    """grid: 2D list of either '.' (empty) or '#' (block)
    words: list of strings (dict)"""
    # 1. 找到所有 slots（连续的空格段，水平 / 垂直）
    slots = find_slots(grid)
    # slots = [{'cells':[(r,c)...], 'len':L, 'dir':'H'/'V'}]

    # 2. 建立约束图：slot 之间的交叉点
    crossings = build_crossings(slots)   # crossings[(i,j)] = (cell_i_idx, cell_j_idx)

    # 3. 按 most constrained first 排序 slots
    slots.sort(key=lambda s: -len([c for c in crossings if c[0] == s_idx]))

    def backtrack(slot_idx, assignment):
        if slot_idx == len(slots):
            return assignment
        slot = slots[slot_idx]
        # 按字典筛同长度的词
        candidates = [w for w in words if len(w) == slot['len']]
        # 检查与已赋值 slot 的交叉一致性
        for word in candidates:
            ok = True
            for (i, j), (pi, pj) in crossings.items():
                if i == slot_idx and j in assignment:
                    if word[pi] != assignment[j][pj]:
                        ok = False
                        break
            if ok:
                assignment[slot_idx] = word
                res = backtrack(slot_idx + 1, assignment)
                if res: return res
                del assignment[slot_idx]
        return None

    return backtrack(0, {})
```

更高效的写法用 **AC-3 + MRV (Minimum Remaining Values)** 约束传播，并维护每个 slot 的"候选词集合"，每赋值一次就传播缩减。

## 分布式工程层面

### 1. Result 缓存（高 hit rate）

很多 puzzle 来自共享报纸 / 杂志，**hash(grid + word_list) → cached_result**。新请求先查 Redis，hit 直接返回。

### 2. Job Queue 模式

- 用 Redis Stream / SQS / Kafka 作为持久化队列
- 队列里的 job 是 `{jobId, gridHash, priority, submittedAt}`
- Worker pull job → 求解 → 写 result store → ack

### 3. Worker 自动伸缩

- K8s HPA 按队列 depth 扩容
- 每 worker 一个 puzzle（CPU 密集，不要在 worker 内多线程）
- 失败重试：上限 3 次，仍失败入 dead-letter

### 4. 超时与降级

- 每 puzzle 设硬超时 5 min；超过就标记 `partial` 或 `failed`
- 用户可以取消任务：worker 定期检查 Redis 标志，发现 cancelled 立即停

### 5. GPU 加速？

对小 puzzle 没必要。对大 puzzle（千 × 千格）可以 GPU 跑 SAT solver 改写，但 ROI 低。优先用 CPU + 多 worker 并行不同 puzzle。

## 数据模型

```python
class Job:
    id: UUID
    user_id: UUID
    grid_hash: str
    state: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result_url: str | None    # S3 link 存大结果

class WordList:
    id: UUID
    name: str          # 'english-standard', 'nyt-dict'
    size: int
    storage_url: str   # S3
```

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 求解算法 | DFS + 约束传播 | SAT solver：通用但启动慢 |
| 任务队列 | Redis Stream（轻量） | Kafka：吞吐更高但复杂 |
| 缓存 | hash(input) → result | 没有缓存：浪费算力 |
| Worker 隔离 | 一 puzzle 一 worker | 多线程：GIL + 调度复杂 |

> [!key]
> 这题真正的考点不在 crossword 算法本身（面试官不会期待你 30 分钟内写完 AC-3），而在**任务调度 + 缓存 + 弹性扩展**。说出"hash 输入做去重"和"按 queue depth 扩 worker"是基本盘。

> [!pitfall]
> ❌ 把求解放在 API 进程内 —— API 直接 timeout；
> ❌ 不做幂等（同一 puzzle 多次提交跑多次）；
> ❌ Worker 任务无超时 —— 一个病态 puzzle 卡死整 worker；
> ❌ 用 Cassandra / Dynamo 存 job state —— 状态机更新需要强一致。

> [!followup]
> "如何支持 partial solution？" → worker 周期性把当前 best assignment 写到 Redis，前端可显示进度。"如何 A/B test 不同算法？" → API 层按 user_id 分桶，给不同 worker pool 打标。
