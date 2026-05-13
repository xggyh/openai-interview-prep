## 题目本质

设计 **Rate Limiter**：控制 API 请求速率，防止系统过载 + 公平资源分配。支持分布式（跨多台服务器追踪）、per-user / per-client / per-endpoint。

经典 SD 题。考点：**算法选择（token bucket / leaky bucket / sliding window） + 分布式协同（Redis）**。

## 需求拆解

**功能性：**
- 按 (key, action) 限速：key = user_id / API key / IP，action = endpoint
- 多维度：per-second / per-minute / per-day quota
- 超限返回 429 + Retry-After header
- 用户可看自己的 quota usage

**非功能性：**
- 100k+ QPS 总流量
- 限流决策延迟 < 1ms（不能阻塞 hot path）
- 99.99% 可用 (rate limiter 挂了不能拖垮上游)

## 限流算法选择

### 1. Token Bucket（推荐 ⭐）

桶容量 capacity，每秒补充 refill_rate 个 token。请求来到消耗一个 token；桶空了拒绝。

```python
class TokenBucket:
    def __init__(self, capacity, refill_per_sec):
        self.capacity = capacity
        self.refill = refill_per_sec
        self.tokens = capacity
        self.last_refill = time.time()

    def allow(self) -> bool:
        now = time.time()
        # 累积补充
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

**优点**：允许 burst（桶满时），平均速率 = refill_rate。

### 2. Leaky Bucket

桶里的请求按固定 leak rate 流出。请求来到塞进桶，桶满拒绝。

**优点**：output rate 完全 smooth；**缺点**：不允许 burst。

### 3. Fixed Window

每分钟（或秒）一个 counter，到了重置。请求来 +1，超过 limit 拒绝。

**问题**：window 边界 burst —— 用户在 0:59.9 + 1:00.1 内可发 2 * limit 个请求。

### 4. Sliding Window Log

存储每个请求的 timestamp，查询窗口内总数。准确但内存大（百万请求每条 timestamp）。

### 5. Sliding Window Counter（推荐 ⭐）

固定窗口 + 加权前一窗口。例：当前分钟过了 30 秒 → count = current_minute_count + previous_minute_count * 30/60。

**优点**：解决 fixed window burst 问题，内存 O(1)。

## 整体架构

```ascii
   API request
       │
       ▼
   ┌──────────────┐
   │  API Gateway │  ← 第一道防线
   │  (Envoy /    │     in-memory bucket
   │   nginx)     │
   └──────┬───────┘
          │ allow / 429
          ▼
   ┌──────────────┐
   │  Backend     │  ← 第二道（精细业务限流）
   │  Service     │     调用 Distributed Rate Limiter
   └──────┬───────┘
          │
          ▼
   ┌──────────────────┐
   │  Rate Limiter    │  Redis-backed token bucket
   │  Service         │
   │ (or in-proc lib  │
   │  with Redis)     │
   └──────────────────┘
```

## 分布式实现（Redis 共享 state）

多台 server 共享 quota → 状态存 Redis。

### Lua 脚本原子计算（推荐）

```lua
-- token_bucket.lua
-- KEYS[1] = bucket key, e.g. "rl:user:123:api:search"
-- ARGV = {capacity, refill_rate, now_ms, requested}
local key      = KEYS[1]
local cap      = tonumber(ARGV[1])
local refill   = tonumber(ARGV[2])
local now_ms   = tonumber(ARGV[3])
local req      = tonumber(ARGV[4])

local state    = redis.call('HMGET', key, 'tokens', 'last_ms')
local tokens   = tonumber(state[1]) or cap
local last_ms  = tonumber(state[2]) or now_ms

-- refill
local delta    = (now_ms - last_ms) / 1000 * refill
tokens         = math.min(cap, tokens + delta)

if tokens >= req then
  tokens = tokens - req
  redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
  redis.call('EXPIRE', key, 3600)
  return {1, tokens}      -- allowed, remaining
else
  redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
  redis.call('EXPIRE', key, 3600)
  return {0, tokens}      -- denied
end
```

Python 调用：

```python
script = redis.register_script(LUA_SCRIPT)
def allow(user_id, endpoint, capacity=100, refill=10, requested=1):
    key = f"rl:{user_id}:{endpoint}"
    now_ms = int(time.time() * 1000)
    allowed, remaining = script(keys=[key], args=[capacity, refill, now_ms, requested])
    return bool(allowed), remaining
```

**关键**：Lua 脚本在 Redis 单线程里原子执行，没有 race condition。

### 替代：固定窗口计数（最简单）

```python
def allow(user_id, endpoint, limit=100, window=60):
    bucket = int(time.time()) // window
    key = f"rl:{user_id}:{endpoint}:{bucket}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, window + 5)
    return count <= limit
```

简单但有 window 边界 burst 问题。

## 多层防御策略

| 层 | 算法 | 目的 |
|---|---|---|
| L1：edge (CDN) | IP-based fixed window | 防 DDoS |
| L2：API GW | Token bucket per-user/key | 业务 quota |
| L3：service-internal | Concurrency limit (semaphore) | 防慢调用拖垮 |
| L4：DB / 下游 | Connection pool + circuit breaker | 防雪崩 |

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 算法 | Sliding window 或 Token bucket | Fixed window：边界问题 |
| 状态 | Redis 共享 | Local：跨 server 不一致 |
| 原子性 | Lua script | Pipeline + WATCH：复杂 |
| 失效行为 | Fail open（Redis 挂了允许通过）+ alert | Fail closed：DoS 自己 |

## 关键技术细节

### 1. Sliding Window Counter 实现

```python
def sliding_window_allow(user_id, endpoint, limit=100, window_sec=60):
    now = time.time()
    cur_bucket = int(now // window_sec)
    prev_bucket = cur_bucket - 1
    cur_key = f"rl:{user_id}:{endpoint}:{cur_bucket}"
    prev_key = f"rl:{user_id}:{endpoint}:{prev_bucket}"
    
    pipe = redis.pipeline()
    pipe.incr(cur_key)
    pipe.expire(cur_key, window_sec * 2)
    pipe.get(prev_key)
    cur_count, _, prev_count = pipe.execute()
    prev_count = int(prev_count or 0)
    
    # 加权前一窗口
    elapsed_in_cur = now - cur_bucket * window_sec
    weight = (window_sec - elapsed_in_cur) / window_sec
    estimated = prev_count * weight + cur_count
    return estimated <= limit
```

### 2. Multi-dimensional Quota

```python
# 用户级 + 端点级 + IP 级同时检查
checks = [
    ('user', user_id, 1000, 60),       # 1000/min per user
    ('ip',   ip,      500,  60),       # 500/min per IP
    ('end',  f'{user_id}:{endpoint}', 100, 60),  # 100/min per user-endpoint
]
for kind, key, limit, window in checks:
    if not allow(kind, key, limit, window):
        return 429
```

### 3. 429 Response

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1700000000
```

让 client SDK 知道何时重试。

### 4. Whitelist / Premium 用户

用户表里存 `rate_tier`，limiter 配置按 tier 取值。

## 容量估算

- 100k QPS → 100k Redis 调用/s（限流决策）
- Redis 单实例可 100k+ ops/s；高峰用 cluster 模式分片
- Lua 脚本每次 ~0.5ms → 决策延迟可控

> [!key]
> 三大要点：(1) **Token bucket / Sliding window** 比 fixed window 更准确；(2) **Lua script** 原子操作避免 race；(3) **Multi-layer 防御**（CDN/GW/service/DB），rate limiter 不是唯一防线。

> [!pitfall]
> ❌ Local in-memory bucket 在分布式系统 —— quota 数 N 倍；
> ❌ Fixed window 不考虑边界 —— 用户可在 2 秒内打 2 倍 limit；
> ❌ Redis 不用 Lua 而是 `GET → INCR` 两步 —— race condition；
> ❌ Redis 挂了 fail-closed → 自己 DoS 自己；
> ❌ 没有 Retry-After header —— 客户端疯狂 retry。

> [!followup]
> "如何 graceful degrade Redis 挂掉？" → 降级到 local in-memory（不完美但比 fail-closed 好）；"如何动态调整 limit？" → 配置中心 push，rate limiter 周期读；"如何 cost-based limit？" → 不只是请求数，按 estimated cost 扣 token (e.g. LLM API 按 prompt+completion tokens)。
