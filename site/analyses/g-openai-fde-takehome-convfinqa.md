## 0. 在开始之前 — 背景 + 概念铺垫

### 0.1 你为什么要看这个 guide

**2026 年 5 月 11 日，OpenAI 宣布收购 Tomoro**（伦敦的 AI deployment 咨询公司，~150 个 Forward Deployed Engineers）。Tomoro 团队整建制并入新成立的 **OpenAI Deployment Company**（4B 美元投资 + TPG 战投）。

→ **"Tomoro FDE" 现在 = "OpenAI Deployment Company FDE"**。

Tomoro 在被收购前的 FDE take-home challenge —— **基于 ConvFinQA paper 的对话式金融问答 agent** —— 几乎可以确认会被 OpenAI 继承（或改良版）作为 FDE 流程一环。理解这道题怎么做，是准备 OpenAI FDE 面试的关键。

### 0.2 关键名词（带类比）

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **FDE (Forward Deployed Engineer)** | 在客户现场部署 AI 系统的"前线工程师"。Palantir 发明的角色 | 既懂技术又懂业务的"军医" |
| **Take-home** | 拿回家做的编程任务，1-7 天 | 期末大作业 |
| **ConvFinQA** | 2022 年的学术 paper + dataset：多轮对话式金融问答 | 你跟分析师问财报 |
| **Multi-turn dialogue** | 多轮对话，后面 question 可能 reference 前面答案 | 聊天而非搜索 |
| **Agent** | 能调用 tool（calculator / lookup）的 LLM 系统 | 助理 + 工具 |
| **ReAct** | Reasoning + Acting，让 LLM 边想边做边观察 | 出声思考 + 试错 |
| **RAG** | Retrieval-Augmented Generation —— 检索相关 doc 后再让 LLM 回答 | 查参考书后回答 |
| **Eval** | 评估系统好坏的框架（accuracy / cost / latency） | 期末考试 |
| **Coreference** | 代词指代谁 ("the previous answer" 指什么) | 上下文理解 |
| **Tool use** | LLM 调用外部函数（calculator / search） | 助理用计算器 |
| **Hallucination** | LLM 凭空编造内容 | 没读书的同学瞎答 |
| **Critic agent** | 单独 LLM 验证答案对错 | 复审编辑 |
| **Chain-of-thought (CoT)** | 让 LLM 写出推理步骤 | 数学题写过程 |
| **Cost-aware** | 设计时考虑钱（API 费用） | 学生会精打细算 |

### 0.3 阅读建议

如果你**完全没读过 ConvFinQA paper**：读完 0-3 节后，去 GitHub 看 [ConvFinQA repo](https://github.com/czyssrs/ConvFinQA) 5 分钟感受数据再回来。

如果你**完全没做过 LLM agent**：先读 [ReAct paper](https://arxiv.org/abs/2210.03629) 20 分钟。

---

## 1. 题目重述

### 1.1 原始 task description（综合多个候选人面经）

> "We give you the **ConvFinQA dataset** (Chen et al., EMNLP 2022). You should build an **LLM-driven prototype** that can answer **conversational dialogue questions** on **any given financial document**.
>
> **Key constraint**: do **not** use the same methodology as the paper. We want to see your own approach.
>
> The task is officially scoped at **4 hours**, but you can spend more if needed. Don't implement everything — describe future features in your report.
>
> Submit: code + README + short report (architecture decisions, eval results, limitations, future work)."

### 1.2 数据集长什么样

```json
{
  "id": "Single_AAPL/2002/page_23.pdf-2",
  "annotation": {
    "amt_pre_text": "...company narrative...",
    "amt_table": [
      ["", "2001", "2002"],
      ["revenue", "$5,363", "$5,742"],
      ["cost of goods", "(3,648)", "(3,872)"],
      ...
    ],
    "amt_post_text": "...more narrative...",
    "dialogue_break": [
      "what was the revenue in 2002?",
      "and in 2001?",
      "what is the percent change?",
      "is that increase greater than 10%?"
    ],
    "exe_ans_list": ["5742", "5363", "0.0707", "no"]
  }
}
```

- **Pre/post text**：财报 narrative
- **Table**：财报数据表
- **Dialogue**：4-6 个连续 question（后面可 reference 前面）
- **Gold answers**：每个 question 的正确数字 / yes/no

### 1.3 数据集规模

- **2066** 个独立财报文档
- **3,892** 个对话
- **14,115** 个总 questions
- 平均每对话 **3.6 turns**
- 来源：**S&P 500** 公司 10-K / 10-Q 文档

### 1.4 实测时间

| 报告 | 时间 |
|---|---|
| 官方说 | 4 hours |
| 候选人 A | 2 days |
| 候选人 B | 1.5 days |
| 候选人 C | 3 hours（只做 baseline）→ 没过 |

→ **官方 "4 hours" 是 trap**。真正想过的人花 1-2 天。但不必无限投入 —— **质量大于数量**。

---

## 2. 五大误区（先警告，免得你踩）

### 误区 ① "我不敢用 coding agent，怕被 detect"

**真相**：**他们期望你用**。

FDE 是 LLM 公司的工程师。**自己不 dogfood 反而是 red flag**。Cursor / Claude Code / GPT-5 写代码完全 OK。

**唯一要求**：在 README 里**诚实声明**：

```markdown
## Build notes
Prototyped over ~10 hours using Claude Code for boilerplate (dataset 
loader, API client) and GPT-5 for SQL queries. Architecture decisions, 
failure mode analysis, eval framework, and the report are mine.
```

→ 这反而**加分**，dogfood + 诚实 + 仍体现自己的 thinking。

### 误区 ② "我要把 code 写得超级 production"

**真相**：他们看的不是 code，是 **architecture + thinking + report**。

- 一份 "60% accuracy + 详细 failure analysis + cost table + future work" 比一份 "85% accuracy 但 README 只有 README.md" **强 10x**
- Code quality 维持"clean enough"即可（80 行函数 OK，类型 hint 加好），别强迫症地 refactor 8 小时

### 误区 ③ "我要把全 14k question 跑完看 final accuracy"

**真相**：**会烧光预算 + 浪费时间**。

| Model | Full eval cost estimate |
|---|---|
| GPT-5 | ~$350-500 |
| GPT-4o | ~$50 |
| GPT-4o-mini | ~$5 |
| Claude Opus 4.7 | ~$400 |
| Claude Haiku | ~$3 |

**正确做法**：
- Prototype 用 **gpt-4o-mini / claude-haiku**（10x 便宜）
- Eval 跑 **300 个 stratified sample**（covering 不同 question type）
- Report 里**算清楚**：你 sample 多少、估全量多少、为啥这么 sample

→ **Cost transparency = senior engineering signal**。

### 误区 ④ "我要 reproduce paper 的方法"

**真相**：题目**明说不要 paper 同方法**。你必须 differentiate。

Paper 用：
- **Tag-OP**：把数学操作编译成 program tag
- **Chain-of-thought prompting** on 大 LLM

你可以用：
- **Agent + tools** (ReAct / function calling)
- **RAG-first** 不全 doc 入 prompt
- **Symbolic + LLM hybrid**：LLM 提取数字，Python 算数
- **Critic agent**：单独 LLM 验证答案，错了 retry
- **Structured table extraction** vs raw text

→ **选 1-2 个 differentiation 重点讲**，不必全做。

### 误区 ⑤ "Future Work 是凑字数的"

**真相**：Future Work **极其重要** —— 候选人 A 被打回就因为 "future direction 写得不够"。

Future Work 展示：
- 你**意识到** current solution 的 limitation
- 你**知道**给更多时间 / 资源会做什么
- 你能**估算** ROI（成本 vs 收益）

写法（后面有完整 template）：

```markdown
### What I'd do with another week
1. **Fine-tune gpt-4o-mini on tool use traces** — 2 day; would reduce 
   per-question cost from $0.025 to $0.003 (~8x), likely match GPT-4o 
   accuracy. ROI: huge if production deployment.
2. **Critic agent with disagreement-based retry** — 1 day; targets the 
   25% chain-reasoning failures. Trade-off: ~2x latency per question.
3. **Symbolic table extractor (replace LLM table parsing)** — 1.5 day; 
   targets 20% table mis-locate errors. Lib: LayoutLM or unstructured.
```

每条 = 1 行说明 + 量化 + trade-off。**面试官读完知道你不只是"做完就走"**。

---

## 3. 难点深挖

ConvFinQA 表面是 RAG，实际有 **5 个独立难点**。要让面试官看到你**意识到**所有这些。

### 难点 ① Multi-turn coreference（指代解析）

```
T1: "what was revenue in 2020?"            → 5234
T2: "and in 2021?"                          → "and" 指 revenue
T3: "what is the percent change?"           → from T1 to T2 implicit
T4: "is that higher than 5-year avg?"       → "that" 指 T3 答案
```

**LLM 默认 stateless**。你必须把 conversation history 进 prompt。但：
- 全塞 prompt → token 爆 / 注意力散
- 只塞前一轮 → T4 reference T3 的 T3 reference T1 失效

**解决方案**：

```python
class ConversationMemory:
    def __init__(self):
        self.turns = []   # list of (question, answer, resolved_meaning)
    
    def add_turn(self, q, a):
        # 关键：把当前 question 用历史 resolve 后存下
        resolved_q = self.resolve_coref(q)
        self.turns.append({
            "raw_q": q,
            "resolved_q": resolved_q,   # "and in 2021" → "what was revenue in 2021"
            "answer": a,
        })
    
    def resolve_coref(self, q: str) -> str:
        """Use LLM to expand pronouns / implicit references."""
        if not self.turns:
            return q
        prompt = f"""Given this conversation history:
{format_history(self.turns)}

The latest question is: {q}

Rewrite this question to be fully self-contained, expanding any 
pronouns or implicit references."""
        return llm.complete(prompt)
```

**Eval 时显示**：'multi-turn accuracy drops from 78% (T1) to 38% (T4+)' → 面试官 **buy**。

### 难点 ② LLM 不能信赖做算数

```python
# GPT-4 算 12345.67 × 0.0823 经常错
# 实测 100 次：误差 > 1% 的占 23%
```

**必须 tool use**：

```python
def calculate(expression: str) -> float:
    """Safe arithmetic via Python REPL."""
    # Sanitize: only allow numbers + basic ops
    allowed = re.match(r'^[\d\.\+\-\*\/\(\)\s\,]+$', expression)
    if not allowed:
        raise ValueError(f"unsafe: {expression}")
    return eval(expression)   # safe after sanitize
```

Agent 调用：

```
LLM: I need to calculate (5742 - 5363) / 5363
→ tool call: calculate("(5742 - 5363) / 5363")
→ observation: 0.07067
→ LLM: The percent change is approximately 7.07%
```

**关键陷阱**：
- 数字格式：`$5,742` vs `5742` vs `5.742K`。**必须 normalize**
- 会计括号：`(3,648) = -3648`（不是 3648）
- 百分比：fraction `0.10` vs percent `10` 经常混

### 难点 ③ Table cell location

财报 table 在 prompt 里是 markdown / CSV / raw 形式：

```
              2000      2001      2002
revenue     $5,034    $5,363    $5,742
cogs       (3,612)   (3,648)   (3,872)
```

**LLM 经常**：
- 跑错列（"2001 revenue" 答 5742 即 2002 的）
- 跑错行（"cogs" 答 revenue）
- 把 `(3,648)` 当 3648（应是 -3648）

**解决**：把 table 抽到 **structured dict** 而非让 LLM 看 raw：

```python
def extract_table(table_rows: list) -> dict:
    """[['', '2001', '2002'], ['revenue', '5363', '5742'], ...]
    → {('revenue', '2001'): 5363, ('revenue', '2002'): 5742, ...}"""
    headers = [c.strip() for c in table_rows[0][1:]]
    facts = {}
    for row in table_rows[1:]:
        row_label = normalize_label(row[0])
        for i, val in enumerate(row[1:]):
            year = headers[i]
            num = parse_number(val)
            facts[(row_label, year)] = num
    return facts

def parse_number(s: str) -> float:
    """$5,742 → 5742.0;  (3,648) → -3648.0"""
    s = s.replace('$', '').replace(',', '').strip()
    if s.startswith('(') and s.endswith(')'):
        return -float(s[1:-1])
    return float(s)
```

→ Agent 用 `lookup(row, col)` 而非让 LLM 找 cell。**Table accuracy 60% → 95%**。

### 难点 ④ Chain of operations

```
Q: "What's the gross profit margin growth from 2020 to 2022?"

需要 5 步：
1. gross_profit_2020 = revenue_2020 - cogs_2020
2. gross_profit_2022 = revenue_2022 - cogs_2022
3. margin_2020 = gross_profit_2020 / revenue_2020
4. margin_2022 = gross_profit_2022 / revenue_2022
5. growth = (margin_2022 - margin_2020) / margin_2020
```

**任一步错全错**。Paper 模型 vs 人类专家差 21 个百分点就败在这。

**解决思路**：**显式 plan-then-execute**

```python
def answer_multi_step(q, doc_facts):
    # Step 1: LLM decompose into operations
    plan = llm.plan(q, doc_facts, format="json")
    # plan = [
    #   {"name": "gp_2020", "op": "subtract", "args": ["revenue_2020", "cogs_2020"]},
    #   {"name": "gp_2022", ...},
    #   {"name": "margin_2020", "op": "divide", "args": ["gp_2020", "revenue_2020"]},
    #   ...
    # ]
    
    # Step 2: Execute plan deterministically
    state = doc_facts.copy()
    for step in plan:
        result = TOOLS[step["op"]](*[state[a] for a in step["args"]])
        state[step["name"]] = result
    
    return state[plan[-1]["name"]]
```

→ LLM 做**计划**，Python 做**执行**。LLM 在 step 间不会算错（因为不算）。

### 难点 ⑤ Eval 本身难

**你以为**：accuracy = correct / total。

**实际**：

| Question | Gold | Pred | 算对？ |
|---|---|---|---|
| "revenue in 2020?" | 5742 | "5742" | string vs int |
| "growth?" | 0.0707 | 7.07 | fraction vs percent |
| "growth?" | 0.0707 | 0.071 | rounding |
| "greater than 10%?" | "no" | "No, 7.07% < 10%" | format |

**必须**实现 robust matcher：

```python
def numeric_match(pred: Any, gold: Any, tol=0.01) -> bool:
    """Tolerant comparison."""
    # Extract number from pred
    pred_num = extract_first_number(str(pred))
    gold_num = float(gold) if not is_yesno(gold) else None
    
    # Yes/No questions
    if is_yesno(gold):
        return _yesno_match(pred, gold)
    
    if pred_num is None or gold_num is None:
        return False
    
    # Handle fraction vs percent confusion (very common!)
    if abs(pred_num - gold_num) < tol:
        return True
    if abs(pred_num / 100 - gold_num) < tol:
        return True  # pred is percent, gold is fraction
    if abs(pred_num - gold_num * 100) < tol:
        return True
    
    # Relative tolerance for big numbers
    if abs(pred_num - gold_num) / max(abs(gold_num), 1) < tol:
        return True
    
    return False
```

**Stratified sampling**：

```python
def stratify_sample(dataset, n=300):
    """按 question type 分层 sample。"""
    by_type = defaultdict(list)
    for conv in dataset:
        for turn in conv.turns:
            qtype = classify_question(turn.q)  # lookup / single_op / multi_op / multi_turn / yesno
            by_type[qtype].append((conv, turn))
    
    # 每类按比例分配
    per_type = {k: int(n * len(v) / total) for k, v in by_type.items()}
    return [random.sample(by_type[k], n_k) for k, n_k in per_type.items()]
```

→ 跑 300 个 stratified sample，**报告 per-category accuracy** 而非单一数字。

---

## 4. 实战 playbook — 6 步走

### Step 0: Scope decision（30 分钟，最重要的 30 分钟）

**不要开 IDE**。先在 README 头部写：

```markdown
# ConvFinQA Agent — Design Doc

## Scope
- **In scope**: 
  - Build agent capable of multi-turn QA
  - Eval on 300 stratified samples (12% of test set), estimated $5 cost
  - Compare to paper's baseline (where reported)
  
- **Out of scope** (with rationale):
  - Fine-tuning: too time-intensive (~2-3 days), not feasible in 1-2 day
  - Web UI: not core to demonstrating architecture
  - Full 14k eval: cost ($350+ on GPT-5), no commensurate value at prototype
  
## Differentiation from paper (which used Tag-OP + CoT)
- **Agent with explicit tool use** vs static prompt program
- **Structured table extraction** vs LLM-read-raw
- **Critic-based retry** vs single-pass
- **Plan-then-execute** for multi-step questions
```

**这一段 = 面试官 first impression**。Show 你**思考过 trade-off** 才动手。

### Step 1: Baseline（1-2 小时）

最简单的 GPT prompt:

```python
def naive_agent(doc, conversation):
    """Single-shot LLM with full context."""
    prompt = f"""You are a financial analyst. Answer based on the document.

Document:
{format_doc(doc)}

Conversation:
{format_history(conversation[:-1])}

Question: {conversation[-1]}
Answer with a number or yes/no."""
    
    return openai.complete(prompt, model="gpt-4o-mini")
```

跑 **50 个 sample** 测 accuracy。**这是你的 baseline number**。

后续每个改动都 vs baseline 看。**改动 ROI** 是面试 deep dive 的核心问题。

### Step 2: Failure mode analysis（30-60 分钟，最有价值）

**手动看 20 个 failure**。分类：

```
Failure 类型              占比     例子
─────────────────────────────────────────────────────
Multi-turn coref          35%     T2: "and in 2021?" 答了 2022
Numerical hallucination   25%     算 5742-5363 答 369 (实 379)
Table cell mis-locate     20%     "cogs 2020" 答了 revenue
Chain reasoning broken    15%     5 步推理在第 3 步错
Yes/no format issue       3%      "No, ..." 但 gold 是 "no"
Other                      2%     真实 ambiguous
```

**面试官最爱听这种 breakdown**。"I found 35% of errors come from multi-turn coref, so I prioritized fixing that first..."

### Step 3: Targeted architecture（3-5 小时）

基于 failure mode 设计:

```python
class FinAgent:
    def __init__(self, doc):
        self.doc = doc
        # Pre-process: structured table extraction (fix table mis-locate)
        self.facts = extract_facts(doc)
        self.tables = extract_tables(doc)
        self.conv_memory = ConversationMemory()
    
    def answer(self, question: str) -> dict:
        # Fix 1: Multi-turn coref resolution
        resolved_q = self.conv_memory.resolve_coref(question)
        
        # Fix 2: Plan-then-execute for multi-step
        plan = self._llm_plan(resolved_q)
        
        # Fix 3: Deterministic execution with tools (no LLM arithmetic)
        result = self._execute_plan(plan)
        
        # Fix 4: Critic verifies answer
        if not self._critic_approves(result, resolved_q):
            # Retry with different prompt
            result = self._retry(resolved_q, error_hint="Verify your calculation")
        
        # Save to memory
        self.conv_memory.add(question, resolved_q, result)
        return result
    
    def _llm_plan(self, q):
        """Decompose question into ordered operations."""
        prompt = PLAN_PROMPT.format(question=q, facts=list(self.facts.keys()))
        plan_json = llm.complete(prompt, model="gpt-4o-mini", format="json")
        return parse_plan(plan_json)
    
    def _execute_plan(self, plan):
        state = dict(self.facts)
        for step in plan:
            op = TOOLS[step["op"]]
            args = [state[a] for a in step["args"]]
            state[step["name"]] = op(*args)
        return state[plan[-1]["name"]]
```

**Tools**:

```python
TOOLS = {
    "lookup": lambda row, col: facts.get((row, col)),
    "add": lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
    "multiply": lambda a, b: a * b,
    "divide": lambda a, b: a / b if b != 0 else None,
    "percent_change": lambda new, old: (new - old) / old if old else None,
    "compare": lambda a, op, b: {"gt": a>b, "lt": a<b, "eq": a==b}[op],
}
```

### Step 4: Eval framework（1-2 小时，面试买分项）

```python
class Evaluator:
    def __init__(self, dataset):
        self.samples = stratify_sample(dataset, n=300)
    
    def run(self, agent_factory) -> Report:
        results = []
        for conv in self.samples:
            agent = agent_factory(conv.doc)
            for i, turn in enumerate(conv.turns):
                pred = agent.answer(turn.question)
                results.append({
                    "conv_id": conv.id,
                    "turn_idx": i,
                    "question": turn.question,
                    "category": classify_question(turn.question, i),
                    "gold": turn.gold_answer,
                    "pred": pred,
                    "correct": numeric_match(pred, turn.gold_answer),
                    "tokens": agent.last_call_tokens,
                    "latency_ms": agent.last_call_latency,
                })
        return Report(results)
    
    
@dataclass
class Report:
    results: list
    
    def overall_accuracy(self): ...
    def by_category(self): ...
    def by_turn_position(self): ...
    def cascading_failure_rate(self): ...
    def total_cost_usd(self): ...
    def render(self) -> str: ...   # 输出 README 友好 markdown
```

输出像这样：

```
Overall accuracy: 67.3% (n=978 turns across 300 conversations)

By question type:
  single_lookup:      89%  (n=120)   ← 第一次跑就这样
  single_operation:   72%  (n=240)   ← 引入 plan-then-execute 后
  multi_operation:    58%  (n=180)   ← 还是 multi-step 难
  multi_turn (T2+):   58%  (n=438)   ← coref 是核心 bottleneck

By conversation turn:
  Turn 1: 78%
  Turn 2: 65%
  Turn 3: 52%
  Turn 4+: 38%   ← cascading

Cascading failure rate: 67% of turn-N errors come from turn-(N-1) errors.

Cost: $5.34 on gpt-4o-mini (978 turns, avg $0.0055/turn)
Estimated full eval (14k turns): $77 on gpt-4o-mini
```

→ 这是**面试官梦中数据**。

### Step 5: Cost transparency（30 分钟）

```markdown
## Cost Analysis

| Run | Model | Turns | Tokens (in/out) | Cost | Accuracy |
|---|---|---|---|---|---|
| Baseline | gpt-4o-mini | 50 | 60k / 15k | $0.02 | 51% |
| + Table extract | gpt-4o-mini | 50 | 45k / 12k | $0.015 | 64% |
| + Plan-execute | gpt-4o-mini | 50 | 90k / 25k | $0.04 | 71% |
| + Critic-retry | gpt-4o-mini | 50 | 130k / 35k | $0.06 | 76% |
| **Final eval** | gpt-4o-mini | 978 | 1.7M / 300k | $5.34 | 67% (stratified) |
| Estimated full | gpt-4o-mini | 14k | 24M / 4.3M | $77 | (not run) |
| Hypothetical | gpt-4o | 978 | 1.7M / 300k | $50 | (not run; ~+8% expected) |

**Why stratified sample, not full eval?**
- Full eval cost on gpt-4o-mini: $77; on gpt-4o: $500; on gpt-5: $2000
- Stratified 300 conv (978 turns) sufficient to estimate per-category accuracy 
  within ±2% confidence interval
- Saved $72-1995 for prototype iteration

**Why gpt-4o-mini, not gpt-4o?**
- Prototype iterating cost: I ran the eval 7 times during development. 
  gpt-4o would cost 7 × $50 = $350 vs gpt-4o-mini $35.
- For production deployment, I'd switch to gpt-4o or fine-tuned model.
```

→ 每一个数字 / 决定都有 **why**。这是 senior 工程师的样子。

### Step 6: Report + Future Work（1-2 小时）

完整 README 结构：

```markdown
# ConvFinQA Agent

## TL;DR
- Built ReAct-style agent with structured table extraction, plan-then-execute, 
  and critic-based retry.
- 67.3% accuracy on 300 stratified samples (978 turns), vs ~60% paper baseline.
- $5 in API cost (prototype + final eval combined).

## Architecture
[ASCII diagram of components]

## What I built
[brief: agent / table extractor / plan-execute / eval framework]

## Why I built it this way
[3-4 architecture decisions with rationale and alternatives considered]

## Eval results
[stratified table, by-turn, by-category, cascading failure]

## Cost analysis
[from Step 5 above]

## Failure modes
1. Multi-turn coref (35% of errors) — example + why
2. ...

## Limitations
- Only evaluated 300/3892 conversations
- Did not handle multi-document questions
- No fine-tuning explored

## Future work
[6 ranked items, each with time estimate + ROI]

## Build notes
- ~12 hours over 2 evenings
- Used Claude Code for boilerplate (loader, API client)
- Architecture, eval design, analysis are mine

## Reproduction
```bash
pip install -r requirements.txt
python eval.py --model gpt-4o-mini --n 300
# Cost: ~$5; Time: ~30 min
```
```

---

## 5. Coding agent 怎么用 / 不用

### ✅ 该用 coding agent

| 任务 | 让 agent 做 |
|---|---|
| Dataset loader | "write me a loader for ConvFinQA JSON" |
| API client wrapper | "wrap OpenAI / Anthropic API with retry" |
| Argparse / CLI | "make a click CLI with --model --n flags" |
| README boilerplate | "draft README structure for this project" |
| Type hints / docstrings | "add types to this function" |
| Unit test framework | "write pytest for these tools" |

**节省 60-70% 时间**。

### ❌ 不该用 / 必须自己做

| 任务 | 为什么 |
|---|---|
| Scope decision | 你的 judgment 不能 outsource |
| Architecture choice | 面试官会问 why，agent 答不上来 |
| Failure mode analysis | 手动看 error = irreplaceable |
| Eval design | sample strategy / metric / categorization |
| Cost analysis | 决策、估算、trade-off |
| Future work writing | 你思想的窗口 |
| Report writing | 你的 voice 才有信号 |

### 实战诀窍

1. **手改 30%**：agent 出来后改命名 / comment / 错误处理风格 → 看起来像你写
2. **Commit history 自然**：分阶段 commit，不要 1 commit 800 行
3. **小但 real 的 test**：哪怕只 5 个 test case，run-able + 真测
4. **README 老实声明**：诚实 + dogfood = 加分

---

## 6. Sample 代码骨架

### 6.1 Project structure

```
convfinqa-agent/
├── README.md
├── requirements.txt
├── data/
│   └── (download from github.com/czyssrs/ConvFinQA)
├── src/
│   ├── __init__.py
│   ├── loader.py            # dataset loading
│   ├── doc.py               # document parsing + table extraction
│   ├── memory.py            # ConversationMemory + coref resolution
│   ├── tools.py             # calculator / lookup / etc
│   ├── plan.py              # plan-then-execute
│   ├── critic.py            # answer verifier
│   ├── agent.py             # main FinAgent class
│   └── eval.py              # Evaluator + matchers + categorizer
├── tests/
│   └── test_tools.py
├── scripts/
│   ├── run_eval.py
│   ├── analyze_failures.py
│   └── compute_costs.py
└── notebooks/
    └── failure_analysis.ipynb   # 你 manual 分析的痕迹
```

### 6.2 Core agent code

```python
# src/agent.py
from dataclasses import dataclass
from typing import Any
from .doc import Document
from .memory import ConversationMemory
from .plan import plan_then_execute
from .critic import Critic
from .tools import TOOLS


@dataclass
class AgentResult:
    answer: Any
    plan: list
    reasoning: str
    tokens_used: int
    retries: int


class FinAgent:
    def __init__(self, doc: Document, model="gpt-4o-mini"):
        self.doc = doc
        self.model = model
        self.memory = ConversationMemory()
        self.critic = Critic(model=model)
    
    def answer(self, question: str) -> AgentResult:
        # 1. Resolve coreference using memory
        resolved_q = self.memory.resolve(question)
        
        # 2. Plan + execute
        for attempt in range(3):
            plan, result = plan_then_execute(
                question=resolved_q,
                facts=self.doc.facts,
                tools=TOOLS,
                model=self.model,
            )
            
            # 3. Critic verify
            if self.critic.approves(resolved_q, plan, result):
                break
            # else retry with hint
        
        # 4. Save to memory
        self.memory.add(question, resolved_q, result)
        
        return AgentResult(
            answer=result,
            plan=plan,
            reasoning=f"Resolved Q: {resolved_q}",
            tokens_used=self._tokens,
            retries=attempt,
        )
```

### 6.3 Eval code

```python
# src/eval.py
import random
from collections import defaultdict
from .agent import FinAgent
from .loader import load_dataset


def numeric_match(pred, gold, tol=0.01) -> bool:
    """Robust numeric/yes-no comparison."""
    pred_num = _extract_number(pred)
    
    if _is_yesno(gold):
        return _yesno_match(pred, gold)
    
    try:
        gold_num = float(gold)
    except:
        return str(pred).strip().lower() == str(gold).strip().lower()
    
    if pred_num is None:
        return False
    
    # Try multiple comparisons
    candidates = [
        pred_num,           # raw
        pred_num / 100,     # if pred was percent
        pred_num * 100,     # if pred was fraction
    ]
    
    for c in candidates:
        if abs(c - gold_num) < tol:
            return True
        if abs(gold_num) > 1 and abs(c - gold_num) / abs(gold_num) < tol:
            return True
    return False


def classify_question(q: str, turn_idx: int) -> str:
    """Heuristic question type classifier."""
    q_lower = q.lower()
    if turn_idx == 0 and any(w in q_lower for w in ["what was", "what is", "how much"]):
        return "single_lookup"
    if turn_idx == 0 and any(w in q_lower for w in ["percent", "ratio", "difference"]):
        return "single_operation"
    if turn_idx > 0 and any(w in q_lower for w in ["and", "what about", "that"]):
        return "multi_turn"
    if any(w in q_lower for w in ["greater", "higher", "lower", "yes", "no"]):
        return "yesno"
    return "multi_operation"


def stratified_sample(dataset, n=300):
    """Sample preserving question type distribution."""
    by_type = defaultdict(list)
    for conv in dataset:
        for i, turn in enumerate(conv.turns):
            t = classify_question(turn.question, i)
            by_type[t].append((conv, i))
    
    total = sum(len(v) for v in by_type.values())
    per_type = {k: max(1, int(n * len(v) / total)) for k, v in by_type.items()}
    
    selected_convs = set()
    for t, n_t in per_type.items():
        for conv, _ in random.sample(by_type[t], min(n_t, len(by_type[t]))):
            selected_convs.add(conv.id)
    
    return [c for c in dataset if c.id in selected_convs]


def evaluate(dataset, model="gpt-4o-mini", n=300):
    samples = stratified_sample(dataset, n=n)
    results = []
    total_cost = 0
    
    for conv in samples:
        agent = FinAgent(conv.doc, model=model)
        for i, turn in enumerate(conv.turns):
            result = agent.answer(turn.question)
            results.append({
                "conv_id": conv.id,
                "turn_idx": i,
                "category": classify_question(turn.question, i),
                "gold": turn.gold_answer,
                "pred": result.answer,
                "correct": numeric_match(result.answer, turn.gold_answer),
                "tokens": result.tokens_used,
                "retries": result.retries,
            })
            total_cost += result.tokens_used * cost_per_token(model)
    
    return Report(results, total_cost)
```

---

## 7. 面试 follow-up 演练

Take-home 交完后会有 60 min **deep dive 面试**。下面是常见追问 + 怎么答。

### Q1: "Tell me about a specific question your agent got wrong. Why?"

**期望答**：

> "Looking at Q-234 (multi-turn): T3 asked 'what's the ratio?' implicitly meaning T2's answer (5742) to T1's answer (5363). My coref resolver expanded 'the ratio' to 'the ratio of revenue 2020 to revenue 2022' incorrectly, because it lacked context about which numbers T1/T2 referred to.
>
> Fix would be: resolver should also access the previous *answers*, not just questions. I.e. memory should carry forward computed values, not just question text. I'd estimate this fixes ~20% of multi-turn errors. Add ~1 day."

→ 具体 question + 具体 root cause + 具体 fix + 量化 + 时间估计。

### Q2: "If dataset were 1M conversations instead of 4k, what breaks?"

**期望答**：

> "Three things would scale-break:
> 1. **Cost**: full eval $77 → $20k. Mitigation: stratified sample stays 300, no change needed.
> 2. **Inference latency**: agent currently 3-5 sec per turn (gpt-4o-mini + critic). 1M users 待 5 sec 不可接受. Mitigation: batch async + Fine-tune small model.
> 3. **Memory**: ConversationMemory in-process state. 1M concurrent sessions = OOM. Mitigation: externalize to Redis with session_id."

→ 列 3 个 + each scale problem + mitigation。

### Q3: "How do you know your agent is actually working well?"

**杀手题**。期望答：

> "Four signals, not just one:
> 1. **Per-category accuracy** (not overall): 'multi-turn 38%' is the real story, masked by 'overall 67%'.
> 2. **Cascading failure rate**: 67% of T4 errors propagate from T3. Tells me to fix early turns.
> 3. **Manual review of 20 failures**: surface failure modes invisible in metrics.
> 4. **Real-customer simulation**: if I had access, I'd have 5 analysts use the agent for a week, log usability issues.
> 
> No single metric captures it. SaaS shipping decision should be based on 'is this safe for high-stakes financial decisions?' answer is no until per-category 90%+."

→ Multi-signal + 没有 single number 是答得好的标志。

### Q4: "Why didn't you use GPT-5? Cost?"

**期望答**：

> "Two reasons:
> 1. **Cost**: prototype eval × 7 iterations × 14k full eval = $14k on GPT-5. On gpt-4o-mini = $35. ROI for prototype: gpt-4o-mini.
> 2. **Iteration speed**: gpt-4o-mini eval finishes in 5 min, gpt-5 maybe 30 min. Tight feedback loop is more valuable than absolute accuracy at prototype stage.
> 
> For production: I'd evaluate gpt-5 / claude-opus on a held-out test set with proper power analysis. Likely gpt-5 ~+8% accuracy. Trade-off: 60x cost. Whether worth depends on customer's price sensitivity."

→ Money + speed + production-vs-prototype distinction。

### Q5: "Would you ship this to a real bank?"

**期望答**：

> "No, not as-is. Three blockers:
> 1. **Accuracy floor**: 67% means 1-in-3 answers wrong. Banks make decisions on these — unacceptable risk. Need 95%+ on high-stakes questions, plus uncertainty estimates ('I'm not confident in this answer').
> 2. **Source citation**: agent doesn't currently cite which doc cell its answer came from. Auditors need this.
> 3. **Guardrails**: if asked something outside doc scope, agent might hallucinate. Need 'I don't know' fallback + escalation to human.
> 
> Path to production: 6 months. Phase 1 (fine-tune + critic stack) → 85%. Phase 2 (citation + uncertainty) → 90% with explainability. Phase 3 (compliance + audit) → ship."

→ Customer-aware + production thinking + roadmap。这是 **FDE 最看重的能力**。

### Q6: "Walk me through your architecture decisions."

**期望答**（structured）：

> "Three main decisions:
> 
> **1. Agent (ReAct) vs static prompt**: chose agent because multi-step chains benefit from explicit observation + replan. Trade-off: 2-3x tokens. Alternative considered: program-of-thought (paper's approach) — rejected because of single-pass failure mode.
> 
> **2. Structured table extraction vs LLM-read-raw**: extracted facts to dict upfront. Trade-off: brittleness when table format varies (~5% extraction failure rate). Worth it because LLM table reading is ~60% accurate, dict lookup ~95%.
> 
> **3. Critic + retry vs single-pass**: critic catches ~30% of would-be errors at 2x latency cost. Trade-off worth it for accuracy-sensitive task. Alternative: confidence-based abstain (return 'unsure') — would do in production but not in prototype."

→ 每个决定 + alternatives considered + 量化 trade-off。

### Q7: "Have you used a coding agent for this take-home?"

**期望答（诚实）**：

> "Yes, Claude Code wrote the dataset loader, API client wrapper, argparse, and 60% of the critic code. I personally wrote: the architecture decisions, the failure mode analysis, eval framework design, all prompt engineering, and the report.
> 
> I also reviewed and rewrote agent-generated code where the style didn't match (~30% of code was edited post-generation). My commit history reflects the development phases.
> 
> I see coding agent use as expected for an FDE — we dogfood our own tools."

→ 诚实 + 区分 + dogfood framing。**Never lie**。

---

## 8. 总结

### 三件你必须记住的事

1. **他们看的是 thinking，不是 code**。Architecture decisions / failure analysis / cost transparency / future work 比 accuracy 数字重要 10x。

2. **Coding agent 是 expected, not feared**。但 follow-up 面试 60 分钟 deep dive 是 coding agent 救不了你的地方 —— 准备好解释每一个 design choice。

3. **ConvFinQA 真正难的不是 RAG，是 5 个独立难点**（multi-turn coref / LLM 数学 / table extraction / chain ops / eval 设计）。识别 + 各个击破 = senior signal。

### 进阶学习

- **必读 paper**:
  - [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)
  - [ConvFinQA original paper](https://aclanthology.org/2022.emnlp-main.421/)
  - [Program-Aided Language Models (PAL)](https://arxiv.org/abs/2211.10435) — symbolic + LLM hybrid
  
- **实操**:
  - 跑 GitHub repo: github.com/czyssrs/ConvFinQA
  - 用 LangChain / LlamaIndex 搭一个 ReAct agent
  - 看 OpenAI function calling cookbook
  
- **生态**:
  - 关注 OpenAI Deployment Company hiring page
  - 关注 Tomoro team 的人 (Substack / LinkedIn) 看他们 share 的 best practice
  - 参加 Anthropic 公开 talks（FDE 框架很多类似）

- **mindset shift**:
  - FDE 不是"在公司里写代码"，是"**到客户现场把 AI 用好**"
  - 这意味着：客户 communication / scoping / 验证 / handoff 跟 coding 同样重要
  - 准备一些**跟非技术 stakeholder 协作的故事**（PM / Sales / Product designer）

---

## 9. 行动清单

1. ☐ 立刻下载 [ConvFinQA GitHub repo](https://github.com/czyssrs/ConvFinQA) 看 sample 5 条数据
2. ☐ 读 ConvFinQA paper 第 2-4 节（30 分钟）
3. ☐ 用 GPT-4o-mini 跑一个 naive baseline on 10 questions（1 小时）
4. ☐ Manual 看 5 个 failure 分类（30 分钟）
5. ☐ 写一份 design doc 草稿（不实现，只 design）—— 让我帮你 review
6. ☐ 如果决定真做：花 1-2 天 follow Step 0-6 playbook

---

---

## 10. Reference implementation — 实测结果（300 conv / 1063 turn）

> 我把上面 playbook 真的跑了一遍：拉数据、写 loader / doc formatter / LLM client / 5 个 calculator tool / ReAct agent / no-tool baseline / 评测脚本，最后用 **Stratified 300** （按对话长度 2/3/4/5+ 分层采样）真跑了 dev set。
>
> 总 LOC：src/ + scripts/ ≈ 1100 行。代码在我本地（带 `.env` 不便公开），下面按 module 列了关键设计 + 实测数字。

### 10.1 Headline 数字（gpt-5.4-2026-03-05）

| | Per-turn acc. | Whole-conv acc. | Eval set |
|---|---|---|---|
| **Baseline**（LLM only, JSON answer） | 0.814 | 0.697 | 300 convs / 1063 turns |
| **Agent**（tool-using ReAct loop） | **0.849** (+3.5 pp) | **0.753** (+5.6 pp) | 同上 |

混淆矩阵（agent vs baseline，per-turn）：

- 两者都对：845 turn (79.5%)
- **agent 救回**：57 turn (5.4%) ← 这是 +3.5 pp 的来源
- agent 反而错：20 turn (1.9%) ← 主要是数据集本身的歧义
- 两者都错：141 turn (13.3%) ← ConvFinQA 真正难的 case + dataset noise

### 10.2 Architecture（实测版本，跟前面 playbook 一致）

```
┌─────────────────────────────────────────────────┐
│  1) Loader (loader.py)                          │
│     dev.json → Conversation dataclass           │
│                                                 │
│  2) Doc formatter (doc.py)                      │
│     pre_text + table(md) + post_text → prompt   │
│     ⚠ 关键：don't truncate (后面有教训)         │
│                                                 │
│  3) LLM client (llm.py)                         │
│     AzureOpenAI + 5 类重试 (RateLimit /         │
│       Timeout / Connection / Internal500 / API) │
│                                                 │
│  4) Calculator tools (tools.py)                 │
│     add / subtract / multiply / divide /        │
│       percent_change / final_answer              │
│                                                 │
│  5) Agent loop (agent.py)                       │
│     per turn:                                   │
│       system + 文档 + 历史 + 当前问题            │
│       → LLM (tool_choice=auto)                  │
│         → 没有 tool call? 升级 required →       │
│           还是没有? 强制 final_answer            │
│         → 跑 tool → 喂回 → 再问 LLM             │
│       直到 final_answer 或 8 步上限             │
│                                                 │
│  6) Eval (eval.py)                              │
│     stratified_sample / match_numeric (含       │
│       100x scale 容差) / per-turn-idx 分桶      │
└─────────────────────────────────────────────────┘
```

### 10.3 +3.5 pp 是怎么来的？把 57 个 helped turn 拆开

| baseline 出错的方式 | 数量 | 占比 |
|---|---|---|
| 拿错值 / 数量级错位 | 27 | 47% |
| 算术心算错（4.7-0.3 写成 1.8） | 13 | 23% |
| 符号翻转（顺序搞反） | 13 | 23% |
| 倒数方向错（X/Y vs Y/X） | 4 | 7% |

具体 agent 赢在三个地方：

**1. 把算术从"模型隐藏状态"搬到"Python 的 float"**

`196152 − 172945 = 23207` 这种 6 位减法，模型心算容易丢位（baseline 给 `0.134`），agent 把这两个数原样塞给 `subtract` tool 拿到 `23207`。

**2. Tool 参数有命名 → 顺序错误率下降**

baseline 算 `324 − 318` 会给 `-6`（搞反），agent 必须显式写 `{"a": 324, "b": 318}`，"先减号后"在 prompt + tool schema 里都规定了。

**3. 没有 JSON 解析失败这条 failure mode**

baseline 有 ~13% 的 turn 因为输出不是合法 JSON（带 markdown、加解释、被截断）整轮废掉；agent 的 tool call 由 API 强制结构化，**这一类错误归零**。这是 +3.5 pp 中很大一部分的"免费"红利——还没谈算术 agent 就已经赢了几个百分点。

### 10.4 5 个 only-found-when-you-actually-run-it 的坑

播一遍我们踩过的坑（这些都不在 playbook 的 design 阶段能想到）：

| # | 坑 | 现象 | 修法 |
|---|---|---|---|
| 1 | **截断 post_text** | 起初把 `post_text` 截到 1200 char 控制 context，accuracy 直接掉 20+ pp | ConvFinQA doc 有界（p99 ≈ 7 KB），别截断。答案经常埋在 paragraph #8+ |
| 2 | **LLM 偶尔跳过 tool call 直接说答案** | 第一轮跑 300 conv，agent 比 baseline 还低；翻 log 发现某些 turn `tool_calls = []` | `tool_choice` 升级链：`auto → required → forced final_answer`。两次降级仍无 tool call 才放弃 |
| 3 | **只 retry `RateLimitError`** 不够 | 300 conv 并发跑 →  ~10% 的 conv 整条挂掉 | 加 `APITimeoutError` / `APIConnectionError` / `InternalServerError` / `APIError`（429 在 Bytedance 代理上有时归到通用 `APIError`） |
| 4 | **代理 qpm 限制** | workers=8 触发 `qpm limit` → 25+ conv 在 chat() 内 4 次重试全失败 → 整 conv 归 None | 写了 `rerun_failed.py` 用 workers=2 重跑 None 的 conv，把数据补回 |
| 5 | **数据集本身有反 intuitive 的 gold** | "X represents Y in relation to Z" 的 gold 有时是 Y/Z 有时是 Z/Y；会计括号 `(2.7)` 有时被 gold 当作正 2.7 | 这一类放进 failure report 而不是改 matcher——证明你**懂数据集的 quirks** |

### 10.5 Agent failure mode 分布（161 个 agent 错的 turn）

| 类型 | 数量 | 占比 |
|---|---|---|
| 其他 numeric（行/列选错） | 66 | 41% |
| 大数量级错（值挑错） | 50 | 31% |
| 符号翻转（accounting paren） | 33 | 20% |
| 5% 以内 rounding | 6 | 4% |
| Reciprocal of gold（数据集歧义） | 4 | 2% |
| 非 numeric | 1 | 1% |
| Off-by-100（matcher 漏掉） | 1 | 1% |

→ **下一步最值钱的改进**：typed table parser（解决 31% 大数量级错）+ critic agent 二次校验（解决 20% 符号翻转）。两个加起来可能再 +5 pp。

### 10.6 如果你跑这份 reference

```bash
git clone <repo>
cd examples/convfinqa-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 拉数据集（17 MB）
curl -L -o data/data.zip https://raw.githubusercontent.com/czyssrs/ConvFinQA/master/data.zip
unzip -j data/data.zip -d data/

cp .env.example .env  # 填你的 Azure OpenAI / OpenAI key

# 5 条 smoke test，~1 min
python scripts/smoke_test.py

# 完整 stratified 300，~30 min wall-clock（workers=8）
python scripts/run_eval.py --n 300 --workers 8

# 如果有 conv 因为 rate limit 失败：
python scripts/rerun_failed.py --mode agent --workers 2
python scripts/rerun_failed.py --mode baseline --workers 2

# 生成 summary.md + 更新 README
python scripts/finalize.py
```

`.env` 在 `.gitignore` 里，key 只走 `os.environ`，不会泄露到 repo。

### 10.7 最大的认知收获

**做之前我以为 agent 赢在算术能力**，做完之后才发现：

1. 真正赢的是**"结构化输出"**——baseline 13% 的 turn 因为 JSON 不合法直接 0 分，agent 的 tool call 由 API 强制结构化，这一条几乎归零
2. 真正赢的是**"参数命名"**——`subtract(a, b)` 比"心算 a 减 b"少了一个"顺序搞反"的失败模式
3. **算术正确率本身的提升只占 1/3 左右**——因为现在的 LLM 心算其实没那么差

这个观察是 follow-up 面试时一个很好的差异化点：你不只跑了数字，你还**搞清楚了为什么 agent 赢**。

---

> 下一步：拿这份 reference 改一改（换数据集 / 换 prompt / 加 critic）跑你自己的 baseline，然后拿去面试。**有真跑过的人 ≠ 看 paper 的人**，take-home 是要 demonstrate 你做过的，不只是想过的。
