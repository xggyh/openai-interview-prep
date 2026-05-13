## 题目本质

设计 **Slack** —— 类 IM 平台但以 channel + thread 为组织核心，支持 DM、公开/私有 channel、消息线程、未读指示器、消息持久化。

题面相比通用 chat（Messenger）的区别：**channel 是一等公民**（用户多对一/多对多关系）、**threads 是消息的回复树**、**unread state 极重要**（团队协作场景 unread 决定每天工作流）。

## 需求拆解

**功能性：**
- DM（1:1 / 多人组）+ Channel（public / private，可加入）
- Message 支持回复成 thread（树形）
- @ mention + reaction（emoji）
- Unread indicator（per-channel、per-thread）
- 全文搜索消息历史
- 文件/图片附件

**非功能性：**
- 1M 企业用户，10k 并发 channel 活动
- 消息延迟 P99 < 200 ms
- 99.99% 可用，断网重连不丢消息

## 整体架构

```ascii
       Client (Web/Desktop/Mobile)
              │
              │ WebSocket + REST
              ▼
       ┌──────────────┐
       │  Edge GW     │
       └──────┬───────┘
              │ sticky by user_id
              ▼
       ┌──────────────┐         ┌─────────────────┐
       │ Chat Server  │ ──────▶ │ Channel Service │
       │ (ws conns)   │         │  (membership,   │
       └──────┬───────┘         │   metadata)     │
              │                 └────────┬────────┘
              ▼                          │
       ┌──────────────┐                  ▼
       │ Message      │            ┌─────────────┐
       │ Service      │            │  Postgres   │
       └──────┬───────┘            │ (channels,  │
              │                    │  members)   │
              ▼                    └─────────────┘
       ┌──────────────┐
       │ Cassandra    │  by channel_id
       │ (messages)   │
       └──────┬───────┘
              │
              ▼ (CDC)
       ┌──────────────┐
       │ Search       │  Elasticsearch
       │ Indexer      │
       └──────────────┘
              ▼
       ┌──────────────┐
       │ Push Notif   │  for offline / mobile
       └──────────────┘
```

## 核心组件

### 1. 数据模型

```sql
-- Channel (Postgres)
CREATE TABLE channels (
  channel_id   UUID PRIMARY KEY,
  workspace_id UUID,
  name         TEXT,
  type         TEXT CHECK (type IN ('public','private','dm','mpdm')),
  created_at   TIMESTAMPTZ
);

CREATE TABLE channel_members (
  channel_id   UUID,
  user_id      UUID,
  joined_at    TIMESTAMPTZ,
  last_read_msg_id BIGINT,    -- 关键：unread 状态
  PRIMARY KEY (channel_id, user_id)
);

-- Messages (Cassandra)
-- partition key = channel_id, clustering = msg_id DESC, thread_root_id
CREATE TABLE messages (
  channel_id      UUID,
  msg_id          BIGINT,            -- Snowflake
  thread_root_id  BIGINT,            -- null 顶层；非 null 是回复
  sender_id       UUID,
  body            TEXT,
  attachments     LIST<TEXT>,
  reactions       MAP<TEXT, SET<UUID>>,
  PRIMARY KEY ((channel_id), msg_id)
);
```

### 2. Thread 模型

不是 nested 树，而是 **两级**：每个 thread root 是一条普通顶层消息；回复指向其 `msg_id` 作为 `thread_root_id`。查询 thread = `SELECT WHERE thread_root_id = ?`。这避免深度递归且 Slack UI 本身就是两级。

### 3. Unread 计算

每个 `(channel_id, user_id)` 存 `last_read_msg_id`。客户端打开 channel 时：
- 查最新 msg_id
- 算 unread_count = `COUNT(msg_id > last_read_msg_id AND channel_id = ?)`
- 用户关闭/切换 channel 时更新 `last_read_msg_id = max_seen_msg_id`

**优化**：unread count 不实时 DB count，**客户端本地维护**（push 来一条 +1，标已读清零）；服务端只 source-of-truth `last_read_msg_id`。

### 4. @mention 实时推送

发送方写消息时 parse `@user`，提取 `mentioned_users` 集合：
- 写入 `mentions` 表（per-user mention queue）
- 推送 `mentioned` event 给被 @ 的用户的 ws（即使他没在该 channel 也要红点）
- 触发 push notification（如果用户不在线）

### 5. 全文搜索

- Cassandra 消息表 CDC（Debezium）→ Kafka → Elasticsearch
- 索引：`channel_id`, `user_id`, `body`, `ts`
- 搜索时按 `channel_id IN (user's channels)` 过滤 + 全文匹配

### 6. 文件附件

- 客户端先 `POST /uploads` → 得 S3 presigned URL → 直接上传 S3
- 上传完成回调 → 创建 file record → 消息 body 引用 file_id
- 下载时校验 channel membership 权限

### 7. Fan-out 策略

- 发送消息：写 DB → 发 Kafka topic `channel.{channel_id}`
- Chat server 订阅自己管的所有 channel 的 topic → 推 ws
- 一个 channel 可能跨多 chat server（不同用户连不同 server），用 Redis pub/sub 也行（更轻）

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Thread 嵌套 | 两级 | 无限递归：查询慢、UI 难做 |
| Unread | client local + last_read_msg_id source | 实时服务端 count：QPS 高 |
| Fan-out | push to online + push-notif for offline | 纯 pull：消息延迟感差 |
| Channel membership | Postgres | DynamoDB：JOIN 不友好 |

## 与通用 Chat/Messaging 区别（面试官爱问）

| 维度 | Messenger | Slack |
|---|---|---|
| 主体 | 用户间 1:1/小群 | Channel 是一等公民 |
| 历史 | 大多看不到加入前消息 | Public channel 任何成员都能拉全部历史 |
| Unread | 简单 | 极重要 + 跨 channel/thread |
| 文件 | 简单附件 | rich snippets, code, code formatting |
| 搜索 | 弱 | Elasticsearch 重投入 |

## 关键决策点

> [!key]
> Slack 与通用 Chat 的最大区别：**channel-centric** + **unread 是一等用户体验**。不要用普通 chat 模板套；要专门设计 channel_members 表的 `last_read_msg_id`。

> [!pitfall]
> ❌ Thread 用无限嵌套：查询噩梦；
> ❌ Unread count 在服务端实时 query：百万 channel × 千用户 QPS 爆炸；
> ❌ 全文搜索直接走 Cassandra：CQL 不支持；
> ❌ 私有 channel 写入不校验 membership：权限漏洞。

> [!followup]
> "Huddles（音频房间）？" → WebRTC mesh / SFU。"Slack Connect（跨 workspace channel）？" → 引入 federation 层，membership 跨 workspace 解析。"如何降低 channel join 后的"历史回灌"成本？" → 按 channel 维度做 cold/hot 分层，老消息存便宜的 S3 Parquet。
