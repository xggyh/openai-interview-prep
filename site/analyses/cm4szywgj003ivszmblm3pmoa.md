## 题目本质

设计一个 Chess.com 级别的实时在线棋类对战平台。考点不在"国际象棋规则"本身（面试官不会指望你 30 分钟写完棋规则引擎），而在**实时双玩家状态同步 + 走子合法性的权威服务端校验 + 高并发匹配 + 排行榜**。

## 需求拆解

**功能性：**
- 用户注册/登录，可发起对局或加入快速匹配
- 双人实时对战（同步走子、聊天、观战）
- 走子合法性校验（服务端为权威，客户端不可信）
- 悔棋 / 认输 / 和棋
- 走子历史 + 棋谱回放
- ELO 排行榜

**非功能性：**
- 实时（走子端到端 < 100 ms）
- 1M DAU 量级，峰值同时进行 50k 局对战
- 99.9% 可用，断线重连不丢局

**容量估算：**
- 平均一局走 80 步，5 分钟 → 50k 并发 → 走子写入 QPS ≈ 50k × 80 / (5 × 60) ≈ 13k QPS
- 每个走子事件 ≤ 200 B → 写带宽 ≈ 2.6 MB/s

## 整体架构

```ascii
                         ┌──────────────┐
   Client A ─── WSS ───▶ │   API GW     │ ◀─── WSS ─── Client B
                         │  (sticky)    │
                         └──────┬───────┘
                                │
                  ┌─────────────┼────────────┐
                  ▼             ▼            ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │ Game     │  │Matchmkr  │  │ Auth /   │
            │ Server   │  │ Service  │  │ Profile  │
            │ (sharded)│  │          │  │ Service  │
            └────┬─────┘  └────┬─────┘  └────┬─────┘
                 │             │             │
                 ▼             ▼             ▼
            ┌─────────┐   ┌─────────┐   ┌─────────┐
            │ Redis   │   │ Queue   │   │ Postgres│
            │ (live   │   │ (Kafka) │   │ (users) │
            │  game   │   │         │   │         │
            │ state)  │   │         │   │         │
            └────┬────┘   └─────────┘   └─────────┘
                 │
                 ▼ (game end)
            ┌─────────┐
            │ MongoDB │  ◀──  move history, replay
            │ (games) │
            └─────────┘
                 │
                 ▼ (rating event)
            ┌──────────┐
            │ Ranking  │  ELO 计算 + Redis SortedSet
            │ Worker   │
            └──────────┘
```

## 核心组件设计

### 1. Game Server（最核心）

- **Sticky session by gameId**：同一局的两个玩家通过 gameId hash 路由到同一台 Game Server（一致性哈希）。这样**走子事件只在单机内存里调度**，无需跨节点协调。
- **走子合法性校验在服务端**：客户端发 `{"from":"e2","to":"e4"}`，服务端把状态机推进一步，校验合法（包括将军、王车易位、过路兵、升变等所有规则）。
- **内存中保存当前对局状态**（FEN string + 走子列表），Redis 作为热备（每走一步异步写入，用于故障恢复 + 观战快照）。
- **超时计时器**：每个玩家剩余时间存在内存，过期触发 `timeout` 事件判定胜负。

### 2. Matchmaking

- 玩家进入队列：`Q_rating_bucket` → Redis ZADD by waiting time
- 配对 worker 每秒扫描相邻 rating bucket，配对 → 创建 gameId → 推回两个玩家 WSS 通道
- ELO 接近度先严格匹配，每过 5 秒放宽 ±25

### 3. WSS 协议

```python
# server → client
{"type":"move", "from":"e2","to":"e4","san":"e4","clock":{"w":297000,"b":300000}}
{"type":"end","reason":"checkmate","winner":"w"}
{"type":"chat","from":"playerA","text":"GG"}

# client → server
{"type":"move","from":"e2","to":"e4","clientSeq":42}
{"type":"resign"}
{"type":"draw_offer"}
```

`clientSeq` 用于 dedup + 顺序：服务端只接受 `clientSeq == lastClientSeq + 1`。

### 4. 悔棋（takeback）

服务端保存所有走子的 SAN 历史 + 每步的 FEN 快照（或仅保存初始 FEN + moves，需要时回放）。悔棋请求需要对手同意；服务端把状态机倒回到上一步，广播新状态。

### 5. 排行榜

走子事件 ≠ 排行榜更新。**对局结束**事件写入 Kafka，Ranking Worker 消费：
- 计算 ELO 增减（标准 K=32 公式）
- 更新 Redis `ZSET leaderboard` 用于实时查询
- 同步落库 Postgres 做长期持久化

## 关键技术决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 实时协议 | WebSocket / WSS | 双向 push，低延迟 |
| 路由 | 一致性哈希 by gameId | 同局两端到达同台机器，避免分布式状态同步 |
| 实时状态 | 内存 + Redis 异步 | 内存低延迟，Redis 做故障恢复源 |
| 历史/回放 | MongoDB（按 gameId 文档） | 走子列表天然适合文档存储 |
| 排行榜 | Redis SortedSet + Postgres | 实时排名 + 长期审计 |
| 防作弊 | 走子合法性强校验 + 引擎反作弊（Stockfish 比对走法相似度） | 走子合法性纯规则可校验，外挂检测靠 ML |

## API 设计

```python
# REST
POST /games          # 创建对局（vs 好友邀请）
GET  /games/{id}     # 获取对局元信息 + 当前状态
GET  /games/{id}/pgn # 下载棋谱
POST /matchmaking    # 进入快速匹配队列

# WebSocket
ws://game.example.com/ws?gameId=xxx&token=yyy
```

> [!key]
> 这题在 OpenAI 被报告 58 次，是最近最热的 SD 题。OpenAI 面试官最爱追问：(1) 如何保证两端看到的棋盘状态一致？答：服务端权威 + 全局递增 moveSeq；(2) 一台 Game Server 挂了怎么办？答：Redis 持久化 + 重连时拉 FEN 重建；(3) 走子合法性的算法复杂度？答：O(1) per move（位棋盘 bitboard）。

> [!pitfall]
> 不要把走子合法性放客户端 —— 1 分钟内会被作弊；不要用 HTTP 长轮询替代 WSS —— 延迟会被打爆；不要把所有对局放在一个 DB 表 —— 写热点。

> [!followup]
> 常见追问：观战如何做？答：观战者订阅 `gameId/spectator` channel，Game Server 走完每步多 fan-out 一份。观战延迟可放宽到 1-2 秒。
