## 题目本质

设计一个简化版 ChatGPT —— 用户在 web 上输入消息，系统调用 LLM 生成回复，**支持多轮对话上下文**，**流式输出（token-by-token streaming）**。规模：先支持中等量用户（say 1k 并发会话）。

OpenAI 自家问这题，他们想看你是否理解 **LLM 推理的工程边界**：上下文管理、流式协议、推理服务集群、长尾延迟控制、限流、安全（prompt injection / 毒性内容）。

## 需求拆解

**功能性：**
- 用户登录 → 创建/切换 conversation → 发消息 → 看到流式回复
- 对话历史持久化，刷新页面不丢
- 多设备同步（手机/电脑看到同一份 history）
- Regenerate / Edit message / Branch conversation
- 模型选择（gpt-4o / o3 / etc.）

**非功能性：**
- 首 token 延迟 P99 < 1s（TTFT，time-to-first-token）
- 端到端流式吞吐 30+ tokens/s
- 1k 并发对话起步，可扩

## 整体架构

```ascii
       Browser
          │  SSE / WebSocket
          ▼
    ┌─────────────┐
    │   Edge GW   │  → auth, rate-limit, fan-in conversation
    └──────┬──────┘
           │
    ┌──────▼──────────┐
    │  Chat API       │  → 拉历史、调 LLM、stream 回去
    │  (stateless)    │
    └──┬──────────┬───┘
       │          │
       ▼          ▼
  ┌────────┐  ┌────────────────────────┐
  │ Convo  │  │  Inference Service     │
  │ Store  │  │  (model serving)       │
  │ (PG +  │  └─────┬──────────────────┘
  │  Mongo)│        │ gRPC streaming
  └────────┘        ▼
                ┌─────────────────────┐
                │ Model Worker Pool   │
                │ (GPU servers,       │
                │  vLLM / TGI)        │
                └─────────────────────┘
                        │
                        ▼ (logging, eval)
                ┌─────────────────┐
                │  Eval / Safety  │
                │  Worker (async) │
                └─────────────────┘
```

## 核心组件设计

### 1. 流式协议（最关键）

**Server-Sent Events (SSE) over HTTPS** —— 单向 server → client 推 token，连接长保持。比 WebSocket 简单（不需要双向），比轮询低延迟。

```
GET /chat/{conv_id}/stream
Accept: text/event-stream

event: token
data: {"t":"Hello"}

event: token
data: {"t":" world"}

event: done
data: {"finish_reason":"stop","usage":{"prompt_tokens":42,"completion_tokens":2}}
```

客户端用 `EventSource` API 接收，遇到 `done` 关闭连接。

### 2. Conversation Store

```python
# Postgres：用户、对话元信息
class Conversation:
    id: UUID
    user_id: UUID
    title: str           # 由 LLM 摘要生成
    model: str
    created_at: datetime
    updated_at: datetime

# MongoDB / Spanner：消息内容（写入量大，schema 灵活）
class Message:
    id: UUID
    conv_id: UUID
    role: 'user' | 'assistant' | 'system' | 'tool'
    content: str
    parent_id: UUID | None   # 支持 branch
    created_at: datetime
    token_count: int
```

**多设备同步**：客户端 subscribe `conv_id` 的 SSE channel，新 message 通过 Redis pub/sub fan-out 到该 conv 的所有活跃 session。

### 3. Context Window 管理

LLM 有上下文长度限制（如 gpt-4o 128k tokens）。策略：

- **完整 history**：当 token 数 < 模型上下文 80%，直接发全部
- **滑窗截断**：丢掉最早的 message（保留 system prompt）
- **摘要压缩**：调用便宜模型把早期对话摘要成 1-2 句，节省 token 数

```python
def build_prompt(conv_id, max_tokens=100_000):
    msgs = load_messages(conv_id)
    total = sum(m.token_count for m in msgs)
    if total <= max_tokens * 0.8:
        return msgs
    # Summarize earliest segment
    keep = [msgs[0]]  # system
    cutoff = 0
    while sum(m.token_count for m in msgs[cutoff+1:]) > max_tokens * 0.6:
        cutoff += 1
    summary = call_cheap_model("Summarize:", msgs[1:cutoff+1])
    return keep + [Message(role='system', content=f"[earlier]: {summary}")] + msgs[cutoff+1:]
```

### 4. Inference Service

- **多副本 GPU worker**（每副本一个模型 instance），前置 router 按 model 名分发
- 用 **vLLM** 或 **TGI**：核心是 PagedAttention + continuous batching，把多个并发 request 拼成一个 batch 喂 GPU
- TTFT 优化：prefill 阶段计算 prompt 的 KV cache，decode 阶段一 token 一 token 出 → 用 **prefix caching** 缓存常用 system prompt，避免重复 prefill

### 5. 限流 + 配额

- 每用户每分钟 token budget（input + output）
- 每模型 global concurrency limit（GPU 数量）
- 排队系统：等待队列长度过大时返回 429 / 显示"系统繁忙"

### 6. 安全（Trust & Safety）

- **Input moderation**：用户输入过 moderation API（敏感词 / 越狱检测）
- **Output moderation**：流式生成的同时分块跑 safety classifier，发现违规即截断并替换
- **Prompt injection 防御**：对系统的内部指令不要直接拼用户输入到 prompt 末尾，要用 message role 隔离

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| 流式协议 | SSE | WebSocket（双向更重）/ HTTP polling（延迟高） |
| 历史存储 | MongoDB（消息）+ Postgres（元信息） | 单 Postgres：写入热点 |
| Inference batching | continuous batching (vLLM) | static batching：延迟 spike |
| TTFT 优化 | prefix caching | 每次重算：浪费 GPU |
| 模型副本 | 多模型多副本，按 SLA 调度 | 单副本：上不去并发 |

## 容量估算

- 1k 并发对话 × 平均 30 tokens/s 输出 = 30k tokens/s
- 一张 H100 跑 gpt-4o-mini 可以达到 ~5k tokens/s（不同模型差很多）
- 至少 6-10 张 H100，加冗余 → 1 个 cluster 16 张

## 实施关键点

- **流式中断**：用户点 stop 按钮 → 客户端关闭 SSE → 服务端检测到对端断开 → 给 worker 发 cancel 信号 → 释放 GPU
- **断线重连**：流式中断后，客户端可以请求 `GET /chat/{conv_id}/messages/{msg_id}` 拉已生成部分继续
- **billing**：每 message 记录 input_tokens、output_tokens，按模型单价 × 量计费

> [!key]
> 这题 OpenAI 自己问最有信号 —— 他们想看你**懂 LLM 推理工程**（不只是叫 API）。三个亮点：**(1) SSE 流式 + cancel**；**(2) continuous batching（vLLM）+ prefix caching**；**(3) context window 管理 + 摘要压缩**。

> [!pitfall]
> ❌ 把 LLM 调用做成普通 REST：流式体验丢失，TTFT 爆炸；
> ❌ 把整个对话历史拼成一个大 string 存：无法 branch / edit / regenerate；
> ❌ 同步模型推理（一请求一 GPU）：浪费 GPU 70%+；
> ❌ 不做 input moderation：jailbreak / 违法内容直接生成；
> ❌ 把每个用户 session 黏在一台 inference server 上（违反 stateless）。

> [!followup]
> "如何支持 image input（multimodal）？" → 图片走 vision encoder 输出 embedding 拼到 LLM context。"如何 fine-tune per-user？" → LoRA adapter per-user，运行时按 conv_id 加载。"如何监控质量？" → online RLHF logging + A/B test 不同 prompt template。
