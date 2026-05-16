## 题目本质

**"Describe your most impactful project"** —— Googlyness。考察：**scope of impact + leadership + tech depth + 自我评估能力**。

这是**最常被问的题之一**。每次面试都该有一个准备好的"flagship project"。

## 选项目的标准

- **Impact 可量化**：$$、users、latency、TC team
- **你的 ownership 高**：不是"team 做了 X 我帮了忙"
- **复杂度匹配 level**：Senior+ 要有 cross-team / 系统级影响
- **技术 + 协作 都强**：不只是"我写了 N 行代码"
- **有 lesson learned**：能反思

## 故事模板：search ranking ML upgrade

**S**：去年我 lead 一个 8 人项目 —— 把 search ranking 从 XGBoost 迁到 deep learning。Business goal: NDCG +3%, 直接转化为 $40M ARR (1% search CTR 增加)。

**T**：作为 tech lead，我负责架构、跨 team 协作（infra / ML research / SRE）、6 个月 delivery。

**A**（关键技术 + 协作 + leadership 三角）：
1. **架构决策**：选 DLRM 架构而非 transformer（latency 顾虑）。写 design doc + 跑数据 + 跟 ML research 团队 align。
2. **风险隔离**：分 4 阶段 —— Phase 1 offline NDCG validate, Phase 2 staging traffic, Phase 3 1% A/B, Phase 4 100%。每 phase 有 go/no-go criteria。
3. **跨 team 协作**：
   - ML research：他们给 model，我给 training infra + serving framework
   - SRE：joint capacity planning, oncall handoff doc
   - Product：每月 demo + adjust 排序权重
4. **leadership**：把 4 个 IC sub-task 分给团队成员，每周 1:1 unblock。一个 senior 工程师在 GPU optimization 上 stuck 2 周，我没接手，而是帮他约 ML platform org 的专家 mentor。
5. **失败 + recovery**：Phase 3 时发现 1% A/B NDCG 反而 -0.5% —— 紧急停 A/B，2 周 debug，发现是 logging bug 让 model 学到 spurious feature。修复后 A/B +3.2%。

**R**：6 个月按计划 GA。NDCG +3.2%（hit goal）。Latency 持平（hit SLO）。Infra 成本 +30%（在预算内）。Team 3 个 mid-level 通过这项目升 Senior。我升 Staff。

## 关键展示点

### 1. 量化 business impact

不只是技术指标，要 translate 到 $ / users。

### 2. 你的 unique contribution

明确"我 personally 做的"vs "team 做的"。Senior+ 期望讲清这个边界。

### 3. 失败 + recovery

完美故事不可信。讲一个真实 setback + 你怎么救回来。

### 4. People impact

不只是 "code/system shipped"，还有"团队成员成长了"。Senior+ 应该。

### 5. Long-term outcome

不止上线那刻，6 个月后系统稳定 / 团队后续 build on it / 文档传承。

## 加分项

- 提到**关键 trade-off**（"为什么不选 transformer"）
- 提到**stakeholder politics**（不只是技术，还有 product / leader buy-in）
- 提到**复用 / generalize**（让 infra 之后用于其他场景）
- 提到**personal struggle**（如：第一次 lead 这么大项目，最焦虑的是什么）

## 易错点

> [!pitfall]
> ❌ Project 是 team 做的但你 take all credit；
> ❌ 没量化 / 数字模糊（"improved a lot"）；
> ❌ 故事没 failure recovery —— 不可信；
> ❌ 选了一个 2 年前的项目 —— 显得 recent impact 不够；
> ❌ Tech 细节过深 vs 完全没 tech —— 失衡；面试官想看两者。

> [!key]
> "Most impactful" 真正想看的是：**你能不能在大项目里同时驾驭技术 + 人 + business + 风险**。Senior+ 是不是 "owner" 心态而不是"executor"。

> [!followup]
> - "What would you do differently?"
> - "What was the hardest moment?"
> - "Who got the credit?"
> - "Has this project influenced your career thinking?"
> - "What if you had to do it in half the time?"
