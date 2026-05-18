## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **WebSocket** | 浏览器 / app 跟 server 的全双工长连接 | 不挂的电话 |
| **Long polling** | client 发请求，server hold 住到有消息再返回 | 顾客在前台等服务员叫号 |
| **Presence** | 在线 / 离线 / 输入中状态 | "对方正在输入..." |
| **Fan-out (写时 / 读时)** | 一条消息扩散给多个收件人 | 发邮件 cc N 个人 |
| **Push notification** | 设备离线时通过 APNs / FCM 推送 | 邮局派件 |
| **Message queue** | 缓冲消息的队列 | 邮件 inbox |
| **Idempotency key** | 客户端给每个 message 的 unique ID，防重发 | 快递单号 |
| **Read receipt** | 已读回执 | 已读未回 |
| **End-to-end encryption (E2EE)** | 只有发收双方能解密，server 看不到内容 | 信封封口，邮局没法拆 |
| **Signal Protocol** | E2EE 标准 (Double Ratchet)，WhatsApp/Signal/Messenger 都用 | 加密协议标准 |
| **Vector clock / HLC** | 给分布式事件加 timestamp 用 | 多时区会议怎么排序 |
| **Group chat fan-out** | 群消息发给所有成员 | 公司全员邮件 |
| **Sharding by user_id** | 按用户分库 | 按姓氏首字母分到不同前台 |
| **Conversation ID** | 一个对话的唯一 ID | 一个房间号 |
| **Sticky session** | 同一用户的请求路由到同一 server | 老顾客认服务员 |

---

## 1. 题目本质

**Chat / Messaging System** = 实时消息平台，1:1 / 群聊 / 多设备 / 离线消息 / 已读回执 / 状态同步。

**典型产品**：
- **WhatsApp** —— 2B users, Signal protocol E2EE
- **Messenger** —— Meta 主打
- **WeChat** —— 1.3B MAU，群最多 500 人
- **Telegram** —— cloud-based，E2EE 可选
- **Slack** —— work chat，workspace 概念
- **Discord** —— gaming/community

**为什么这是 STAFF 高频题（OpenAI/Google/Meta 都问）**：

考的是 4 个核心难点：

1. **WebSocket fan-out** at scale：1B 在线用户，毫秒级递送
2. **Message ordering** + dedup + at-least-once
3. **Multi-device sync**：手机 / 桌面 / 网页消息同步
4. **Storage**：万亿条消息，GDPR / 删除合规

考 STAFF 关键：**不只是"发消息"**，而是**presence + delivery status + multi-device + offline + E2EE** 这堆复杂 trade-off。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `SendMessage(from, to, text) -> msg_id` | 1:1 发消息 |
| `SendGroupMessage(from, group_id, text) -> msg_id` | 群发 |
| `GetMessages(conv_id, before_id?, limit) -> msg[]` | 历史 |
| `MarkRead(msg_id)` | 已读 |
| `SetPresence(status)` | 设状态 |
| `Subscribe(user)` | 监听 |
| `CreateGroup(name, members) -> group_id` | 建群 |
| `AddToGroup / RemoveFromGroup` | 群成员管理 |

**澄清要点**：
- E2EE 需不需要？(影响 server 是否可见消息)
- 群最大成员数？(WhatsApp 1024, WeChat 500)
- 多设备：登录数量限制？session 模型？
- 是否支持 voice / video call？(可声明 out of scope)
- Search？(影响 server-side index, 与 E2EE 冲突)

### Non-functional

| 维度 | 目标 |
|---|---|
| **延迟** | p99 < 200 ms (in-region), < 500 ms (cross-region) |
| **Scale** | 1B DAU, 100M concurrent 在线 |
| **Throughput** | 100M MAU send 50 msg/day = 5B msg/day = 60k QPS sustained, 200k peak |
| **Availability** | 99.99% |
| **Durability** | 消息**不能丢** |
| **Consistency** | eventual; 顺序保证：同 conversation 内 strong |
| **Storage** | 100T messages × 200 B = 20 PB |

---

## 3. 容量估算

- **DAU**: 1B
- **Concurrent online**: 10% = 100M
- **Send rate**: avg 50 msg/user/day → 5 × 10^10 msg/day → **600k QPS sustained, 1.8M peak**
- **WebSocket connections**: 100M concurrent → 100k connections/server (Linux ulimit limit) → **1000 WebSocket servers**

**Storage**:
- Hot (last 30 days): 1.5 × 10^12 msg × 200 B = 300 TB
- Cold (older): 几年 history → 10 PB scale → cold tier (S3/GCS)

**Network**:
- Send 1.8M msg/sec × avg 1KB = 1.8 GB/s upstream
- Fan-out (assume avg 2 recipients per msg) = 3.6 GB/s downstream

---

## 4. 高层架构

### Step 1: 1:1 chat baseline

```
Client A ─WebSocket─→ Chat Server ─WebSocket─→ Client B
                            │
                            ↓
                       Message DB
```

### Step 2: 多 server + routing

100M concurrent users / 100k per server = 1000 servers，**怎么把 message 路由到正确的接收 server**？

**Pub/Sub**:
```
Sender ─→ Server X ─→ Kafka topic (user_b)
                              ↓
                      Server Y (consumes if user_b connected here)
                              ↓
                      WebSocket → Client B
```

**或 Discovery service**:
```
Server X queries Discovery: "user_b is on server Y"
Server X → Server Y (RPC) → WebSocket → B
```

**STAFF 推荐 Kafka pub/sub**：解耦、高可靠、retry 简单。每用户 topic 太多（10亿 topic不可），用 **shard topic** (`user-shard-0` ~ `user-shard-999`)，consumer group 订阅。

### Step 3: Persistent storage

Message DB 设计：

```
table: messages
  conversation_id (sharded by)
  message_id (timestamp + ULID for ordering)
  sender_id
  body (encrypted if E2EE)
  created_at
  status (sent/delivered/read by recipient)

table: conversations
  conversation_id
  participants
  last_message_id  (for sorting conv list)
  unread_count
```

**Sharded by conversation_id** (1:1 chat 创建一个 conv_id，群一个 conv_id)。

### Step 4: Group chat fan-out

**Write fan-out (Pull)**:
- Sender writes once
- 每个 receiver pull on demand
- 写便宜，读复杂 (要 query 所有 join 的 group)
- WhatsApp 这种用 push（fan-out write）更简单

**Read fan-out (Push)**:
- Sender writes once
- Server fan-out N copies to N receivers' inbox
- 读便宜，写贵 (1 msg → N writes)
- **N 太大时不行**（百万人群）

**Hybrid (Facebook / WhatsApp)**:
- 普通群 (< 500): push fan-out
- 超大群: pull fan-out
- "celebrity user" 1M followers: pull fan-out (Twitter feed 同理)

### Step 5: Presence

**Naive**：每秒上报 heartbeat → 不 scale (100M users × 1 Hz = 100M QPS)

**Better**:
- 用户上线时 sets `presence_key = user_id` in Redis with TTL = 60s
- 每 30s refresh TTL
- 朋友想看 presence → Redis GET (O(1))
- 上线/下线时 publish to **friends' channels** (subscribe 模型)

**Privacy**: presence 默认对朋友可见，可关闭。WhatsApp "last seen" 是这个。

### Step 6: Multi-device sync

User 有 phone + desktop + web。每个登录一个 device。

**Each device = independent WebSocket connection**:
- Server 给每个 device 一个 `device_id`
- Sending: 任一 device 发消息，all devices get echo (saved to history)
- Receiving: 所有 device 都收消息
- Read marker: device A marked read → broadcast to device B/C
- E2EE: each device has its own key pair → encrypt N times (one per recipient device)

**Signal protocol**: pairwise sessions, group chat uses sender key (一次加密，群内成员有 sender key 解密)。

### Step 7: Offline + Push

User offline (no WebSocket connection):
- Message saved to DB
- APNs/FCM push triggers wake → app fetches via REST API + opens WebSocket
- WhatsApp 的 "X 条新消息"

---

## 5. 组件深挖

### Deep Dive 1: WebSocket Server at 100M Connections

**单机 100k WebSocket connections** 极限：
- File descriptor limit (`ulimit -n` 改到 1M+)
- TCP socket memory (4KB / connection)
- Epoll efficiency (一个 thread 跑 100k connection events)

**实现**：
- Go (goroutine 10k → 100k 很轻)
- Erlang / Elixir (BEAM VM 原生支持百万连接)
- Java + Netty
- Node.js + uWebSockets

**Scaling out**:
- Stateless WebSocket server: 1000 nodes, sticky session via consistent hashing on `user_id`
- Discovery: Redis or Zookeeper maps `user_id → server`
- Load balancer: HAProxy / Envoy supports WebSocket upgrade

### Deep Dive 2: Message Ordering

**Same conversation 必须严格按发送顺序**。

**Naive**：用 server-side timestamp → 多 server / 多 region 时钟漂移破坏顺序。

**正确**:
- **Conversation-level sequence number**: each msg in conv gets monotonic `seq_no` (server assign)
- Client 显示按 `seq_no` 排序
- **HLC (Hybrid Logical Clock)** for cross-region: physical timestamp + counter

**Idempotency**:
- Client 生成 `client_msg_id` (UUID) 发到 server
- Server 检查重复 (within last 24h) → dedup
- 防 retry 造成重复消息

### Deep Dive 3: Delivery Receipts (sent/delivered/read)

**Sent**: server 收到 (HTTP 200 / WebSocket ack)
**Delivered**: 收件人 device 拿到 message (设备 ack 给 server)
**Read**: 用户在 app 看到 (user action ack 给 server)

**Update path**:
```
Message m1 from A → B
  status_A: sent (after server ack)
  status_A: delivered (after B device ack)
  status_A: read (after B reads in app)
```

每个状态变化 → server 推回给 sender。

**Storage**: 每条 msg 维护 status 字段，每个 group msg 维护 `delivered_to: [user_id], read_by: [user_id]` 列表。

### Deep Dive 4: Storage Strategy

**Hot vs Cold**:
- Last 90 days: Cassandra / DynamoDB (fast random read by conversation_id)
- Older: S3 archived (cold tier, 10× cheaper)

**Schema design**:
```
PK: (conversation_id, message_id)  // ordered by msg_id
SK: message_id (ULID, lex sorts by time)
```

**Pagination**: `GetMessages(conv, before=msg_id, limit=20)` → range scan backward。

**Compaction**: deleted messages (legal/GDPR) → tombstone + scheduled physical delete after 30 days.

### Deep Dive 5: End-to-End Encryption (Signal Protocol)

**Why E2EE**: server can't read messages → strong privacy。

**Double Ratchet**:
1. **X3DH (Initial key agreement)**: pre-key bundle exchange when first contacting
2. **Symmetric ratchet**: each message gets new key (forward secrecy)
3. **DH ratchet**: every reply triggers new DH key exchange (break-in recovery)

**Multi-device**:
- Each device has its own identity key
- Encrypting to user X = encrypt N times (N = X's devices)

**Group chat (Sender key)**:
- Encrypt msg with sender key (symmetric)
- Distribute sender key to N members via pairwise E2EE
- Rotate sender key when member added/removed (forward secrecy)

**Trade-off**:
- ✅ Privacy
- ❌ Server can't index for search / backup encrypted backup
- ❌ Multi-device sync is harder (each device needs own key)

### Deep Dive 6: Group Chat at Scale

**Small group (< 500)**: push fan-out
- Sender writes once
- Server fan-out N copies to each member's inbox table
- Simple, but write amplification N

**Large group (> 10k)**: pull fan-out
- Sender writes to group msg log
- Members poll/subscribe to the log
- Like Slack channels / Discord

**WhatsApp 1024 max member**: push fan-out works fine.

### Deep Dive 7: Search

**E2EE makes search hard**: server can't see content.

**Options**:
1. **Client-side search**: device downloads all history, full-text search locally (WhatsApp 这么做)
2. **Server-side search (no E2EE)**: ElasticSearch index of msg body (Slack)
3. **Searchable encryption**: 学术方向，未广泛使用

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：E2EE? group size? multi-device? search? |
| 5-10min | 容量：100M concurrent, 1.8M peak msg/s, 20 PB storage |
| 10-20min | 高层架构：WebSocket → pub/sub → DB → fan-out (push vs pull) |
| 20-35min | Deep dives: WebSocket scale / ordering / receipts / E2EE / group |
| 35-45min | presence / multi-device / search / GDPR |

---

## 7. 样板讲解稿

> Chat 是 SD 经典中的经典，难点有 4 个：(1) WebSocket fan-out at scale, (2) message ordering + dedup, (3) multi-device sync, (4) storage 万亿级。
>
> **架构**：
> 1. **WebSocket server pool** (1000 servers × 100k connection each)，sticky session via consistent hashing on user_id
> 2. **Pub/sub via Kafka** (shard topic 1000 个) 跨 server 路由
> 3. **Sharded DB** (by conversation_id)：hot 90 天在 Cassandra，cold 在 S3
> 4. **Group fan-out**: push for < 500, pull for > 10k
> 5. **Presence** via Redis TTL key + subscribe model
>
> **Deep dives**：
> - WebSocket at scale: Go/Erlang, sticky session, discovery service
> - Ordering: server-assigned seq_no per conversation, HLC for cross-region
> - Receipts: status field per msg + push to sender on change
> - E2EE: Signal protocol (Double Ratchet), sender key for group
> - Multi-device: each device = independent connection + key, sync via fan-out
>
> Numbers: 1B DAU, 100M concurrent, 60k QPS sustained / 200k peak, 20 PB storage.

---

## 8. Follow-up Q&A

### Q1: "如果我有 5 台设备，发一条消息怎么 sync 到全部？"

**A**：sender 发 → server 持久化 → fan-out 给 user 的 N devices (echo to sender's own devices + push to recipient's). 每 device 独立 WebSocket connection。Read receipt 也 broadcast to 所有 device。

### Q2: "WhatsApp 的 "last seen" 怎么实现？"

**A**：Presence via Redis：用户 active 时 SET `last_seen:user_id = now()` with TTL 5min. 朋友查询 GET this key。privacy 可关闭（key 不更新或 read 鉴权）。

### Q3: "Message 怎么保证不丢？"

**A**：3 层保险：
1. **Client retry with idempotency key**：网络失败 client 重发，server dedup
2. **Server WAL**：写消息先 append-only log，再 ack client
3. **Replication**：DB 3 副本，cross-AZ

如果 server 收到没 ack client，client 重发 → dedup by `client_msg_id`。

### Q4: "1000 人 group，一个人发消息怎么实现？"

**A**：push fan-out。Sender writes 1 row to `messages` (group_id, ...) → server fan-out 1000 inserts to each member's inbox table。Sequence number 由 group-level counter assign 保证顺序。如果 group > 10k 改 pull (member subscribe group log)。

### Q5: "User 在飞机模式 5 小时，回来后怎么拿到这期间的消息？"

**A**：app 上线 → 拉取 inbox `WHERE seq_no > last_synced_seq_no`。Server keep 至少 30 天历史。push notification 在飞机模式无效，但 app 上线后 fetch 历史。

### Q6: "Group key rotation 怎么实现 (E2EE)?"

**A**：成员变更时：
- 老 sender key 失效（不再 distribute）
- 新 sender key 生成，通过 pairwise E2EE distribute 给新成员列表
- 旧消息用旧 key 仍可解（已分发给老成员）
- 新消息用新 key 加密
- 这就是 **forward secrecy** for group。

### Q7: "怎么扛 DDoS？"

**A**：
- Rate limit per user (e.g., 100 msg/sec)
- Rate limit per IP at LB level
- CAPTCHA on registration
- Anti-spam ML model 在 message path 上 detect bot

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **All connections to 1 server** → 单机连接数爆 → 必须 shard
2. **没说 fan-out 策略** → group chat 失败
3. **Message order 靠 client timestamp** → 时钟漂移破坏顺序
4. **没考虑 multi-device** → echo 不同步
5. **E2EE 当作 server 透明** → 不知道 search/backup 是问题
6. **Presence 全 heartbeat** → 不 scale
7. **没有 idempotency** → 重试导致重复消息

### ✅ 加分项

1. **Signal Protocol / Double Ratchet** 提一嘴
2. **HLC for cross-region ordering**
3. **Sender key for group E2EE**
4. **Hybrid push/pull fan-out** (size threshold)
5. **Hot/Cold storage tier**
6. **Sticky session via consistent hashing**
7. **Erlang / Go 提一嘴**（百万 WebSocket 的经典选择）
8. **GDPR compliance**：tombstone + scheduled delete

> [!key] STAFF vs SENIOR：SENIOR 答"WebSocket + DB"；STAFF 答"WebSocket pool 1000 nodes + pub/sub + shard by user_id + push/pull hybrid fan-out + Signal protocol for E2EE + HLC for ordering + hot/cold storage tier"。

---

## 10. Cheat Sheet

```
架构层次:
  Client (WebSocket × N devices)
   → WebSocket Server Pool (1000 nodes, sticky session)
   → Kafka pub/sub (1000 shard topics)
   → Message DB (sharded by conv_id, Cassandra)
   → Cold tier (S3)
   → APNs/FCM for offline push

核心问题:
  - WebSocket at scale: Go/Erlang, 100k/node
  - Ordering: conv-level seq_no + HLC
  - Idempotency: client_msg_id dedup
  - Fan-out: push (< 500), pull (> 10k), hybrid
  - Multi-device: N WebSocket, fan-out to all
  - E2EE: Signal Protocol (Double Ratchet)
    - Pairwise for 1:1
    - Sender key for group
  - Presence: Redis TTL key + subscribe

Status flow:
  sent → delivered → read
  (每变化 → push to sender)

Storage:
  Hot 90 天: Cassandra/DynamoDB
  Cold: S3 archive
  GDPR: tombstone + scheduled physical delete

数字:
  1B DAU, 100M concurrent
  60k QPS sustained, 200k peak send
  20 PB total storage
  p99 < 200ms in-region, 500ms cross
```
