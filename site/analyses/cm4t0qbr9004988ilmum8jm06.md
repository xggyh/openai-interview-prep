## 题目本质

设计 **Online Game Leaderboard**：百万玩家实时 ranking，按 score 排序。支持：top-N global、around-me、按 friends / country 过滤。

## 解法核心

**Redis Sorted Set (ZSET)** 是 leaderboard 标准方案：
- `ZADD lb score user_id` —— 写
- `ZREVRANGE lb 0 99 WITHSCORES` —— top 100
- `ZREVRANK lb user_id` —— 我的排名
- `ZREVRANGEBYSCORE lb +inf -inf` —— 范围查询

O(log N) per op，1M users 不到 1ms。

## 整体架构

```ascii
  Game Server
       │ score update
       ▼
  ┌──────────────┐
  │ Score Service│
  └──────┬───────┘
         │
   ┌─────┼──────────────┐
   ▼     ▼              ▼
  Redis  Redis      Redis 
  ZSET   ZSET       ZSET
  Global Country    Friends
  Lead.  Lead.      (per user)
         │              │
         ▼              ▼
   ┌───────────┐
   │ Postgres  │  source of truth, audit
   └───────────┘
```

## 关键技术

### 1. Multi-dimensional leaderboards

- Global: `lb:global`
- Per country: `lb:country:US`, `lb:country:JP`
- Per friend group: `lb:friends:{user_id}` —— pre-compute or compute on-the-fly with `ZINTERSTORE`

### 2. Time windows

- All-time: 永久 ZSET
- Weekly: `lb:weekly:2026W19`, expire after 2 weeks
- Daily: 同理

### 3. 大数据量分片

1B 用户 → 单 Redis 装不下。**Sharding by score range**：
- Shard 0: score [0, 100]
- Shard 1: score [101, 1000]
- ...

Query top-N from highest shard down。但 `ZREVRANK` 跨 shard 需算 cumulative offset。

**简化**：top-100 global 只查最高 shard 就够。其他 query 退到 DB。

### 4. Write amplification

每 user 同时写 global + country + weekly + daily ZSET = 4 writes per update。OK，Redis pipeline 一次发出。

### 5. Around-me

`ZREVRANGEBYRANK lb (my_rank - 10) (my_rank + 10)`。需先 ZREVRANK 取 rank。

### 6. Anti-cheat

新 score 写入前过 fraud check：
- Rate limit per user (每秒不能 +1000 score)
- ML model on suspicious patterns
- Server-side validation of game events

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Storage | Redis ZSET | DB ORDER BY：每查 O(N) |
| Sharding | Score range | Hash by user_id：rank query 难 |
| Friends LB | ZINTERSTORE | 全 DB join：慢 |
| Time window | 多 ZSET key + TTL | Single + filter：慢 |
| Persistence | Redis AOF + Postgres backup | Pure Redis：crash 丢数据 |

## 容量估算

- 1M concurrent player × 1 update/min = 17k QPS write
- Redis ZADD ~50k QPS per node → 1 node 撑得住
- Top-100 query: O(log N) = ~20μs → CDN cache 5s 99% hit

## 易错点

> [!pitfall]
> ❌ DB ORDER BY 实时计算 —— TLE；
> ❌ 不分 time window —— 老玩家 dominate weekly；
> ❌ Friend leaderboard 实时 compute —— 慢；预算或周期 refresh；
> ❌ 没 anti-cheat —— 第一周 hack score 上去；
> ❌ Tie 处理（同 score）：用 secondary key (timestamp) 保稳定。

> [!key]
> Redis ZSET 是 leaderboard 经典且最优解。同 score tie-break 用 (-score, timestamp) tuple。多维度分多 ZSET 不要 over-engineer。

> [!followup]
> "如何 percentile rank（"你超过 X% 玩家"）？" → `ZREVRANK / ZCARD`；"如何 historical "我去年这天排名"？" → daily snapshot to S3；"实时排行榜推送（rank 变化通知）？" → pub/sub on score update。
