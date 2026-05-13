## 题目本质

设计一个支持**多 conversation thread** 的 mobile chatbot。重点是**移动端架构** —— offline support、消息持久化、跨设备同步、UI 响应性。

OpenAI Staff 级（Mobile System Design），1 人报告。考点：**mobile-first 的 chat app 架构**，区别于 server-side SD。

## 需求拆解

**功能性：**
- 用户与 AI bot 对话；多个 conversation thread 切换
- 移动端 UI：消息列表 + 输入框 + thread switcher
- 离线发送：网络断时输入消息，恢复后发送
- 多设备：手机 / 平板 / web 端看同一份历史

**非功能性：**
- 单 thread 历史 ≤ 10k 消息
- 启动 < 1s 显示最近 thread
- 流式响应（token streaming）
- 离线不丢消息

## 移动端架构

```ascii
       ┌────────────────────────┐
       │     Mobile App         │
       │                        │
       │  ┌──────────────────┐  │
       │  │  UI Layer        │  │  React Native / SwiftUI / Compose
       │  │  (chat list +    │  │
       │  │   thread view)   │  │
       │  └──────┬───────────┘  │
       │         │              │
       │         ▼              │
       │  ┌──────────────────┐  │
       │  │  ViewModel       │  │  state mgmt (MVI / Redux)
       │  │  (per thread)    │  │
       │  └──────┬───────────┘  │
       │         │              │
       │         ▼              │
       │  ┌──────────────────┐  │
       │  │ Repository       │  │
       │  │  - local: SQLite │  │
       │  │  - remote: HTTP  │  │
       │  └──────┬───────────┘  │
       │         │              │
       │  ┌──────▼───────────┐  │
       │  │ Sync Engine      │  │  offline queue + reconnect
       │  └──────┬───────────┘  │
       │         │              │
       └─────────┼──────────────┘
                 │  HTTP/WS
                 ▼
          ┌─────────────────────┐
          │   Backend API       │
          │   - threads CRUD    │
          │   - messages CRUD   │
          │   - LLM proxy (SSE) │
          └──────┬──────────────┘
                 │
                 ▼
          ┌─────────────────────┐
          │  Storage            │
          │  - threads/msgs PG  │
          │  - object S3        │
          └─────────────────────┘
```

## 核心组件

### 1. 本地优先（offline-first）

**所有读 / 写先走 SQLite**，UI 立即响应；后台 sync engine 异步推到 server。

```kotlin
// Pseudocode (Compose)
fun sendMessage(threadId: String, body: String) {
    val msg = Message(
        id = UUID.randomUUID().toString(),     // 客户端生成 ID
        threadId = threadId,
        body = body,
        sender = "user",
        ts = System.currentTimeMillis(),
        status = "pending",                    // 本地状态
    )
    db.messages.insert(msg)                    // 本地立即可见
    syncEngine.enqueue(msg)                    // 异步推 server
}
```

UI subscribe local DB（Room/SQLDelight），插入立即触发 UI 更新。

### 2. Sync Engine

```kotlin
class SyncEngine(val db, val api) {
    val outbound = Channel<Message>()    // pending 队列

    fun enqueue(msg: Message) {
        outbound.send(msg)
    }

    suspend fun start() {
        for (msg in outbound) {
            try {
                val res = api.sendMessage(msg)   // 包含 idempotency key = msg.id
                db.messages.updateStatus(msg.id, "sent")
                // 流式接收 assistant reply
                api.streamReply(res.threadId).collect { token ->
                    db.messages.appendToLastAssistant(threadId, token)
                }
                db.messages.markComplete(threadId)
            } catch (e: Exception) {
                // 重新入队 with backoff
                delay(backoff)
                outbound.send(msg)
            }
        }
    }
}
```

**关键**：
- `idempotency_key = msg.id` 让 server 去重（同一消息 retry 不会创建两条）
- 失败重试用 exponential backoff
- 流式响应 token 也写本地 DB，UI 自然 update

### 3. Thread 切换

- 用户点 thread → ViewModel 加载该 thread 的 messages（DB query LIMIT 50 by ts DESC）
- 滚动到顶时 lazy load older（按 ts 分页）

```kotlin
class ThreadViewModel(threadId: String) {
    val messages: StateFlow<List<Message>> = db.messages
        .observeByThread(threadId)
        .map { it.sortedByDescending { it.ts }.take(50) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
```

### 4. 多设备同步

每条消息有 server `seq` 字段；客户端记 `last_synced_seq`：

```
On reconnect:
    GET /sync?since={last_synced_seq}&thread_id={thread_id}
    → 返回新消息
    → 本地 upsert
    → last_synced_seq = max(seq)
```

冲突：客户端 pending 消息 + server 已有同 id → 用 server 版本（server wins for sent；本地 wins for pending）。

### 5. LLM 流式响应

```
Mobile → POST /threads/{id}/messages { body, idempotency_key }
        ← 200 OK + SSE stream
        ← event: token data: {"t":"hi"}
        ← event: token data: {"t":" there"}
        ← event: done

App 收到 token：
    db.appendAssistantToken(threadId, token)
    UI flow 触发刷新
```

App 后台时：保留下载的 part response，但暂停渲染。前台时继续。

### 6. 持久化 / 加密

- SQLite 加密：SQLCipher（用户密码 / KeyStore 派生 key）
- 备份：iCloud Documents / Android backup（如果用户允许）
- 服务端可选 E2EE：消息在客户端加密，server 只见密文

### 7. Push Notification

App 后台 / 关闭时：server FCM/APN push 新消息。Tap 推送 → 跳到对应 thread。

## 移动端特有的取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 数据本地化 | SQLite（强 offline） | 仅内存：app kill 后丢 |
| 状态管理 | MVI / Redux | imperative：难维护 |
| 网络 | HTTP + SSE | WebSocket：穿透差，电池耗 |
| Sync 时机 | App 前台 + 后台 limited（iOS background fetch） | 实时长连：电池 / 数据流量耗 |
| 加密 | 客户端 + 服务器透明 | E2EE：服务端不能做内容审核 |

## 关键技术细节

- **打字延迟**：用户输入到 UI 显示必须 < 16ms（一帧）。本地 DB 写要异步，不阻塞 UI 线程
- **历史滚动性能**：LazyColumn / RecyclerView 虚拟化，只渲染可见 + buffer
- **图片**：使用 Coil/Glide 缓存，避免重复下载
- **Backstack**：thread 切换走 Navigation，记住每 thread 滚动位置
- **数据流量节省**：消息列表 GZIP；图片低分辨率预览，点 enlarge 再下载原图

> [!key]
> 核心是 **offline-first** —— 所有 UI 都读本地 DB，sync engine 在后台处理网络。这样：(1) 启动快（本地数据立即显示）；(2) 离线可用；(3) UI 永远响应快。

> [!pitfall]
> ❌ UI 直接调网络 —— 弱网 / 离线时白屏；
> ❌ ID 服务端生成 —— 离线无法乐观显示；客户端用 UUID + idempotency key；
> ❌ Sync 不做幂等 —— 重试时消息重复；
> ❌ SSE 不在后台保留 —— iOS 后台 5 分钟就 kill connection；
> ❌ 加密用户密码不用 KeyStore —— OS 重装后丢；
> ❌ Thread 滚动位置不记 —— 用户切回老 thread 跳回顶。

> [!followup]
> "如何 E2EE 还能 server-side 内容审核？" → 客户端审核 + zero-knowledge proof（前沿）；"如何降低 LLM 调用成本？" → 客户端 cache 常用问答；"如何支持百万 thread？" → 客户端 paginated list；删除久未用 thread 的本地副本（保留 server 拷贝）。
