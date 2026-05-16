## 题目本质

**Building a Large-Scale LLM Serving System** (Technical Project Retrospective) —— 这是"讲你做过的一个 specific tech project" 的题。Google 经常用 retrospective format 让候选人 deep dive 一个真实项目。

## Retrospective 框架

不同于 Behavioral STAR，TPR 期望 **technical depth**：
- **Problem & motivation**：why this 项目, who cares
- **Constraints**：scale, latency, budget, deadline
- **Architecture choices** & **alternatives considered**
- **Hard problems** + **how you solved them**
- **Results** + **what you learned**

## 我作为候选人的 sample answer

### Problem

> "去年我 lead 团队 build 内部 LLM serving platform —— 让 dozens of internal teams 在 prod 调用 fine-tuned LLM (GPT-style, 7B-70B params) for low-latency use cases. Before this, each team self-host model on own GPU box, leading to 30% GPU utilization + inconsistent SLO + 6 months ramp-up per team."

### Constraints

- 100k QPS aggregate across teams
- P99 TTFT (time-to-first-token) < 1s
- Multi-tenant: 50+ models served from 1 platform
- Cost: stay within $X budget (5% of total infra budget)
- 6 months to GA

### Architecture choices

> "Chose vLLM as inference engine for continuous batching + PagedAttention. Built around it:
> - gRPC API with streaming
> - Per-model sharding (tensor parallel for 70B)
> - Request scheduler: priority queue + fairness across tenants
> - Adaptive batching: tune batch size based on current load + SLO budget
> - Quantization service: FP16 → INT8 quant offline; serve quantized for cost savings (3x throughput, 2% quality loss)"

### Alternatives considered

> "Considered NVIDIA Triton — strong batching but limited LLM-specific optim. TensorRT-LLM — fastest but Nvidia-only. HuggingFace TGI — similar to vLLM but less mature scheduling. Picked vLLM for openness + continuous batching + active community."

### Hard problems

**Problem 1: GPU memory fragmentation**

> "vLLM's PagedAttention solved most of it, but with 50 different model checkpoints, memory fragmented. Solution: per-GPU dedicated to single model (not multi-tenant per GPU). Trade off utilization for predictability."

**Problem 2: Cold model load latency**

> "Loading 70B model takes 5+ minutes. Users got 'model not ready' errors. Solution: keep top 10 popular models always warm (90% memory budget). Cold models load in background while serving 'fallback' smaller model."

**Problem 3: Fair share across tenants**

> "Heavy user's bursty load could starve other tenants. Implemented token-bucket rate limit per tenant + priority queue. P99 latency tracked per tenant separately."

### Results

> "GA on schedule. 18 teams onboarded in 6 months. GPU utilization went from 30% to 78%. Per-team onboarding time: 6 months → 2 weeks. Total cost down 35% even with 3x load. Platform team won internal engineering excellence award."

### What I learned

> "Three biggest lessons:
> 1. **LLM serving 比 traditional ML serving 难 10x** —— stateful (KV cache), heterogeneous workload (短/长 prompt), stochastic output length。Traditional batching assumes uniform requests.
> 2. **Multi-tenant fairness is harder than performance** —— SRE 同学说 'fairness is just performance with adversaries'。我们花 30% time 在 fairness code.
> 3. **Quantization is critical for cost** —— 3x throughput from quantization is 'free lunch'。所有 serving 系统都该 day-1 quantize."

## 关键展示点

### 1. Technical depth

讲清 vLLM continuous batching / PagedAttention 这类 specific tech。展示你 dig deep。

### 2. Alternatives + reasoning

不只是 "我选 X"，要讲 X vs Y vs Z 比较。证明你 informed decision。

### 3. Hard problems + creative solutions

每个 architecture 都有难点。Show 你 navigate it。

### 4. Quantified impact

GPU util 30% → 78%；cost 35% down；onboarding 6mo → 2wk。Specific numbers。

### 5. Reflection on what 难 + what you learned

Not just "we did it"，而是 "we learned X about LLM serving"。

## 加分项

- **Industry-level reasoning**：比较自己设计 vs OpenAI / Anthropic public 文章
- **失败 / setback**：一个 mid-project 的 wrong turn + recovery
- **People aspect**：mention team dynamics + cross-team negotiation
- **Future plans**：下一阶段 roadmap，what you'd do v2

## 易错点

> [!pitfall]
> ❌ 平铺直叙没 hard problem → 显得 trivial；
> ❌ 不讲 alternatives → 显得没思考；
> ❌ 全 success no failure → 不真实；
> ❌ Tech depth 浅 → 面试官就 unable to 深问；
> ❌ 没数字 / 没 outcome；
> ❌ 故事是 team 做但你 take all credit。

> [!key]
> Tech project retrospective 期望 **deep + honest + concrete**。是 staff/principal 级别的 cornerstone interview。能讲清一个 real production system 的 architecture choices + trade-offs + lessons 是最强 signal.

> [!followup]
> - "If you'd had more time, what would you have built differently?"
> - "What surprised you most?"
> - "How did you decide on vLLM vs TGI specifically?"
> - "What metric mattered most for SLO?"
> - "Did anyone push back on your architecture? What did they say?"
> - "How would you re-design for 10x scale?"
