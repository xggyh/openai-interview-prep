## 题目本质

设计 **Webhook Callback System**：应用注册 callback URL → 当特定事件发生 → 系统**异步 POST 给该 URL**。代表：GitHub Webhooks、Stripe Webhooks、Slack 事件订阅。

OpenAI 报告 10 次，Mid-level-Staff。考点：**at-least-once delivery + retry with backoff + dead letter + 限流**。

## 需求拆解

**功能性：**
- 用户注册：`POST /webhooks { url, events: [...] }` → 返回 webhook_id + secret
- 发送：事件发生时系统找匹配的 webhook → HTTP POST event 到 user URL
- 重试：用户 endpoint 不可达 / 5xx → 退避重试 N 次
- 签名验证：POST 含 `X-Signature` 头，用户用 secret 验证
- Dashboard：用户看 delivery history、retry status

**非功能性：**
- 1M events/s 峰值
- delivery 平均延迟 < 5s
- 重试期间 endpoint 恢复后能继续投递
- at-least-once（接受偶尔重复，用户做幂等）

## 整体架构

```ascii
                 Internal services
                       │
                       ▼ event published
                ┌──────────────┐
                │   Event Bus  │  Kafka topic
                │   (Kafka)    │
                └──────┬───────┘
                       │
                       ▼ event router
                ┌──────────────────┐
                │ Webhook Matcher  │  → 查 webhook registry，
                │                  │     按事件类型找匹配 sub
                └──────┬───────────┘
                       │
                       ▼ produce delivery job
                ┌──────────────┐
                │ Delivery     │  Kafka topic: deliveries
                │ Queue        │  partition by webhook_id
                └──────┬───────┘
                       │
                       ▼ pull
                ┌──────────────────┐
                │ Delivery Worker  │  HTTP POST to user URL
                │ (fleet)          │
                └──┬───────────┬───┘
                   │           │
              success         failure → retry
                   │           ▼
                   │      ┌──────────────┐
                   │      │ Retry Queue  │ delay queue, exp backoff
                   │      │ (Redis ZSET) │
                   │      └──┬───────────┘
                   │         │
                   │         ▼ when due → re-enqueue to Delivery Queue
                   │         │
                   ▼         ▼
            ┌──────────────────┐
            │ Delivery Log DB  │  per-attempt log
            │ (Cassandra)      │
            └──────────────────┘
```

## 核心组件设计

### 1. Webhook Registry

```sql
CREATE TABLE webhooks (
  id           UUID PRIMARY KEY,
  user_id      UUID,
  url          TEXT,
  secret       TEXT,                    -- HMAC signing key
  events       TEXT[],                  -- subscribed event types
  status       TEXT,                    -- active / paused / failed
  created_at   TIMESTAMPTZ,
  last_success TIMESTAMPTZ,
  failure_count INT                     -- consecutive 失败计数
);
CREATE INDEX idx_events ON webhooks USING GIN (events);
```

### 2. Webhook Matcher

事件发布时按 `event.type` 查 webhooks：`SELECT * WHERE 'order.created' = ANY(events)`，按结果 fanout 写 delivery queue。

**优化**：Matcher 内存里缓存 `event_type → list[webhook_id]`，几分钟刷新一次。注册/更新通过 CDC 流推送 invalidation。

### 3. Delivery Worker（核心）

```python
async def deliver(delivery_job):
    webhook = await get_webhook(delivery_job.webhook_id)
    if webhook.status != 'active':
        return  # paused / failed，丢弃

    payload = delivery_job.event_payload
    body = json.dumps(payload)
    sig = hmac.new(webhook.secret.encode(), body.encode(), 'sha256').hexdigest()
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Id': str(webhook.id),
        'X-Event-Type': delivery_job.event_type,
        'X-Signature': f'sha256={sig}',
        'X-Delivery-Id': str(delivery_job.id),
        'X-Attempt': str(delivery_job.attempt),
    }
    try:
        async with aiohttp.ClientSession(timeout=15) as sess:
            async with sess.post(webhook.url, data=body, headers=headers) as resp:
                ok = 200 <= resp.status < 300
                await log_attempt(delivery_job, resp.status, ok)
                if ok:
                    await mark_success(webhook)
                else:
                    await schedule_retry(delivery_job)
    except (TimeoutError, ConnectionError) as e:
        await log_attempt(delivery_job, status=0, ok=False, error=str(e))
        await schedule_retry(delivery_job)
```

### 4. 重试策略（指数退避 + jitter）

```python
RETRY_DELAYS = [
    30,        # 30s
    120,       # 2min
    900,       # 15min
    3600,      # 1h
    14400,     # 4h
    43200,     # 12h
    86400,     # 24h
    # max 7 attempts -> total ~42h
]

def schedule_retry(job):
    if job.attempt >= len(RETRY_DELAYS):
        # 永久失败，搬到 dead letter，标记 webhook failed
        await dead_letter(job)
        await pause_webhook(job.webhook_id)
        await notify_user(job.webhook_id, "Your webhook has been disabled after 7 failed deliveries")
        return
    delay = RETRY_DELAYS[job.attempt] + random.uniform(-5, 5)  # jitter
    redis.zadd('retry_queue', {job.id: time.time() + delay})
    job.attempt += 1
```

### 5. Retry Queue（Redis ZSET）

`ZADD retry_queue {due_timestamp} {delivery_id}` —— 按到期时间排序。

后台 retry scheduler：`ZRANGEBYSCORE retry_queue -inf NOW` → 到期 job 取出来 → 入 Delivery Queue 重投。

### 6. 限速保护

- 单用户 webhook 每秒并发上限（防止用户 endpoint 被打挂）
- Worker 池内部 per-host concurrency limit（同一 host 最多 N 个并发请求，否则慢 host 拖累整个 fleet）

### 7. 签名验证

```python
# 在用户侧的代码 (server 期望 user 这样验证):
expected = hmac.new(secret.encode(), request.body, 'sha256').hexdigest()
provided = request.headers['X-Signature'].split('=')[1]
if not hmac.compare_digest(expected, provided):
    return 401   # reject
```

防止伪造请求 + 防 replay（可以加 timestamp + 5min 有效期）。

### 8. Delivery Log

每次 attempt 记录：

```sql
CREATE TABLE delivery_attempts (
  id            UUID,
  webhook_id    UUID,
  event_id      UUID,
  attempt       INT,
  http_status   INT,
  response_body TEXT,
  duration_ms   INT,
  ok            BOOLEAN,
  attempted_at  TIMESTAMPTZ,
  PRIMARY KEY (webhook_id, attempted_at, id)
)
```

按 webhook_id partition，按时间 DESC clustering → 查询用户某 webhook 的 history 飞快。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 投递语义 | at-least-once（用户做幂等） | exactly-once：分布式不可能 |
| 重试 | 指数退避 + jitter | 固定 interval：火灾恢复时打挂用户 |
| 失败处理 | 7 次后 pause webhook | 无限重试：垃圾占资源 |
| 队列 | Kafka delivery + Redis retry | 单 Kafka：retry delay 不易做 |
| 限速 | per-host concurrency | 单全局限速：慢 host 拖累 |

## 关键技术细节

- **Idempotency-Key**：每条 delivery 唯一 ID，用户用此去重（at-least-once 意味着可能重复投递）
- **Timeout 15s**：用户 endpoint 处理时间上限，超过认为失败重试
- **Webhook URL 白名单**：禁止指向 internal IP（127.0.0.1, 10.x, 172.16.x, 169.254.x），防 SSRF
- **TLS only**：拒绝 http://，要求 https://
- **Cancellation**：用户 disable webhook → 立即停止后续重试（worker 拉前查 webhook.status）

> [!key]
> 三大要点：(1) **at-least-once + 用户幂等**（Idempotency-Key）；(2) **指数退避 + Redis ZSET 做 delay queue**；(3) **HMAC 签名验证 + SSRF 防御**。

> [!pitfall]
> ❌ Sync delivery（请求来时同步 POST）—— 服务被慢 endpoint 拖垮；
> ❌ Retry 固定间隔 —— 集群恢复时所有 retry 同时打挂用户；
> ❌ 不限制 webhook URL —— SSRF 攻击内网；
> ❌ 不签名 —— 用户没法验真伪；
> ❌ Worker 单 host 无并发限制 —— 慢用户占用所有 worker；
> ❌ Delivery log 写每条 row 同步 —— I/O 瓶颈。

> [!followup]
> "如何保证 event 顺序？" → 同 webhook 同 entity 的 events 路由到同 partition（按 webhook_id + entity_id hash）；"如何处理百万订阅者？" → fan-out 改为 pull 模型（消费者订阅 Kafka，自己拉）；"如何审计 / replay？" → 持久化原始 event payload，admin 可手动 retry。
