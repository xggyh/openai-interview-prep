## 题目本质

**Behavioral / People Management** 题：讲一个你最大的失败 / 错误，以及你从中学到了什么。

OpenAI 报告 5 次，Mid-Senior + Manager 都问。不是要听"假装失败的成功"（"我太追求完美了"），面试官想看：**真实 + 自责 + 学到的具体经验 + 改了之后的行为变化**。

## 框架（CARL，比 STAR 更适合 failure 题）

| 步骤 | 说明 | 时间 |
|---|---|---|
| **C**ontext | 背景：什么项目，你的角色，stakes | 30 秒 |
| **A**ction | 你做了什么 + 哪里做错了 + 为什么决定那么做 | 60 秒 |
| **R**esult | 结果：失败的具体表现（数字 / 影响） | 30 秒 |
| **L**earning | 学到了什么 + 你之后改变了什么具体行为 | 60 秒 |

总长 2.5-3 分钟，再长面试官会打断。

## 选故事的标准

**好故事的特征：**
- ✅ 失败是**你做的决定导致的**，不是别人 / 运气
- ✅ 后果**真实可量化**（损失 $X、延迟 N 周、N 人受影响）
- ✅ 你**主动承担责任**，不甩锅给 team / mgr / 外部
- ✅ 学到的是**具体技能或行为**，可以举之后改进的实例
- ✅ 与你目标岗位有关联（Staff Eng 讲技术决策、Manager 讲团队管理）

**避坑：**
- ❌ "We launched late" 大型集体失败 —— 你的责任在哪？
- ❌ "I worked too hard / I was a perfectionist" —— 面试官翻白眼
- ❌ 5 年前实习时的小事 —— 想不出更近的失败说明你避免反思
- ❌ 学到的是"我以后多 check" —— 太虚，要具体

## 三个高质量模板

### 模板 1：技术决策失误（适合 Staff / IC track）

**Context**: 我在 X 公司是 search infrastructure team 的 tech lead。我们要把推荐召回从 lookup 改成 vector search，技术选型 Faiss vs ScaNN vs Milvus。

**Action**: 我没等 prod traffic 数据，直接基于离线 latency benchmark 选了 Faiss。理由是开发周期短。我跳过了 shadow 流量验证就直接上 50% prod。

**Result**: 上线后 P99 latency 从 80ms 跳到 350ms，cold start QPS 高峰时 OOM 重启。3 天后 rollback，期间 CTR 跌 8%，估算 $200k 收入损失。事故复盘上我被点名。

**Learning**: 我学到的不是"benchmark 更全面"，而是**"任何 infra 替换必须先 shadow，shadow 至少跑过完整业务峰值"**。之后做的 storage layer 改造，我强制要求 shadow 至少 2 周 + 1 个完整 sales event；遇到 PM 推快上线时我把这次的 incident 拿出来。从那以后没再出过类似问题。

### 模板 2：沟通 / 优先级失误（适合 PM / TL）

**Context**: 我带 5 人小组做一个 Q3 OKR，目标降低 backend latency 30%。

**Action**: 我开干前没跟 mobile team align —— 我自以为这是纯 backend 项目。结果 6 周后做完才发现 mobile 客户端依赖一个老接口，要 backward-compatible，我们的优化全白做。

**Result**: 整组 6 周工作要重来 60%。OKR 季末只达成 12%。组员士气掉，一个 senior 第二季度跳槽。

**Learning**: 学到的具体行为：**任何 backend 改动开工前必须画 cross-team impact list 并 ack-back 每个 stakeholder**。之后每个 project 我加了"Week 0 alignment doc" 模板，list 所有 downstream consumers 并必须签字。我也学会**主动找潜在依赖团队**，不再被动等他们提需求。

### 模板 3：管理失误（仅适合 Manager 岗）

**Context**: 我刚提拔成 EM，带 7 人 team。其中一个高级工程师 A 表现下滑 —— code 质量降、review 延迟。

**Action**: 我没及时正面谈，而是把任务越来越多分给其他人，希望 A 自己感觉到。3 个月后 A 主动找我说他想离职因为"感觉被边缘化"。

**Result**: A 离职 → 团队失去关键人 → 一个 deliverable 延期 6 周。我后来才知道 A 当时家里有事不好开口。

**Learning**: 学到：**对表现下滑的 IC，唯一对的做法是尽早 1:1 直接谈、问发生了什么、共同制定支持计划，而不是变相施压**。之后我建立了双月 deeper 1:1（30 min 非工作话题），任何 perf 下滑 ≤ 2 周内必须谈。之后 18 个月没再有人因 perf-不沟通而离职。

## OpenAI 特别加分项

- 把学习关联到 **AI safety / risk management**：在 LLM 团队，技术决策失误的代价可能不只是 $$ 而是**模型有害输出**或**用户信任损失**
- 提到**post-mortem 文化**：你之后写过的 incident review 模板、组内推广的 blameless culture
- 展示 **growth mindset**：失败后做了哪些 follow-up（学课程、读书、找 mentor）

## 真实候选人 timeline 显示（OpenAI 报告）

抓到的页面里有 5 个其他公司也问这题（Meta、Anthropic 都问过），是高频 behavioral。说明这题不是 OpenAI 特殊偏好，是行业标准 Manager 题。

> [!key]
> 不要美化失败 —— 面试官嗅得出来。**真失败 + 真自责 + 真改变** = 信号。可量化的 dollar / time / people impact 让故事可信。

> [!pitfall]
> ❌ "I trusted my team too much" → 推责任给团队，反向 red flag；
> ❌ "I learned to communicate better" → 学习太抽象；
> ❌ "I wouldn't change anything looking back" → 答案违背题意；
> ❌ 没数字 / 没影响 → 不可信；
> ❌ 失败发生在 5 年前 → 长不出新经验。

> [!followup]
> 准备好回答深挖问题：
> - "How did you tell your manager?" → 主动 vs 被动？
> - "What did the post-mortem look like?" → blameless？谁主导？
> - "Have you seen this happen since?" → 你的改变真的起作用了吗？
> - "What would you do today differently?" → 又过了 1-2 年，现在还会再优化什么？
