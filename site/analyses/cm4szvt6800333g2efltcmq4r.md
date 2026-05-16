## 题目本质

设计 **Facebook Live Comments**：直播流期间，几百万观众实时发送 + 看到 comments。Twitch / YouTube Live / FB Live 同问题。

## 需求

- 1M+ concurrent viewers per stream
- < 1 sec comment delivery
- 全局有序（同一秒内）
- Spam / 违规过滤
- 历史 replay 时也要 sync 显示

## 整体架构

```ascii
   Viewer A (post comment)
       │
       ▼
  ┌──────────────┐
  │ Comment API  │  → moderation + rate limit
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Kafka topic  │  per-stream partition
  │ stream.{id}  │
  └──────┬───────┘
         │
   ┌─────┼──────────────┐
   ▼     ▼              ▼
  Pub/Sub fan-out per region
   │
   ▼
  Viewer B/C/... receive via WebSocket
```

## 核心组件

### 1. 写路径（post comment）

```
Client → POST /streams/{id}/comments {text}
       → rate limit (per user, per stream)
       → spam / profanity filter (sync if fast，async if heavy ML)
       → assign comment_id (snowflake) for global ordering
       → write Kafka topic stream.{id}
       → return ack
```

### 2. 读路径（receive comment）

```
Client opens stream → subscribe WebSocket to comment fan-out for stream.{id}
                    → server tails Kafka topic stream.{id}
                    → push new comments via WS
```

### 3. Fan-out

1M viewer per stream → 不可能 1 server 同时 push 给 1M。多层：
- 1 stream → 10 fan-out servers (each handles 100k viewer WS connections)
- Each fan-out server subscribes Kafka → push to its viewers

### 4. Moderation

- **Sync (lightweight)**：profanity wordlist match，spam regex —— < 10ms
- **Async (ML)**：toxicity classifier，hate speech detect —— 100ms+，先 publish 后异步 redact

如果 ML 判定 violation：发 "delete" event 让所有 viewer 客户端 hide。

### 5. Rate limit

每 user：
- 5 comments/second per stream
- 100 comments/minute global
- Captcha if exceeded

防 bot 刷屏。

### 6. Ordering

同一秒数千条 comments —— 完全 strict order 不重要（用户感知 ~1s 内 OK）。但**每用户自己的 comment** 必须按 send 顺序。

实现：partition by stream_id → kafka 同 partition 内 ordered。同 user 同 stream comments 同 partition → ordered。

### 7. 历史 replay

录播 viewer 看的时候同 comment 也要播：
- Live 时 Kafka offset 写入 video timestamp metadata
- Replay 时按 video position → query (stream_id, video_position_range) → fetch historical comments + show

存 Cassandra / Bigtable，partition by stream_id。

### 8. 客户端 buffering

WebSocket 每秒 push N comments。客户端 buffer + render at 30fps，不让 UI 卡。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Transport | WebSocket | SSE：单向 OK |
| Pipeline | Kafka per stream | Single global topic：partition hot |
| Moderation | Sync simple + async ML | Pure sync：慢；pure async：危险 |
| Order | Per-user ordered | Global strict：贵 |
| Replay | Persist + replay-by-time | None：录播 silent |

## 容量估算

- 1M viewers × 1 comment/min average = 17k comment QPS per stream peak
- Fan-out: 1M × 17k = 17B msg/s total volume per stream → 需 sharded fan-out
- Storage：1 stream × 4 hour × 17k/sec = ~250M comments / stream

## 易错点

> [!pitfall]
> ❌ 单 Kafka topic for all streams → partition hot；
> ❌ 1 server fan-out 1M WS → 资源爆；
> ❌ 不 rate limit → spam 刷屏；
> ❌ 没 async ML mod → 极端内容 live；
> ❌ Reply 不存 timestamp → 录播时 comment 错位。

> [!key]
> 三大要点：(1) **Per-stream Kafka partition + multi-tier fan-out**；(2) **Sync 简单 mod + async ML mod**；(3) **Snowflake comment_id + 持久化 enable replay**。

## 类似系统

参考 [[cm4szunov00303g2e2gomqo2j]] (chat system) — 同样 WebSocket + fan-out，但 chat 更小群组，live comment 是巨型广播。

> [!followup]
> "Super chat / paid highlights？" → 特殊 message type + 优先 display；"Mod tools (banhammer)？" → admin API + 实时 ban propagation；"AI auto-summary of comments？" → batch process trending themes。
