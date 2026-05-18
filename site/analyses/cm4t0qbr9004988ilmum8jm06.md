## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Leaderboard / Ranking** | 按分数排序的列表 | 班级成绩榜 |
| **Top-N global** | 全游戏排名前 N | 全国高考排名 |
| **Around-me** | 我前后 ±50 名是谁 | "你在班里第 12 名，11/13/14 名是 X/Y/Z" |
| **Sorted Set (ZSET)** | Redis 的"按 score 排序的 set"，O(log N) 操作 | 自动排好的排行榜 |
| **Skip List** | ZSET 底层实现，O(log N) 插入/查询/排名 | 多层索引的链表 |
| **Percentile rank** | 你超过百分之几玩家 | "你比 85% 玩家强" |
| **Sharding by user / by score** | 按用户分库 vs 按分数分库 | 按姓氏分 vs 按成绩分 |
| **CDN edge caching** | 静态排行榜缓存到全球边缘 | 全球便利店都备着今日热销榜 |
| **Real-time vs near-real-time** | 即时更新 vs 几秒延迟 | 直播比分 vs 5 分钟一次刷新 |
| **Idempotency** | 同操作重复执行结果不变 | 重新提交分数不会重复加 |

---

## 1. 题目本质

**Online Game Leaderboard** = 百万玩家实时 ranking，按 score 排序，支持多种查询：
- **Top-N global**（前 100 名）
- **Around-me**（我前后 50 名）
- **Filtered**（按好友 / 国家 / 时段过滤）
- **Score 更新实时反映**

**典型产品**：
- **Steam global leaderboard** —— 跨游戏的全球榜
- **PUBG / Fortnite seasonal rankings** —— 赛季榜
- **Strava** —— 跑步 / 骑行排名
- **Pokemon GO Battle League** —— 实时段位
- **LeetCode contest ranking**

**为什么这是 STAFF 题（虽然只 1 ppl 报告）**：

考的是**Redis ZSET 玩到极致 + scale 到 1B 玩家**。难点：

1. **Real-time updates** at 100k+ score updates/sec
2. **Around-me query** at p99 < 50 ms
3. **Multiple filtered leaderboards** (global / friends / country / weekly)
4. **Hot range** — 大家都看 top 100，热点流量
5. **Score 异常**（作弊）detection

考的是**正确选数据结构 + 知道 Redis 极限在哪**。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `UpdateScore(user_id, score, board_id)` | 更新玩家分数 |
| `GetTopN(board_id, n) -> player[]` | 前 N |
| `GetAroundMe(board_id, user_id, range) -> player[]` | 我前后 ±range |
| `GetRank(board_id, user_id) -> rank` | 我第几名 |
| `GetByFriends(user_id, friend_list) -> player[]` | 朋友间排名 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **更新延迟** | < 100 ms (score 更新到榜单生效) |
| **查询 latency** | p99 < 50 ms |
| **Scale** | 1B players × 10 boards = 10B player-board entries |
| **Throughput** | 100k score updates/sec sustained, 500k peak |
| **Read** | 1M reads/sec (top-N / around-me) |
| **Hot path** | 90% read 在 top 100 / top 1000 |

---

## 3. 容量估算

- **Players**: 1B
- **Boards**: 10 (global / weekly / friends / country × 5)
- **Total entries**: 10B (player + board + score)
- **Each entry**: 50 B (user_id 8 + score 8 + meta 30) → **500 GB** total
- **Memory feasibility**: 500 GB ÷ 256 GB/node = 2 nodes → 单 Redis cluster 能装！但要分 shard。

**Read QPS**: 1M, **mostly top-100** → CDN edge cache 命中 ≥ 95% → real backend QPS ~50k
**Write QPS**: 100k sustained, 500k peak

---

## 4. 关键设计 — 用 Redis ZSET

### 4.1 Why ZSET

Redis ZSET 完美匹配 leaderboard 需求：

| 操作 | Redis 命令 | 复杂度 |
|---|---|---|
| 更新分数 | `ZADD board user_id score` | O(log N) |
| 取 top-N | `ZREVRANGE board 0 N-1` | O(log N + N) |
| 取 around-me | `ZREVRANK + ZREVRANGE` | O(log N + range) |
| 取 rank | `ZREVRANK board user_id` | O(log N) |
| 移除 | `ZREM board user_id` | O(log N) |

**底层是 skip list + hash table**，所有操作 sub-millisecond。

### 4.2 Single Redis 限制

- 单 Redis instance 内存 ~256 GB → 装 5B entries
- 单 Redis CPU ~100k QPS → 不够 peak

→ **Sharding**

---

## 5. 高层架构

### Step 1: 单 Redis 单 board

```
Client → API → Redis ZSET (one board)
```

够用如果 board 小（< 10M entries 都 OK）。

### Step 2: Multiple boards

每个 board 是独立 ZSET：

```
ZADD global_2026 user_id score
ZADD weekly_2026_W19 user_id score
ZADD friends_user_42 user_id score (each user has own friend board)
```

### Step 3: Sharding 大 board

**1B players in 1 global board** → 单 Redis 装不下。**Sharding by score range**：

```
shard_0: rank 1 - 100k       (low scores)
shard_1: rank 100k - 1M
shard_2: rank 1M - 10M
...
shard_N: rank 100M - 1B      (top scores)
```

**Read top-N**: 直接 `shard_N` （最高分 shard） `ZREVRANGE 0 N`
**Read around-me**: 先 `ZSCORE` 拿 score → 知道在哪个 shard → ZREVRANGE around
**Write**: 知道当前 user 的 shard，update 时如果 score 越过 shard 边界 → 移动到对应 shard

**Trade-off**: top-N 极快（hot shard），but score 边界附近的 user 频繁迁移。

### Step 4: 缓存 hot path

- Top 100 是 99% 查询打中的范围
- 直接 CDN edge cache，TTL = 10 s
- 后端实际 read 减少 95%

### Step 5: Write path

```
Client → API → Kafka (score update event)
                ↓
          Score Processor (cluster)
                ↓
          Redis ZADD (with optimistic locking)
                ↓
          Cache invalidate (Top-100 TTL refresh)
```

**Why Kafka**：peak 500k QPS 直接打 Redis 会过载，Kafka 削峰。

### Step 6: Multi-board update fan-out

User 玩一场 → 更新 multiple boards (global, weekly, friends, country):

```
Score event → Score Processor
  → ZADD global
  → ZADD weekly_current_week
  → ZADD friends boards of all friends
  → ZADD country_XX
```

**Friends fan-out**：如果用户 1000 个朋友，每场比赛要写 1000 个 ZADD → 写放大严重。**Pull model**：friends leaderboard 用 query time aggregation（不写每个 friend 的 board）。

---

## 6. 组件深挖

### Deep Dive 1: Around-Me Query

**Naive**: `ZREVRANK(user) → ZREVRANGE(rank - range, rank + range)` = 2 个操作。

**优化**:
- 单次 `ZRANGEBYLEX` if score has unique tie-breaker
- 客户端 batch query 减少 round trip
- Cache "user → rank" with TTL 1 sec (rank 变化不快)

### Deep Dive 2: Friends Leaderboard

**写时 fan-out (1000 friend boards)**：写放大 1000×，500k × 1000 = 5亿 QPS 不可行。

**读时 aggregation**：
```python
def friends_leaderboard(user, friend_list):
    scores = ZMSCORE("global", friend_list)  # batch 拿 friend 们的 score
    return sorted(zip(friend_list, scores), key=lambda x: -x[1])
```

如果 friend list < 1000，单次 Redis call 完成，< 10 ms。

### Deep Dive 3: Sharding by Score

**Score 边界附近 user 频繁迁移**：用户 score 在 99999 → 100001（shard 边界），如何避免抖动？

**Solution**:
1. **Overlap shards**：shard_i 包括 score 90000-110000，shard_i+1 包括 100000-200000 → 写双份，读时只读"主 shard"
2. **Hysteresis**：score 上涨到 100100 才升 shard，跌回 99900 才降 shard → 防 churn
3. **Periodic rebalance**：每天 batch 跑一次正确分 shard，不实时迁移

### Deep Dive 4: 实时性 trade-off

**Score 更新 → 榜单可见**多久？

| 方案 | 延迟 | 复杂度 |
|---|---|---|
| 同步写 ZSET | < 10 ms | 简单，但 peak 写量大时 Redis 过载 |
| Kafka 缓冲 + worker 处理 | 50-500 ms | 削峰，可扩展 |
| Batch every 10s | 10s | 极简，但实时性差 |

**STAFF 答**：Kafka 缓冲，p99 < 100 ms 用户感知不到。

### Deep Dive 5: Anti-Cheat

**典型 cheat**：发 fake 高分 → 直接占榜首。

**Defense layers**:
1. **Server-side validation**：score 必须 server 计算（不要信 client）
2. **Sanity check**：单次比赛分数有 max (e.g., 不超过 100000)
3. **Rate limit**：单 user score update / minute 有 cap
4. **Anomaly detection**：score 突然 10× 增长 → flag for review
5. **Shadowban**：被检测 cheater 写入隔离 board（cheater 看到自己排名，但全榜不显示）

### Deep Dive 6: Seasonal / Weekly Boards

**Weekly board**: 7 天 reset 一次。

实现:
- ZSET key 包含 week ID: `weekly_2026_W19`
- 写时同时写 current week
- Sunday midnight: 创建新 key `weekly_2026_W20`
- 老 key 保留 30 天用于历史查询，之后删除

**Pre-creation**: 提前创建下周 key 防 midnight spike。

### Deep Dive 7: Pagination

Top-100 → Top-1000 → ... 用户翻页：

```
Page 1: ZREVRANGE 0 99
Page 2: ZREVRANGE 100 199
...
```

**问题**：score 变化时翻页可能漏 / 重。

**Solution**:
- 用 `score + user_id` as cursor (not offset)
- Page 2: `ZREVRANGEBYSCORE < cursor LIMIT 100`
- 这种是 stable pagination，新分数加入不影响已加载

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：board 数量、用户量、real-time 要求 |
| 5-10min | 容量：1B players × 10 boards = 500 GB, 100k write QPS |
| 10-15min | 数据结构选择 Redis ZSET，复杂度分析 |
| 15-25min | 高层架构：单 ZSET → 多 board → sharding → Kafka 削峰 |
| 25-40min | Deep dives: friends leaderboard / around-me / sharding boundary / anti-cheat |
| 40-45min | seasonal reset / pagination / monitoring |

---

## 8. 样板讲解稿

> 这道题核心选择是数据结构 —— **Redis ZSET (sorted set, skip list 实现)** 几乎是完美匹配：
> - O(log N) 更新分数
> - O(log N + N) top-N
> - O(log N) rank lookup
>
> **架构**：
> 1. Score update 走 Kafka 削峰（peak 500k QPS）
> 2. Worker 写 Redis ZSET (`ZADD board user score`)
> 3. **Top-N 缓存在 CDN edge**, TTL 10s, 命中率 95%+
> 4. 多 board 都是独立 ZSET (global / weekly / country / friends)
>
> **关键 trade-off**：
> - 1B player 单 ZSET 装不下 → **sharding by score range** (shard 边界用 hysteresis 防 churn)
> - Friends leaderboard 1000 friend 写放大 → **pull model**: query 时 `ZMSCORE` batch
> - Real-time 要求 < 100 ms → Kafka + 立即 process
>
> **Anti-cheat**：server-side score validation + rate limit + anomaly detect + shadowban。
>
> 数字: 1B players × 10 boards = 500 GB, 100k write QPS sustained.

---

## 9. Follow-up Q&A

### Q1: "Around-me 需要 ±50, 怎么实现？"

**A**：`rank = ZREVRANK(user)` → `ZREVRANGE rank-50 rank+50`。两个操作，< 5 ms。如果 rank 频繁查，cache user→rank with TTL 1s。

### Q2: "1000 friends, 每场比赛都要更新这 1000 个 friend 的 friends board？"

**A**：写放大太大。改 **pull model**：friends board 不主动维护，query 时用 `ZMSCORE global, friend_list` batch 拿分数 + sort，< 10 ms 完成。

### Q3: "Top-100 是全 server 都在查，热点严重，Redis 怎么扛？"

**A**：三层兜底：
1. **Local cache** in API server (1s TTL)
2. **CDN edge** cache global top-100 (10s TTL)
3. **Read replica** of Redis: top-100 read 打到 5 个 replica 分摊

90% 流量被 CDN 兜住。

### Q4: "Sharding by score 时用户 score 跳变 shard，怎么办？"

**A**：3 个机制：
1. **Hysteresis**: 上涨进新 shard 100100 阈值，下降出去 99900 阈值，防 churn
2. **Overlap range**: 边界 shard 略有重叠，写双份
3. **Periodic clean-up**: 后台扫描 misplaced entries，迁回正确 shard

### Q5: "Score 更新 throughput 突然 5x，Redis 扛不住怎么办？"

**A**：
1. **Kafka 削峰**：write side 永远入 Kafka，不直接打 Redis
2. **Scale out Redis shards**：consistent hashing 加机器
3. **Batch writes**：worker 每 100ms flush 一批 ZADD (Redis pipeline)，吞吐 5-10×

### Q6: "Weekly board 怎么 reset？"

**A**：
- Key 用 week ID: `weekly_2026_W19`
- 周日 midnight 后写入 `weekly_2026_W20`
- 老 key 不删，保留 30 天历史
- 提前 1 天 pre-create 新 key 防 midnight spike

### Q7: "用户 score 是 1000.500000，怎么 break tie？"

**A**：ZSET score 是 double，相同 score 内按 lex order of member (user_id)。可以用 `score = real_score * 1e6 + (max_user_id - user_id)`，把"先达成 score 者排前"编进 score。

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **不知道 ZSET 是关键** → 用 SQL ORDER BY 之类，O(N log N) per query
2. **Friends fan-out 写时** → 写放大 1000×
3. **没有 anti-cheat** → score 可伪造
4. **Top-100 不 cache** → Redis 顶不住
5. **Sharding by user_id 而非 by score** → top-N 要 scatter-gather 慢
6. **Weekly reset 无 pre-create** → 0 点 spike
7. **没说 server-side score 计算** → 暴露不懂安全

### ✅ 加分项

1. **Skip list 复杂度 O(log N)** 主动提
2. **Sharding by score** + hysteresis
3. **Pull model** for friends leaderboard
4. **Stable pagination** via cursor
5. **Anti-cheat layered defense**
6. **ZMSCORE batch** 减少 round trip
7. **CDN edge cache for top-100**
8. **Shadowban for detected cheaters**

> [!key] STAFF vs SENIOR：SENIOR 答 ZSET；STAFF 答 ZSET + sharding by score + pull for friends + multi-layer cache + anti-cheat 完整 stack。

---

## 11. Cheat Sheet

```
核心: Redis ZSET (skip list)
  ZADD board user_id score          O(log N)
  ZREVRANGE board 0 N-1             O(log N + N)
  ZREVRANK board user_id            O(log N)
  ZMSCORE board user_list           batch

架构:
  Client → API → Kafka → Score Processor → Redis ZSET
                                        ↘ Cache invalidate

Sharding:
  by score range (with hysteresis)
  not by user (会 scatter-gather)

Cache:
  Top-100 → CDN edge (10s TTL, 95% hit)
  user→rank → API server local (1s TTL)

Friends leaderboard:
  PULL model (no fan-out write)
  ZMSCORE batch when queried

Weekly reset:
  Key includes week_id
  Pre-create day before midnight

Anti-cheat:
  Server-side score
  Rate limit / minute
  Anomaly detect (10× spike)
  Shadowban

数字:
  1B players × 10 boards = 500 GB
  100k writes/sec sustained, 500k peak
  1M reads/sec, 95% from CDN cache
  p99 < 50 ms
```
