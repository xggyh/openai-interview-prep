## 题目本质

**"Tell me about your job and role"** —— 看似最简单，**实则是面试官第一道筛选**。你的回答决定了：
- 接下来 30 分钟问什么类型的题
- 面试官对你的 baseline 期待
- 你的 seniority signal

OpenAI 报告 Manager 级 2 人。这题在 Manager / TL 面试里**必问**。

## 面试官想从这题得到什么

1. **Scope of impact**：你管多少人、负责多少 surface、决策权多大
2. **Technical depth**：你做的是什么具体技术，而不是"我们做平台"这种虚词
3. **Communication clarity**：能不能 2-3 分钟讲清自己是谁
4. **Match signal**：你的经验跟目标岗位有多 align

## 回答结构（2-3 分钟）

### Layer 1：身份定位（30 秒）

一句话 nail down 三个维度：**职级 + 组织规模 + 业务领域**

> "I'm a Staff engineer at X company, leading the personalization-infrastructure team — 4 ICs reporting to me on the technical track, plus close partnership with 2 PMs and an EM."

不要："I work at X doing stuff"。给数字。

### Layer 2：业务上下文（45 秒）

你的 team 在做什么、为公司创造什么价值。**避免内部 jargon**。

> "Our team owns the real-time feature pipeline that feeds the recommendation models — basically when a user clicks something, we propagate that signal to the ranking model within 200 ms so the next page they see is updated. This drives roughly 12% of total ad revenue."

模板：`我们 team 做 [系统] 给 [谁] 解决 [什么问题]，影响 [可量化指标]`。

### Layer 3：技术深度（60 秒）

举 1-2 个**最近**的项目，**展示你的技术决策**：

> "Last quarter I led a migration from Kafka to Pulsar for our event bus. The decision came down to needing tiered storage and per-message TTL — Kafka required us to maintain a separate cold storage path. I designed the migration as a dual-write phase followed by gradual cut-over by topic. We migrated 200+ topics in 6 weeks without a single consumer outage. The hardest part was retrofitting our schema registry to support both protocols during the transition."

提供：(1) 问题、(2) 你的方案、(3) 数字结果、(4) 一个具体技术细节让面试官 hook 上来追问。

### Layer 4：当前重心 + 转向（30 秒）

> "Right now we're scaling the system 5x to handle the new region launch in EMEA. I'm focused on both — the technical hard problem of cross-region replication latency, and the people side of building out a new sub-team in Dublin."

不要说"I do many things"。给一个**具体在做的事**。

## 不同 level 的 anchor 表达

| Level | 应有的描述 |
|---|---|
| Junior | "I work on tasks within my team's roadmap, primarily X" |
| Mid | "I own feature areas of X system end-to-end" |
| Senior | "I lead 2-3 person efforts and mentor 1-2 juniors" |
| Staff | "I drive 3-month+ initiatives, set technical direction, manage cross-team dependencies" |
| Principal | "I shape multi-year architectural direction for our org of 50+" |
| Manager | "I have N reports / org of M, focus on hiring + people growth + delivery" |

回答时**自然透露**你的 level，让面试官调整问题难度。

## OpenAI 加分项

- **AI / LLM 相关经验**：哪怕只是 side project，提一提（"My side project is a ... using GPT-4o"）
- **Production scale 数字**：QPS、users、$$ impact —— 让面试官知道你接触过 scale
- **跨 team 影响**：不要只描述自己 team —— 提到 partner team + 外部 stakeholder
- **Failure / learning**：可以铺一个失败 hook，等面试官追问 "tell me about a hard problem"

## 真实示例

### Example 1：Tech Lead / Staff IC

> "I'm a Staff software engineer at LinkedIn on the search ranking team. We're a team of 5 ICs and 1 EM, reporting into the search org of about 80 engineers.
> 
> Our team owns the second-stage ranker — given the top 1000 candidates from recall, we run a deep model to produce the final ranked list. We serve about 8M queries per second peak with P99 latency 80ms.
> 
> The most recent project I led was migrating our ranker from XGBoost to a transformer-based model. The hard part was that the transformer needs 30x more compute per query — we couldn't just swap. I designed a two-tower architecture where we precompute user embeddings nightly and only run the cross-attention at query time. End result: 2.1% lift in CTR, 1.5x infra cost (acceptable to the business).
> 
> I'm currently working with our research partners to integrate LLM-generated query expansions. That's why I'm exploring OpenAI — your work on agents and tool use directly impacts what we're trying to build."

### Example 2：Engineering Manager

> "I'm an EM at Square on the developer platform team. I have 7 direct reports — 5 ICs ranging from new grad to Staff, plus 1 TL who manages 2 of them.
> 
> My team builds the internal SDK and API gateway that every Square service uses to talk to each other. Roughly 600 internal services, 4 million RPC/s peak.
> 
> What I've been spending most time on: I'm 8 months into a re-architecture from monolith gRPC services to service mesh (Istio). The org-wide rollout has been... educational. Three engineering teams pushed back on adoption because of latency concerns; we did a series of joint perf workshops to ground-truth the numbers. We're now at 60% rollout with no major incidents.
> 
> On the people side, I just promoted two engineers — one to Senior, one to Staff. I'm now working with my new TL on his first scope expansion."

## 易错点

> [!pitfall]
> ❌ "I do whatever needs to be done" / "I'm flexible" → no signal；
> ❌ 报家门 5 分钟不停 —— 面试官会拦截；2-3 分钟是上限；
> ❌ 全部 internal jargon ("我 own SLO 跨 PR 推动 OKR") —— 听不懂；
> ❌ 不给数字 —— 没法评估 scope；
> ❌ 用过去 5 年 + 当前 1 个 + 未来 5 年都讲了 —— 范围太大；只讲**当前 + 最近 1 个 highlight**；
> ❌ 故意大而虚 "leading transformation" —— 具体！

> [!key]
> 这题的**唯一目标**：让面试官精准判断 "Should I ask the easy version of question X, or the hard version?" 你越能展示 specific scope + concrete impact + relevant tech depth，面试官越会给你 senior-级的题。

> [!followup]
> 后续可能问的：
> - "Walk me through the most challenging tech decision you made"
> - "Tell me about a time you disagreed with someone"
> - "What's your team's biggest constraint right now?"
> - "Why are you considering leaving?" → 提前准备好诚实回答
