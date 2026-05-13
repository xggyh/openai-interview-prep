## 题目本质

设计 **CoderPad**（或 LeetCode IDE、Hello Interview 自家的代码编辑器）：浏览器内的多语言 IDE，支持**实时协作编辑**、**代码执行**、**面试场景**（候选人 + 面试官同步看代码）。

OpenAI 报告 4 次，Senior-Staff 级。**OpenAI 自家也有 coding interview tool**，对这题敏感。考点：**CRDT 协作编辑 + 沙箱执行 + 实时同步**。

## 需求拆解

**功能性：**
- 实时多人协作（候选人、面试官、同行）
- 语法高亮 + LSP（自动补全、jump-to-def）
- 运行代码（Python / Java / C++ / JS …）并显示输出
- 支持 stdin
- 可保存 session（面试结束后 reviewable）

**非功能性：**
- 输入延迟 < 100ms（打字时另一端立即看到）
- 代码执行启动 < 2s
- 100k 并发 session

## 整体架构

```ascii
       Browser (Monaco / CodeMirror editor)
              │
              │ WebSocket
              ▼
       ┌──────────────┐
       │  Realtime    │   sticky by session_id
       │  Gateway     │
       └──────┬───────┘
              │
              ▼
       ┌─────────────────────┐
       │  Collab Service     │  → CRDT / OT 同步引擎
       │  (per-session       │
       │   in-memory state)  │
       └──┬──────────────────┘
          │
          ▼
       ┌──────────────┐
       │  Redis       │  pub/sub for fan-out + cold storage
       └──────────────┘
              │
              ▼ (run code)
       ┌──────────────┐
       │  Code Run    │  ◀── Docker / Firecracker sandbox
       │  Service     │
       └──────────────┘
              │
              ▼ stdout/stderr
       streamed back to all clients
```

## 核心组件设计

### 1. 实时协作编辑（最核心）

两种主流方案：

**A. OT (Operational Transformation)** —— Google Docs 早年用。
- 客户端发本地 op (`insert at pos X char 'a'`)；
- Server 维持序列号，对其他 client 已经发过的 op 做 transform；
- 实现复杂度高（transform 函数难写对）。

**B. CRDT (Conflict-free Replicated Data Type)** —— Yjs、Automerge。
- 每个 char 有全局唯一 id（基于客户端 id + lamport timestamp）；
- 操作天然 commutative + idempotent，乱序到达不影响最终状态；
- 实现复杂度低，写代码场景**首选**。

**推荐 Yjs**（成熟、与 Monaco 编辑器集成现成）。

```python
# Server 侧伪代码
class CollabSession:
    def __init__(self, session_id):
        self.doc = Y.Doc()
        self.clients = set()

    def on_update(self, client, update_bytes):
        # 应用 CRDT update
        Y.applyUpdate(self.doc, update_bytes)
        # fan-out 给其他 client
        for c in self.clients:
            if c is not client:
                c.send(update_bytes)
        # 持久化
        redis.set(f"doc:{self.session_id}", Y.encodeStateAsUpdate(self.doc))
```

### 2. Cursor / Selection 同步

CRDT 主体是文档；cursor 是 ephemeral（关闭就没了）。用单独的 awareness protocol：
- 每客户端定期广播 `{user_id, cursor_pos, color}`；
- 其他 client 渲染对方光标。

### 3. 代码执行沙箱

**绝对不能在共享 server 跑用户代码** —— 即时挖矿、文件读、反向 shell 都可能。

```ascii
Run request
    ↓
Code Run API
    ↓
Spawn Docker container with strict limits:
  - cpu 1, mem 256 MB
  - network none
  - readonly rootfs except /tmp
  - timeout 10s
  - non-root user
    ↓
Pipe stdin in, stream stdout/stderr
    ↓
Capture exit code + output
    ↓
Cleanup
```

更安全：**Firecracker MicroVM** 或 **gVisor** —— 比 Docker 更强隔离。

实现选择：
- 客户端 click Run → API → 启动 sandbox（≤ 2s）
- 流式输出走 WebSocket 推回所有 session 客户端

**冷启动 < 2s 怎么办：** Hot pool 保留一批待命容器，按需弹出 + 注入代码。

### 4. 语言支持

每语言一套 image：`python:3.12-slim`、`openjdk:21`、`node:20`、`g++:13`。镜像里预装常用包（numpy、pandas）。

LSP（autocomplete / jump-to-def）：每 session 起一个 pyright / typescript-language-server 进程，client 通过 WSS 发 LSP request。**轻量**：LSP 不需要每个 session 启 image，可以共享 LSP 池 + workspace 隔离。

### 5. Session 持久化

- 文档实时存 Redis（CRDT state + 文本 snapshot）
- 每 10s 异步刷到 Postgres（备份）+ S3（长期归档）
- Replay：保存所有 CRDT update 历史，可以回放打字过程（候选人面试录像）

### 6. 面试角色

- 候选人 / 面试官 / 观察者三种 role
- 不同权限：观察者只读；面试官可切换 question / 给候选人写 hint comment
- "Lock to me" 模式：面试官点击 → 候选人侧编辑器被禁用（演示用）

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 协作算法 | Yjs CRDT | OT：实现难且 Yjs 生态成熟 |
| 编辑器 | Monaco（VS Code 同款） | CodeMirror：更轻量但 LSP 集成差 |
| 沙箱 | Firecracker MicroVM | Docker：可被攻击 |
| 实时通讯 | WebSocket | SSE：单向，不适合协作 |
| Cursor 同步 | Yjs awareness | 自己实现：浪费时间 |

## 容量估算

- 100k 并发 session × 平均 3 user/session = 300k 并发 ws conn
- 每 keystroke 1 KB 上行 + 3 KB fan-out
- 输入峰值 10 ops/s/user → 300k × 3 KB × 10 = 9 MB/s 上行 + 27 MB/s 下行

## 关键技术细节

- **Cold storage**：闲置 30 min 后 session 从内存清出，需要时从 Redis/Postgres restore
- **Replay log**：每 CRDT update 写 append-only file（不是直接覆盖 snapshot），用于审计 + 防作弊（候选人是不是 paste 大段代码？diff 时间间隔可以检测）
- **代码运行 history**：每次 run 保存 (input, output, exit_code) 留下面试官回看

> [!key]
> 三大技术亮点：(1) **Yjs CRDT** 协作；(2) **Firecracker sandbox** 跑代码；(3) **Awareness 协议** 同步光标。OpenAI 面试官会狠抠"如果两端同时编辑同一行怎么办"—— 答 CRDT 性质保证最终一致。

> [!pitfall]
> ❌ 用 Docker 跑用户代码不限网络 —— 用户可以反向 shell；
> ❌ 用 polling 不用 WebSocket —— 协作延迟 ≥ 200ms 体验崩；
> ❌ 把代码每改一字写 DB —— 写 QPS 爆；用 in-memory + 周期 flush；
> ❌ 自己写 OT —— 30 分钟面试写不完。

> [!followup]
> "如何防作弊（GPT 自动答）？" → keystroke timing 分析、tab switching detection（实际很难根治）；"如何支持白板 / 图？" → tldraw 集成；"如何录制视频？" → screen + voice + code timeline 三轨同步。
