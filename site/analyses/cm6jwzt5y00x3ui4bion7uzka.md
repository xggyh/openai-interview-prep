## 题目本质

**"Tell me about a time when your manager set reasonable demands. Follow up: a situation with unreasonable demands."** —— Googlyness，报告 3 次。考察：**对管理风格的适应能力 + push back 的成熟度**。

特别注意：**这是两段式问题**。"reasonable demands" 部分要展示**信任 + 执行力**；"unreasonable demands" 要展示**有原则地拒绝 + 解决问题**。

## STAR 框架（双故事）

每段故事 ~2 分钟。

## 故事 A：Reasonable demands

**S**：上季度 manager 让我们 team 在 2 周内完成 search ranking 一次 latency 优化，目标 -15% P99，因为下季度大型营销活动。

**T**：我作为 IC 主负责实现。

**A**：
1. 主动跟 manager 确认目标背后的 why（"是为了 marketing event 还是长期 KPI？"）—— 知道是 hard deadline 后我重组了优先级。
2. 把 2 周拆成 4 个 milestone (each 3.5 day)，每个有可衡量产出。
3. 主动 daily standup 报进度（不需要他追问）。
4. 提前 3 天发现某优化方案不可行 → 立即调整 + 通知 manager + 提出 plan B。

**R**：按期交付，P99 降 18%（超目标）。Manager 把这事写在我 perf review 当年 highlight。

**点**：reasonable demand 的关键是 **"理解 why → 主动管理 → 主动 sync"**。

## 故事 B：Unreasonable demands

**S**：去年 Q4 一个 senior leader（不是直属 manager）pinged me，说要在 4 天内把整个 recommendation pipeline 从 v1 切到 v2，因为他要在年终 review 上 demo "新成果"。技术上需要 3-4 周才稳。

**T**：我不能直接说 "no"（他是 +2 级别），但仓促切换会导致 prod incident + 影响 30+ M users。

**A**：
1. **First seek to understand**：约他 30 分钟，问清楚他真正需要什么 —— 原来他要的是 "可 demo 的成果"，不是 prod cutover。
2. **重新框架问题**：提出 "demo path"：在 staging 环境跑 v2 + 准备 A/B test 数据 + 可以 demo "我们已 ready for cutover Q1"。
3. **明确风险**：把"4 天 prod 切换"的失败概率 + 用户影响数 写进 doc 给他 + 抄送我 manager。
4. **给替代时间表**：Q1 第一周 staging full traffic，第三周 5% prod，第四周 100%。
5. **跟我 manager 同步**：确保他不被 surprise，且 he can back me up if needed.

**R**：他接受了 staging demo 方案。年终 review 他 demo 顺利。Q1 我们按 plan 切换，0 incident。他后来直接邀请我加入他 org 的另一个 strategic project。

**点**：unreasonable demand 的关键是 **"不正面拒绝，而是重新框架 + 给替代方案 + 让对方真正需求被满足"**。

## 加分项

- **理解需求背后的 why**（reasonable 和 unreasonable 都关键）
- **不 escalate 不抱怨**，给 solution
- **提前 sync** 给 manager / 利益相关方
- **数据说话**（"4 天概率 < 30%，3 周概率 > 95%"）
- **长期关系考虑**（不只解决当下，还考虑这件事对将来关系的影响）

## 易错点

> [!pitfall]
> ❌ Reasonable 故事讲得太 routine（"manager said do X, I did X"）—— 没信号；
> ❌ Unreasonable 故事变成抱怨 manager —— 大忌；
> ❌ 直接拒绝 "I said no" —— 显得僵化；
> ❌ 完全屈服 "I worked 4 nights and did it" —— 显得没 judgment；
> ❌ 没准备 follow-up 那段 —— 准备同样深度的两个故事是关键。

> [!key]
> Google 想看的：**reasonable 时是 high-performer + 主动 communicator；unreasonable 时是 protective stakeholder + creative problem-solver**。最差答案是 "我永远 say yes"。

> [!followup]
> - "Have you ever said no to a demand and the manager pushed back?"
> - "How do you balance speed with quality when manager pressures speed?"
> - "Did your manager hold a grudge after you pushed back?"
> - "What did you learn about your manager's communication style?"
