## 题目本质

**"Why do you want to work at OpenAI?"** —— 经典 behavioral 开场题。看似简单，是面试官的**信号筛选器**：你是想做 LLM 这个事，还是只是想搭末班车 / hype 跟风。

OpenAI 报告 6 次，所有 level（Mid-Senior-Principal）都问。

## 面试官真正想听什么

不要答："because OpenAI is a leading AI company"（虚）

面试官想听三个层次：

1. **你了解 OpenAI 在做什么** —— 不只是 ChatGPT 是 LLM，还知道他们在 alignment、agents、evals、tools 上的具体方向
2. **你的过去经历与他们的工作有真实接点** —— 不是凭空想做 AI，而是过去做过 X 现在能贡献 Y
3. **你的价值观对齐** —— OpenAI 的 mission 是"safe AGI for humanity"。你认同什么、为什么

## 我的回答框架（3 分钟）

### Part 1: Hook —— 一个具体触发时刻（30 秒）

不要泛泛而谈，给一个具体瞬间：

> "去年我在做 X 项目时，第一次用 GPT-4 重写了我们的 [具体功能]，发现它把我之前花 3 周写的 [复杂业务逻辑] 替换成了一个 prompt + 50 行代码，而且效果更好。那一刻我意识到 LLM 不只是工具，而是在重新定义 software 的边界。从那之后我每周都会..."

**亮点**：具体场景、可量化的对比、个人意识转折。

### Part 2: 我做了什么 / 我能贡献什么（60 秒）

证明你不只是观察者，是 builder：

> "我开始在 [现工作 / side project] 用 LLM 解决 [具体问题]，比如：
> - 给 [team] 搭了一个 internal RAG bot，用 [embedding model + vector db + 关键工程选择]，把 [指标] 提升 X%
> - 在 [项目] 里集成 function calling，让 agent 能 [具体能力]
> - 我读完了 [InstructGPT / GPT-4 technical report / Anthropic Constitutional AI 等]，并复现了 [小实验]"

要展示**你为这次面试不是临时抱佛脚**，而是已经在做相关事情。

### Part 3: 为什么是 OpenAI 而非别家（60 秒）

这部分是面试官最在意的。要展示你做过功课：

**针对 OpenAI 的具体点**：
- **Mission**：safe AGI for humanity。"我认同把 AI 当作 broad capability 而不是单点工具，长期愿意为对齐和安全投入"
- **Product + Research 一体**：OpenAI 是少数 product (ChatGPT, API) 和 research (GPT, Sora) 同时推的，能让我做研究的同时看到 100M 用户的产品反馈
- **Infra at scale**：训练 GPT-4o / o3 的规模是别处看不到的工程挑战
- **具体 team match**：你想加入的 team 在做什么（应聘时已经搞清楚），你的 background 怎么 match

**对比别家**（如果被追问）：
- Anthropic：研究纯，产品声音小，没有 ChatGPT 那种 product feedback loop
- Meta / Google：AI 是 division，不是公司 mission
- Mistral / 创业公司：scale 不够大，infra 经验不能积累

### Part 4: 长期视角（30 秒）

> "5 年后，我希望自己在 [具体技术方向] 上能成为 [具体角色]，而 OpenAI 是唯一能让我同时碰到 [research depth + product reach + infra scale + mission alignment] 的地方"

## 真实示例（一个 ML infra 工程师答这题）

> "去年我在做 search relevance ranking 时，第一次用 GPT-4 替换了之前手动维护的 5000 行业务规则。原本一个 query 解析模块要花我两个 sprint 加 unit test，新方案是 50 行 prompt + few-shot examples，离线 NDCG 提升 12%。那次我意识到：LLM 不是给工程师加 buff，是在改变 software 是什么。

> 之后我在 team 里推了三个 LLM 相关项目：用 GPT-4o function calling 实现 internal data query agent；fine-tune 一个 small model 做 PII 检测；还做了一个 prompt 评测 pipeline 用来 monitor production 调用质量。我读完了 InstructGPT 的 paper 然后用 trl 库复现了一个 mini RLHF 实验。

> 我想加入 OpenAI 是因为：OpenAI 是少有的同时做研究和 100M 用户产品的公司。我看到 [具体 team 名字] 团队最近在 [具体方向] 的工作，我之前在 [ranking infra] 的经验直接对得上 —— 我能用 production scaling 经验帮 research idea 上 prod。

> 最重要的是，我相信 OpenAI mission："safely scaling AGI for humanity"。看到 Sam 在 [具体 blog / paper] 提到的 [具体观点]，跟我对 [AI safety / capability] 的判断高度一致。我愿意把未来 5-10 年押在这里。"

## 注意事项

- **不要说**"because of the salary / equity / TC" —— 即使是真的
- **不要批评 OpenAI**，"虽然 ChatGPT 有 hallucination 问题但我相信..." → 听上去像吐槽
- **不要假装喜欢一切**，面试官嗅得出
- 提前 google 你应聘的具体 team 的 blog / GitHub repo，能说出 2-3 个具体项目名

## OpenAI 内部价值观参考（公开来源）

- **Audacity**：do hard things
- **Sustained intensity**：长期持续高强度
- **Mission first**：safety > shipping
- **Scrappiness**：小团队大事
- **Make something people love**

把你的故事 map 到 2-3 个上。

> [!key]
> 这题答案不是模板，是**你 6-12 个月内 LLM 相关的具体行动 + 你为什么把 OpenAI 排到第一**。前者证明你不是 hype 跟风，后者证明你做过功课。

> [!pitfall]
> ❌ "OpenAI 是最好的 AI 公司" → 谁告诉你的？给具体；
> ❌ "我对 AI 有热情" → 行动呢？没有 → 空话；
> ❌ "为了挑战自己" → 哪里都能挑战自己；
> ❌ "ChatGPT 改变了我生活" → 改变了所有人，你的特殊点呢；
> ❌ 没准备 → 即兴答案 80% 概率说出"虚"。

> [!followup]
> 准备好这些追问：
> - "What specifically do you not like about OpenAI?" → 诚实但建设性（如 "API rate limit 对独立开发者还是高"）
> - "How do you feel about the safety vs capability tension?" → 你的立场
> - "If we don't make AGI, who will?" → 这是个钩子，看你怎么定义责任
> - "What would you build first if you joined?" → 准备 1-2 个具体 idea
