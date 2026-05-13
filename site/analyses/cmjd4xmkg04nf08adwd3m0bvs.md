## 题目本质

设计一个 **prompt playground**：用户编写 prompt，**用不同模型 + 不同参数**（temperature、top_p、max_tokens）测试、对比、迭代。代表产品：OpenAI Playground、Anthropic Workbench、Vercel AI Playground。

OpenAI 自家工具，他们最懂。核心考点：**多 model 调用 / 并发 diff 对比 / 模板系统 / 历史版本 / 协作**。

## 需求拆解

**功能性：**
- 编辑 prompt（含 system / user / assistant 多 role messages）
- 选择模型（gpt-4o, gpt-3.5, claude, custom fine-tune）
- 调参数（temp, top_p, max_tokens, stop sequences）
- Run → 流式看到输出
- 多 run 横向对比（同 prompt，不同 model / 参数）
- 保存 prompt template，参数化（`{{variable}}` 替换）
- 版本历史 + 分享 link

**非功能性：**
- 1k 并发用户测 prompt
- 单次 run 流式 < 30s
- 历史保存可追溯

## 整体架构

```ascii
        Browser
           │
           ▼
     ┌─────────────┐
     │   Playground│  React SPA
     │   Frontend  │
     └──────┬──────┘
            │ REST + SSE
            ▼
     ┌──────────────┐
     │  Playground  │
     │  API         │   manage runs, templates, history
     └──┬─────┬─────┘
        │     │
        ▼     ▼
   ┌──────┐  ┌────────────────┐
   │ Tmpl │  │ Run            │  → 流式调底层 LLM
   │ Store│  │ Orchestrator   │
   │ (PG) │  │  (1 run = 1+ models in parallel)
   └──────┘  └─────────┬──────┘
                       │
                       ▼ gRPC
              ┌──────────────────┐
              │ Inference Pool   │ ◀── vLLM / TGI / external API
              │ (multi-model)    │
              └──────────────────┘
                       │
                       ▼ logging
              ┌──────────────────┐
              │ Run History DB   │ Cassandra / Postgres
              │  (prompt + resp +│
              │   tokens + cost) │
              └──────────────────┘
```

## 核心组件

### 1. Prompt Template 系统

```python
class Template:
    id: UUID
    user_id: UUID
    name: str
    version: int
    messages: list[{
        'role': 'system' | 'user' | 'assistant',
        'content': str   # 支持 {{var_name}} 占位
    }]
    variables: list[{'name': str, 'description': str, 'default': str}]
    created_at: datetime
```

**版本化**：每次保存 incr version；旧版本不可改（immutable）。`current_version` 指针指最新。

**渲染**：

```python
import re
def render(template, vars: dict[str, str]) -> list[dict]:
    rendered = []
    for msg in template.messages:
        body = re.sub(r'\{\{(\w+)\}\}', lambda m: vars.get(m.group(1), ''), msg['content'])
        rendered.append({'role': msg['role'], 'content': body})
    return rendered
```

### 2. Run（一次 API 调用）

```python
class Run:
    id: UUID
    template_id: UUID
    template_version: int
    variables: dict
    config: {
        'model': str,
        'temperature': float,
        'top_p': float,
        'max_tokens': int,
        'stop': list[str]
    }
    status: 'pending' | 'streaming' | 'done' | 'failed'
    started_at: datetime
    completed_at: datetime
    rendered_messages: list[dict]   # 已展开的 prompt
    response: str
    finish_reason: str
    usage: {'prompt_tokens': int, 'completion_tokens': int, 'cost_usd': float}
```

### 3. 多 Run 横向对比

UI 上用户可点 "Run with 3 models" → 后端并发发起 3 个 Run，每个独立 stream。前端用 3 列显示 streaming 输出。

```python
async def run_comparison(template_id, variables, configs: list):
    """同一 prompt × N 个 model/param 组合 → 并发"""
    tasks = [run_one(template_id, variables, cfg) for cfg in configs]
    return await asyncio.gather(*tasks)
```

### 4. 流式 + cancel

跟 ChatGPT 设计一样：SSE 推 token；用户点 stop → 关闭连接 → 后端检测到 → cancel 给 inference worker。

### 5. 协作（团队共享 prompt）

- Workspace 概念：一个公司一个 workspace，prompts 默认 workspace-shared
- 权限：owner / editor / viewer
- 实时协作：Yjs / CRDT，多人同时编辑 prompt 看到对方 cursor

### 6. Cost tracking

每 run 写 `cost_usd = prompt_tokens × in_price + completion_tokens × out_price`。汇总到 dashboard per-template、per-user、per-month。

### 7. Eval（如果时间够）

用户可以定义一组 test inputs + expected outputs / criteria，批量跑模板 → 输出 pass rate。这就是 OpenAI Evals 的雏形。

## 取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| 流式协议 | SSE | 单向，简单，浏览器原生支持 |
| Template store | Postgres | 元数据查询友好 |
| Run history | Cassandra | 写量大，按 user_id partition |
| 多模型路由 | API 层适配（OpenAI / Anthropic / 自家 vLLM 一视同仁） | 用户不应感知后端 |
| 协作 | CRDT (Yjs) | 比 OT 简单 |

## 关键技术点

- **Latency 对比**：UI 要显示 TTFT、tok/s、total_latency 三个数；后端在 SSE 第一个 token 时记 TTFT，每隔 N 个 token 算 tok/s
- **Token 计数**：用对应模型的 tokenizer（tiktoken for OpenAI、anthropic counter）实时算 prompt_tokens
- **Diff view**：两个 run 输出做字符 diff，标红删除标绿新增

> [!key]
> 这题面对 OpenAI 面试官，亮点要打在：(1) **并发多 model 对比 + 流式 diff**；(2) **template 版本化**（不要让用户改 prompt 后丢历史）；(3) **token / cost 实时计算**。

> [!pitfall]
> ❌ 把 multi-model 调用做成串行 —— 用户等不了；并发；
> ❌ Template 改了直接覆盖 —— 用户找不回旧版；必须 immutable + version；
> ❌ 不计算 cost —— 用户用着用着收账单傻眼；
> ❌ 不做 input 长度校验 —— 超过 model context window 直接 400。

> [!followup]
> "如何支持 chain-of-thought / multi-turn template？" → template 支持多 turn 占位，运行时按 turn 顺序调；"如何 A/B test？" → eval framework，定 metric（accuracy/cost），跑 prompt 变体；"如何 fine-tune 集成？" → 在 model 选择里加用户自训 model id，path 一样。
