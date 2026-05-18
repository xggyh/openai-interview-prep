## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Realtime PvP** | 实时玩家对战 | 网球场两人对打 |
| **Authoritative server** | 服务端是"真理"，client 输入要 server 验证 | 球场裁判说了算 |
| **Move validation** | 走子合法性检查 (国王不能走 2 格之类) | 裁判判球出界 |
| **Game state** | 棋盘当前状态 (FEN 字符串通常) | 棋谱的快照 |
| **WebSocket** | 双工长连接，server 主动推 | 不挂的电话 |
| **Matchmaking** | 给 user 找势均力敌对手 | 牵线相亲 |
| **Elo / Glicko-2** | 棋手积分系统 | 综合实力评估 |
| **Time control** | 比赛限时 (e.g., 5+3 = 5 min + 3s/move) | 象棋钟 |
| **Premove** | 提前走下一步，对手走完立即执行 | 闪电战预判 |
| **Spectator mode** | 看比赛的观众 | 棋赛旁观者 |
| **Engine / Bot** | 电脑棋手 (Stockfish 之类) | 对弈电脑 |
| **Replay / Game replay** | 回放走过的棋 | 比赛录像 |
| **Reconnection** | 断线重连恢复 game | 中场休息后回来 |

---

## 1. 题目本质

**Online Chess Platform** = chess.com / lichess 级实时在线棋类对战。

**注意**：面试不会让你 30 分钟实现完整国际象棋规则引擎。重点在**实时双玩家状态同步 + 服务端权威走子校验 + 高并发匹配 + 排行榜**。

**典型产品**：
- **chess.com** —— 1 亿+ 注册，5k 同时在线
- **lichess** —— 开源，简洁 UI，~10k peak
- **Chess24 / playok**
- **Pokemon Showdown** —— 类似 PvP turn-based 架构

**为什么这是 STAFF 题**：

考的是 **realtime PvP architecture**（适用于象棋、围棋、扑克、跳棋等多种 turn-based game）：

1. **Authoritative game state**：server 是 source of truth
2. **WebSocket 双玩家同步**：低延迟，互不见对方
3. **Matchmaking**：Elo 接近的玩家配对
4. **Spectator** at scale：1 局 1M 观众怎么 broadcast
5. **Reconnection / cheating prevention**

考 STAFF 关键：**server-authoritative + low-latency state sync** 的经典 PvP 模式。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `JoinMatchmaking(user, time_control, rating)` | 找对手 |
| `MakeMove(game_id, from, to)` | 走子 |
| `GetGameState(game_id) -> state` | 取当前状态 |
| `Resign(game_id)` | 认输 |
| `OfferDraw / AcceptDraw` | 求和 |
| `Spectate(game_id)` | 观战 |
| `GetRating(user) -> elo` | 查积分 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Move latency** | < 100 ms (move → opponent sees) |
| **Matchmaking** | < 5 s wait for active player |
| **Concurrent games** | 50k concurrent at peak |
| **Concurrent users** | 100k online |
| **Spectator** | up to 100k per game (championship) |
| **Game history** | 1B+ games, immutable |
| **Anti-cheat** | detect engine assist + colluders |

---

## 3. 容量估算

- 50k concurrent games × 2 players = 100k WebSocket connections + spectators
- Avg move rate: 1 move / 3 sec / game → 50k × 0.33 = **17k moves/sec sustained**, peak 50k
- Storage: 1B games × 100 KB (PGN + meta) = **100 TB** game history
- Matchmaking: 100k waiting users, 10k matches/sec at peak

---

## 4. 关键设计：Server-Authoritative

**Why 必须 server-authoritative**:

- Client can be hacked → 不能 trust client say "I moved knight to e4"
- Cheat prevention：server validates each move
- Time control：server is timer source of truth

**Architecture**:
```
Player A ─WebSocket─→ Game Server ─WebSocket─→ Player B
                          ↓
                     Validate move
                          ↓
                     Apply to state
                          ↓
                     Broadcast new state
```

---

## 5. 高层架构

```
┌─────────────────────────────────┐
│  Player Devices (browser/mobile) │
└─────────────────────────────────┘
              │ WebSocket
              ↓
┌─────────────────────────────────┐
│  Game Server Cluster             │
│   - Sticky session per game      │
│   - In-memory state per game     │
│   - Validate + apply + broadcast │
└─────────────────────────────────┘
              │ Persist
              ↓
┌─────────────────────────────────┐
│  Game DB (Spanner / DynamoDB)     │
│  - On move: append to PGN          │
│  - On end: full game record        │
└─────────────────────────────────┘
              │
              ↓
┌─────────────────────────────────┐
│  Matchmaking Service              │
│  - Elo-based pairing               │
│  - Pool by time control + rating   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Rating Service                   │
│  - Glicko-2 / Elo update          │
│  - Leaderboard (Redis ZSET)        │
└─────────────────────────────────┘
```

### Step 1: Matchmaking

- User join queue → place in "rating bucket" (e.g., 1500 ± 100)
- Periodic 100ms cycle: try to pair from each bucket
- If no match in 5s, widen rating range
- Once paired → create `game_id`, both players connect to same Game Server

**Sticky session**: 同一 game 的两 player WebSocket 走 same Game Server (用 consistent hashing on game_id)。

### Step 2: Game state machine

In-memory state per game:
```
GameState {
    board: FEN string,
    move_history: [moves],
    turn: 'white' | 'black',
    clocks: { white_ms: 300000, black_ms: 300000 },
    status: 'active' | 'over' | 'draw',
}
```

**On move from Player A**:
1. Validate (legal move? A's turn? clock not 0?)
2. Apply (update board, switch turn, deduct clock)
3. Broadcast new state to A + B + spectators via WebSocket
4. Persist (async write move + new state)

### Step 3: Game persistence

- Each move → append to game log (Spanner row)
- On game over → write final record + outcome
- Indexed: by `user_id` (find user's games), by `created_at`

### Step 4: Rating update (after game ends)

```python
def update_elo(winner, loser, k=32):
    expected_w = 1 / (1 + 10 ** ((loser.rating - winner.rating) / 400))
    winner.rating += k * (1 - expected_w)
    loser.rating += k * (0 - (1 - expected_w))
```

Or Glicko-2 (chess.com 实际用，更精确 with uncertainty)。

### Step 5: Spectator broadcast

- Spectator opens WebSocket → subscribe to `game_id`
- Game Server maintains spectator list per game
- On move: broadcast to all spectators
- Large game (championship 100k spectators): use **fan-out service**

For championship: don't broadcast individual WebSocket from Game Server (slow)。Use:
- Game Server → Kafka `game_events.{game_id}`
- N **Spectator Servers** subscribe Kafka → push to their WebSocket clients
- Scale spectator servers independently

---

## 6. 组件深挖

### Deep Dive 1: Sticky Session

How to ensure player A + B both connect to same Game Server?

**Mechanism**:
1. Matchmaking creates `game_id`
2. Returns `game_id` + `game_server_address` (assigned via `consistent_hash(game_id)`)
3. Both clients connect to that address

If Game Server crashes:
- Restore game state from DB (replay PGN since last snapshot)
- New Game Server selected
- Notify both clients to reconnect to new endpoint

### Deep Dive 2: Clock Sync

Time control is critical (5 + 3 = 5 min total + 3 sec increment per move).

**Server-authoritative clock**:
- Server starts clock at game start
- On each move: deduct (server_now - move_start), add increment
- Client displays clock based on `(server_clock, server_now_offset)` — periodic resync

**Network lag compensation**:
- Player A's move took 200 ms to reach server → which clock to deduct?
- Convention: deduct from server-received time (player loses 200 ms latency time)
- Or: use NTP-synced client timestamp + max(client, server) for fairness

### Deep Dive 3: Premove

Player wants to pre-set next move. Common in bullet (1-min games).

**Implementation**:
- Premove stored client-side (visual indicator)
- When opponent's move arrives, client sends premove immediately if still legal
- Server validates premove same as regular move

**Server-side enforcement**: don't allow premove → tactical chess shouldn't allow super-fast premove abuse (chess.com allows, lichess optional)。

### Deep Dive 4: Anti-cheat

**Engine assist detection** (chess.com's hardest problem):

1. **Move similarity to Stockfish**: every move computed vs top engine moves → match rate
2. **Time pattern**: human move time varies; engine moves uniformly fast
3. **Move accuracy by phase**: engine has same accuracy throughout, human degrades in time pressure
4. **Statistical model**: ML classifier on these features

**Action ladder**:
- Suspicious → review by human
- Confirmed → ban / rating reset
- Repeat offender → IP/device ban

**Collusion** (two friends trade rating points):
- Detect repeated pairs winning suspiciously
- Game outcome pattern不正常 (always draws, etc.)

### Deep Dive 5: Reconnection

Player loses connection mid-game → must allow reconnect within time control。

**Implementation**:
- Client maintains `session_token` (signed, includes user_id + game_id)
- On reconnect: WebSocket reopen + send session_token
- Game Server checks: game still active + player belongs → resume
- Time during disconnect: deduct from disconnected player's clock (or 30s grace period)

### Deep Dive 6: Matchmaking Algorithm

**Naive**: queue per rating bucket → FIFO pair.

**Issue**: peak time (10k waiting) vs off-peak (10 waiting) — different optimal strategies.

**Lichess approach**:
- "Pool" model: every 1s tick, match all currently waiting
- Within pool, sort by rating, pair adjacent
- If queue thin: widen rating tolerance over time

**Edge**: avoid pairing same user back-to-back, prevent stale queue items > 30s wait.

### Deep Dive 7: Game Storage

Storage per game:
- PGN (Portable Game Notation): ~5 KB compressed (200 moves × ~15 B each)
- Metadata: 1 KB (players, outcome, ratings, time, tournament)
- Total: ~6 KB/game

1B games × 6 KB = **6 TB** — manageable single Spanner cluster.

Indices:
- by user_id (find your games)
- by ELO range (find historical example games)
- Full-text search on opening (Elasticsearch separately)

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：scope (chess engine 不做?), spectator scale, time control |
| 5-10min | 容量：50k concurrent games, 17k moves/sec, 100k spectators per championship |
| 10-15min | API + state machine |
| 15-25min | 高层架构：matchmaking → sticky session game server → DB → rating |
| 25-40min | Deep dives: clock sync / anti-cheat / reconnection / spectator broadcast |
| 40-45min | tournament / replay / monitoring |

---

## 8. 样板讲解稿

> Online chess 核心是 **server-authoritative state + low-latency WebSocket sync**。Server 永远是 truth，client 只显示。
>
> **架构**：
> 1. **Matchmaking**: Elo bucket queue → 100ms tick pair → assign game_id + game_server (consistent hash)
> 2. **Game Server**: in-memory state per game (board FEN + clocks + history)，validate move + apply + broadcast via WebSocket
> 3. **Sticky session**: both player + spectators 连同一 game server
> 4. **Persistence**: 每 move append to Spanner, 每局结束写 final record + update Elo (Redis ZSET leaderboard)
> 5. **Spectator at scale**: Kafka game_events.{game_id} + Spectator Servers fan-out for championship (100k viewers)
>
> **Deep dives**:
> - Clock sync: server-authoritative, deduct on server-receive time
> - Anti-cheat: move similarity vs Stockfish + time pattern + ML classifier
> - Reconnection: signed session_token + grace period
> - Matchmaking: pool-based pairing, widen tolerance over time
>
> Numbers: 50k concurrent games, 17k moves/sec, 1B historical games × 6 KB = 6 TB.

---

## 9. Follow-up Q&A

### Q1: "Player A 的 move 200ms 到 server，怎么 charge clock？"

**A**：deduct from server-receive time (player loses network latency)。**Fair** because both players have same condition. 如果想更 fair：用 NTP-synced client timestamp + 最大 50ms clamp。

### Q2: "Game Server crash 怎么办？"

**A**：
- Game state 周期 snapshot (每分钟) + 持续 append move 到 DB
- Crash 后：consistent_hash(game_id) 选 new server → server replay from DB → 通知 player 重连
- Client side：connection drop → exponential backoff reconnect → resume
- Time during outage: 暂停 clock 30s, 超 30s 算 player loss

### Q3: "Stockfish 8 layer 算分 1 秒，怎么实时检测 cheat?"

**A**：不在 game 时实时检测。Post-game analysis：
- 每局结束后 5 min 内跑深度引擎对比每步
- 累计 user 移动质量分（如 95% 接近最优）→ threshold trigger
- 累计够多 trigger → human review → action

Real-time impossible，但延迟 5 min ban 仍 effective。

### Q4: "100k 观众观战决赛，server 怎么撑？"

**A**：
- Game Server 不直接 broadcast to 100k WebSocket
- Game Server → Kafka topic `game_events.{game_id}`
- N **Spectator Fan-out Servers** subscribe Kafka → push to spectators
- 每 fan-out server 维护 10k WebSocket → 10 server enough
- Fan-out 跨 region (CDN-like)

### Q5: "Matchmaking 50ms 必须找到对手 vs 等到合适对手 5s, 怎么平衡？"

**A**：tunable per game type:
- Bullet (1 min): 优先快 match，rating tolerance 大
- Rated tournament: 严格 rating，等久也行
- Smart：如果 queue 一边 thick（high rating waiting）一边 thin（low rating waiting），不能 wide cross 否则 rating 暴动

Lichess 实测：90% match in 10s, 99% in 30s for active hours。

### Q6: "用户 board 数据可以本地缓存吗？"

**A**：client 缓存 visual board state 但**不能 trust**。Server-side validates every move. Client UX 改进：optimistic update (client immediately shows own move before server ack)，但 server reject → rollback 显示。

### Q7: "怎么实现 takeback (撤销上一步)?"

**A**：两玩家协议 feature。
- Player A 请求 takeback → server send "takeback offer" to B
- B accept → server rollback game state to previous move (从 log replay 或保留 snapshot)
- Broadcast new state to both
- Rated games 通常 disabled (防 cheese)

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **Client-authoritative move** → cheater 直接发 invalid move
2. **不用 sticky session** → player A 在 server X 走，player B 在 server Y，状态不同步
3. **Broadcast spectator 直接 from Game Server** → 大场观战时单 server 过载
4. **Clock 用 client time** → 时钟漂移可作弊
5. **不考虑 reconnection** → mobile 网差直接判负
6. **Storage 全 SQL ORM** → 1B games 慢

### ✅ 加分项

1. **Server-authoritative** state 主动强调
2. **Consistent hashing for game_id** sticky session
3. **Kafka + fan-out servers** for spectator scale
4. **Server-side clock** with latency compensation
5. **Glicko-2** (chess.com 实际用) instead of plain Elo
6. **Anti-cheat ML** (Stockfish move similarity + time pattern)
7. **Premove + optimistic UI** 提一嘴
8. **Pool-based matchmaking** (vs naive queue FIFO)

> [!key] STAFF vs SENIOR：能讲 **sticky session + clock sync + spectator fan-out + anti-cheat ML** 是 STAFF；只说 "WebSocket + DB" 是 SENIOR。

---

## 11. Cheat Sheet

```
核心: Server-authoritative state, WebSocket bidirectional

架构:
  Matchmaking → assign game_id → consistent_hash → Game Server
  Game Server (sticky) → validate move → broadcast WS → persist DB
  Rating Service post-game → Elo/Glicko-2 → Redis ZSET leaderboard

State:
  In-memory FEN + clocks + history per game
  Periodic snapshot + persistent move log (Spanner)

Spectator:
  Small: Game Server direct broadcast
  Large: Game Server → Kafka → Fan-out Servers (10k WS each)

Anti-cheat:
  Move similarity vs Stockfish
  Time pattern analysis
  ML classifier
  Async detection (5 min post-game)
  Human review for confirmed cases

Reconnect:
  Signed session_token
  Replay from DB on server crash
  Grace period 30s

Matchmaking:
  Pool tick every 1s
  Pair adjacent rating
  Widen tolerance over time

数字:
  50k concurrent games
  17k moves/sec
  100k spectators per championship
  1B games × 6 KB = 6 TB storage
  p99 move latency < 100 ms
```
