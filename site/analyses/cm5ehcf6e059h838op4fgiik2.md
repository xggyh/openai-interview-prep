## 题目本质

**"Tell me about a project where requirements were unclear or kept changing. How did you adapt?"** —— Googlyness，报告 3 次。考察：**应对 ambiguity 的能力 + 主动管理需求 + 适应性**。

工业实际中需求清晰 < 50% 时间。面试官想看你是怎么在"无地图"时仍能交付。

## STAR 框架

## 故事模板：LLM 产品的需求探索

**S**：去年我接手一个 LLM-powered customer support automation 项目。客户给的需求是 "用 GPT-4 来自动处理 customer ticket"。但具体哪些 ticket / 怎么处理 / 准确率要求 / 失败 fallback —— 全没明确。CEO 想要"几周内 demo"，product manager 想要"年内 GA"，客服总监想要"先解决 top 10 重复 ticket"。

**T**：作为 tech lead，我需要在 unclear / conflicting requirements 下推进项目。

**A**：
1. **第一周：探索 + 拼图**
   - 跟 5 个利益相关方各 1:1 30 分钟 —— 把每方"想要的 outcome" 和"deadline / 资源限制" 列成 doc
   - 把交集找出来：top 5 high-frequency ticket type
   - 把冲突列出来：CEO 要的 "demo" 与 PM 要的 "GA" 时间冲突
2. **第二周：写一个 Minimum Viable Spec 文档**
   - 三段：(1) Q1 demo 范围 = top 5 ticket type, 70% precision; (2) Q2 expand 范围；(3) GA Q3
   - 邀请所有方 sign-off。CEO 不满意 "demo only top 5"，我用数据说服："top 5 占了 60% volume"
3. **每两周一次 stakeholder sync**：变化的需求在这里 surface + 取舍。不在这里提的不算 binding requirement
4. **建立"决策日志"**：每次需求/范围变化记一条 (date, who requested, decision, rationale)，避免 amnesia

**R**：6 周 demo 成功。Q3 GA。期间需求改了 11 次，但因为有 sync + decision log，每次变更影响清楚。我后来把这套流程写成 team manual。

## 关键展示点

### 1. 主动 framework 而非被动等清晰

不等 PM "给清楚需求"，自己主动建 spec 让对方 sign-off。

### 2. 数据驱动取舍

不是说"全做" 也不说 "没法做"，而是用数据（top 5 = 60% volume）说服 stakeholder 接受范围限制。

### 3. 记录决策日志

需求变了不可怕，可怕的是"我以为是 A，你以为是 B"。Decision log 是低成本防 amnesia 工具。

### 4. 规律性 sync

把 ad-hoc requirement change 收敛到 bi-weekly sync —— 避免每天被打断，又能及时响应。

## 加分项

- **主动 prototype 帮 stakeholder 形成需求**（很多时候他们不知道自己要什么，看到 demo 才知道）
- **用 leading question 帮 PM 把需求说清楚**（"如果只能做一件事，是哪件？"）
- **保留 buffer 应对未来变化**（不要把 100% capacity 都 commit 给当前 spec）
- **跟 manager 同步早期** —— 当需求 ambiguity 大时让 manager 知道你需要 air cover

## 易错点

> [!pitfall]
> ❌ "我就一直加班 catch up 需求变化" —— 缺方法论；
> ❌ 抱怨 PM / stakeholder —— 显得不成熟；
> ❌ 故事里你 "总是 yes" —— 没体现 push back 能力；
> ❌ 没数字 / 没结果 —— 缺 outcome 信号；
> ❌ 流程过度（4 个 stakeholder 每周 meeting 全 mandatory）—— 显得不会 trade-off。

> [!key]
> Ambiguity 中的核心能力 = **"自己建框架，让 stakeholder 在框架内沟通"**。Senior+ 工程师区分点：能在没人告诉你"该做什么"时，自己定义"该做什么 + 用数据让别人同意"。

> [!followup]
> - "What if a stakeholder kept changing their mind?"
> - "How did you decide which requirements to prioritize?"
> - "Did you ever push back on a change request?"
> - "What if the CEO disagreed with your prioritization?"
- "Have you ever made the wrong call on prioritization?"
