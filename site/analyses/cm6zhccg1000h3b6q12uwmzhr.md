## 题目本质

**"Describe your approach to solving new and unfamiliar problems"** —— Googlyness。考察：**学习能力 + 方法论 + 元认知**。

这题不是讲"某个具体故事"，而是讲**你的思维框架**。但仍要用具体例子佐证。

## 推荐框架（5 步）

1. **Understand**：问清楚问题边界 + 已知/未知。不假设。
2. **Decompose**：把大问题拆成几个可独立验证的子问题。
3. **Research + analogize**：找已知的相似问题（学术 paper / 内部 doc / 工业实践），借鉴框架。
4. **Prototype + measure**：先做最小可验证版本，数据驱动迭代。
5. **Reflect + generalize**：解决后回看 —— 哪些适用更大类问题？

## 故事示例：第一次做 ML infrastructure

**S**：去年 team 要把 search ranking 从 XGBoost 迁到 deep learning model。我之前是 backend 工程师，对 ML infra 不熟。

**Approach**：
1. **Understand**：跟 ML 研究员 1:1 5 次，画一张 "training-serving pipeline" 图，标出我哪些懂 / 哪些不懂。
2. **Decompose**：分 4 块 —— data prep / model training infra / serving / monitoring。每块独立攻克。
3. **Research**：读 papers (DLRM, DCN-V2)、读 Meta/Google 公开博客、跟内部 ML platform team 借鉴。形成"reference architecture"。
4. **Prototype**：先做一个 toy pipeline（1% data, single GPU），跑通 end-to-end。3 周后扩到 full pipeline。
5. **Reflect**：完成后写一份"ML infra checklist for backend engineers" 分享给 team。3 个同事后来 ramp up 快很多。

**Result**：6 个月迁完。Serving latency 持平 XGBoost。NDCG +3.2%。

## 关键展示点

- **不假设懂**：明确列出 unknowns
- **借鉴而非重造**：先看业界 / 内部已有方案
- **数据 + 迭代**：先 prototype 再 scale
- **沉淀**：把学习变成 team asset

## 加分项

- 提到 **不耻于问 "stupid questions"**（最有效的学习）
- 提到**用类比解释自己** —— "对我，TF training loop 就像 backend 的 long-running service，只不过 state 在 GPU memory"
- 提到 **失败的探索** —— "我也试过 X，发现不 work because Y"
- 提到 **timebox** —— 不允许无限 explore，定 deadline 强制 commit

## 易错点

> [!pitfall]
> ❌ 全程纸上谈兵 没具体例子 —— 显得 abstract；
> ❌ "I just learn fast" —— no methodology；
> ❌ 故事的"unfamiliar problem" 其实是熟练领域 —— 没说服力；
> ❌ 没 reflect / generalize —— 显得 one-off。

> [!key]
> Google 想看：**你能在 unfamiliar 领域用结构化方法快速 ramp up**，而不是"靠经验"。这正是 staff+ 跨领域 lead 项目的核心能力。

> [!followup]
> - "How long would you spend on research before committing?"
> - "When do you ask for help vs figure it out yourself?"
> - "What if your prototype shows the approach won't work?"
- "Has this approach ever failed you?"
