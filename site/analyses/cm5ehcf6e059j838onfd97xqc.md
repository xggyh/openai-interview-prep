## 题目本质

**"Tell me about a time where you proactively proposed a change"** —— Googlyness，报告 2 次。考察：**主动性 + ownership + 改变 status quo 的能力**。

不是"我老板让我改 X 我改了"。是**你 self-identify a problem + propose solution + drive it through**。

## STAR 框架

## 故事：从季度 on-call 到周轮值

**S**：team on-call 是季度轮值，每个工程师一季度负责 oncall 1 周。问题：incident 来了往往 1 人扛，疲惫 + 学不到东西。我注意到这个 status quo 已经 2 年，无人挑战。

**T**：我作为 mid-level senior，没有 mandate 改这个。但我相信改成 week-based rotation 更好。

**A**：
1. **数据收集**：扒过去 12 个月 oncall log。计算每周 incident 数 + 每 oncall 周 burnout 信号（pages / hour, after-hours pages, weekend pages）。
2. **写 proposal doc**：列 (a) 现状问题 (b) 建议改 (c) cost / risk (d) 试点计划。
3. **私下 socialize**：先跟最有影响力的 senior 工程师 1:1，听她 input。她意见让 doc 更好。再跟 manager 1:1。
4. **manager 不反对但有顾虑**："新人 rotate 频率高，知识传承差"。我加入 "shadow week" 设计 —— 新人 oncall 前一周跟当前 oncall shadow。
5. **试点 3 个月**：跟 team 共同决定试 3 个月。Set up evaluation metrics（incident resolution time, oncall NPS）。
6. **结果好就 sustain**：3 个月后数据更好，team vote 96% 继续。

**R**：oncall NPS 从 4.2/10 升到 7.8/10。Avg resolution time 降 30%（多人 fresh + shadow）。1 年后这套被其他 team 借鉴 4 个。我自己积累了 driving change 的 playbook。

## 关键展示点

### 1. Self-identify the gap

不是 manager pointed out。**你看到问题且 care enough to act**。

### 2. Data first

不是凭感觉提议。先收集 12 个月数据 supporting。

### 3. Socialize before formal proposal

先 1:1 跟 stakeholders。这避免 surprise + 让你提前 absorb 反对意见。

### 4. Address objection

Manager 顾虑 "knowledge transfer"。你不 dismiss，加 shadow week 设计。

### 5. 试点 vs 全推

不是"all or nothing"。3 个月试点 + metrics 让 risk 可控。

### 6. Generalize

不止你 team，影响到 4 个其他 team。

## 加分项

- 提到 **manager 反对 / 中立 时 你怎么 navigate**
- 提到 **如何 maintain team morale during 改变**
- 提到 **你之后另一个 proactive change**（建立 pattern）

## 易错点

> [!pitfall]
> ❌ "我老板让我 propose 改" —— 不是 proactive；
> ❌ 改的事很小 —— 缺信号（"我建议每天 standup 缩短 5 分钟"）；
> ❌ 改的事 manager 不喜欢但你硬推 —— 缺 politics sense；
> ❌ 没数据 / 没 trial —— 显得 aggressive；
> ❌ 改完没 long-term outcome —— missing closure。

> [!key]
> Senior+ 信号 = **identify + propose + drive change** 完整 loop。Junior 看到问题抱怨；Senior 看到问题动手；Staff+ 把改变 generalize 到更多 team。

> [!followup]
> - "What if the team had rejected the trial?"
> - "How did you handle people who liked the old system?"
> - "What's another change you proposed that didn't work?"
> - "How do you decide what's worth changing?"
