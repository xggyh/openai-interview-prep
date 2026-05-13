## 题目本质

经典 **Chat/Messaging system**（WhatsApp / Messenger 级）：1:1 + group conversation、message delivery status、user presence、conversation history、扩展到百万级用户。

OpenAI 报告这题在 Mid-level-Senior Staff 级别都问，是 SD 面试经典题。考点：**fan-out 写策略、消息顺序、多设备同步、presence 系统**。

## 需求拆解

**功能性：**
- 1:1 和群聊（最多 100 人/群）
- 消息送达回执（sent / delivered / read）
- 用户在线状态（online / typing / last-seen）
- 历史消息持久化 + 滑动分页
- 多设备同步（手机 + 电脑 + Web）

**非功能性：**
- 1 亿 DAU，峰值 1M 并发连接
- 端到端消息延迟 P99 < 500 ms
- 消息至少送达一次（at-least-once），客户端做去重

**容量估算：**
- 1 亿 DAU × 平均每人 30 条/天 = 3B 条/天 ≈ 35k 写 QPS
- 峰值 5x → 175k 写 QPS

## 整体架构

```ascii
   Client (mobile / web)
        │  WebSocket (persistent)
        ▼
   ┌──────────────┐
   │  Edge GW     │  sticky by user_id
   │  (Envoy/L7)  │
   └──────┬───────┘
          │
          ▼
   ┌──────────────────┐
   │  Chat Server     │  Hot connection state, presence
   │  (stateful, 1M   │  Notification fan-out
   │   conn each)     │
   └──┬───────────┬───┘
      │           │
      ▼           ▼
 ┌──────────┐  ┌──────────────────┐
 │ Presence │  │  Message Service │
 │ Service  │  │  (write path)    │
 │ (Redis)  │  └────────┬─────────┘
 └──────────┘           │
                        ▼
                 ┌──────────────┐
                 │ Message DB   │  Cassandra / DynamoDB
                 │ (by conv_id) │
                 └──────┬───────┘
                        │
                        ▼ (CDC)
                 ┌──────────────┐
                 │  Push Worker │  → APN / FCM / Web Push
                 │  (offline    │
                 │   users)     │
                 └──────────────┘
```

## 核心组件设计

### 1. WebSocket 长连接（Edge ↔ Client）

- 1M 并发 → 至少 100 台 chat server，每台 ~10k 连接
- **Sticky routing**：edge L7 按 `user_id` consistent hash → 用户重连仍到同一台 server（state 沿用）
- 心跳：客户端每 30s ping，server 60s 没收到判断离线
- TLS 终结在 edge

### 2. 消息发送路径

```
A → ws send → Chat Server A → Message Service
                                  │
                          1. 写入 Message DB (conv_id, msg_id, sender, body, ts)
                          2. 发布到 Kafka topic: conv.{conv_id}
                                  │
                  ┌───────────────┴─────────────────────┐
                  ▼                                     ▼
        Chat Server B (where B is online)      Push Worker (B offline)
                  │                                     │
                  ▼                                     ▼
              ws push to B's clients           APN/FCM notification
```

### 3. 消息顺序 + ID 生成

**Snowflake 64-bit ID**: `timestamp_ms(41) | server_id(10) | seq(12)`，单服务器单毫秒可生成 4096 个。同一 conv 内 ID 自然递增，客户端可按 ID 排序。

**对一 conv 的写入路由到同一 partition**：保证同对话内消息顺序。

### 4. 多设备同步

每个用户有多个 `device_id`（手机、电脑、Web）。消息表存 `(conv_id, msg_id, body, sender, ts)`，**只存一份**，不是 per-device 复制。

每设备维护一个 `last_synced_msg_id`：上线时 `SELECT msg_id, body FROM messages WHERE conv_id=? AND msg_id > last_synced` 拉新消息。

### 5. 消息存储（DB schema）

**Cassandra**：partition key = `conv_id`，clustering key = `msg_id DESC`。这样同一对话的消息物理上聚集，按时间倒序查询是单 partition scan，飞快。

```sql
CREATE TABLE messages (
  conv_id      UUID,
  msg_id       BIGINT,        -- Snowflake
  sender_id    UUID,
  body         TEXT,
  msg_type     TEXT,
  reply_to     BIGINT,
  ts           TIMESTAMP,
  PRIMARY KEY (conv_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);
```

**Conversation membership**：单独表 `(conv_id, user_id, joined_at, role)`，群聊查成员用。

### 6. 送达回执

- `sent`：客户端 → server，server 写完 DB 即 ack
- `delivered`：接收方设备收到 ws push 时，发回 `ack delivered`，server 写 status
- `read`：用户打开会话，客户端发 `ack read up_to msg_id`，server 写 status

回执也是消息（特殊 type），通过同样的 ws + DB 路径走。

### 7. Presence System

- 用户在线状态存 Redis：`SET presence:{user_id} {device_id} EX 60`，每 30s 客户端续期
- "好友列表"订阅好友的 presence —— pub/sub on Redis channel
- 频繁更新会爆 Redis QPS，做 **batching + 节流**（每用户 1 次/30s 更新足够）

### 8. Typing indicator

不写 DB，纯走 ws 转发。客户端每 3s 发 `typing` ping，server 转发给 conv 内其他在线用户。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Pull vs Push | Push（ws）on-line + Pull（API）on-reconnect | 纯 pull：延迟高 |
| Fan-out 时机 | 写时 fan-out（写后立即 push 到所有 conv 成员） | 读时聚合：群多了爆炸 |
| 消息 DB | Cassandra（写优化，按 conv 分区） | Postgres：写吞吐撑不住 |
| ID | Snowflake | UUID：无序，clustering 坏 |
| 多设备 | 共享单条消息 + per-device cursor | per-device 复制：膨胀 |

## 一致性 / 可靠性

- **at-least-once 送达**：消息可能被推 2 次，客户端用 `msg_id` 去重
- **离线消息**：用户离线时消息仍写 DB，下次上线拉 missed
- **消息 ordering**：同 conv partition 内强保证；跨 conv 无保证（也不需要）
- **GDPR / 删除**：消息删除标记 + 异步实际删除

## OpenAI 报告里的真实变种

抓到的 timeline 里有几个值得注意的：
- "WhatsApp without group chat and media upload" → 简化版（也常被问）
- "Regular chat question but with images instead of text" → GDrive+Chat 解法：图片上传到 S3 presigned URL，消息只存图片 URL
- "Anthropic Mid-level (2021)" / "Anthropic Staff (May 2026)" —— Anthropic 也问，说明这是行业标准 SD 题

> [!key]
> 三大要素：(1) WebSocket sticky + Chat Server 长连接；(2) Cassandra by conv_id 写优化；(3) Push 实时 + Pull on reconnect 兜底。

> [!pitfall]
> ❌ 用 HTTP polling 替代 ws —— 延迟 + 服务端连接数爆；
> ❌ 同 conv 用多个 partition —— 消息乱序；
> ❌ Read receipt 单独存 per-message-per-user 表 —— 数据膨胀 N²；
> ❌ Typing indicator 写 DB —— 完全没必要；
> ❌ 不做 dedup —— 客户端会显示重复消息。

> [!followup]
> "E2E 加密怎么做？" → Signal Protocol，client-side double ratchet。服务端只是密文转发，不知道明文。"如何支持百万人群？" → 不再做 push fan-out，改读时聚合 + 抽样压缩。"语音/视频通话？" → 走 WebRTC，server 只做 signaling + STUN/TURN。
