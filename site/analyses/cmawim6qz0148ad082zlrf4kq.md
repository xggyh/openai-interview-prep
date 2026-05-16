## 题目本质

**"Tell me about a time you had to pivot mid-project"** —— Googlyness。考察：**判断力 + 沉没成本管理 + change management**。

## STAR 框架

## 故事：从规则引擎到 ML

**S**：6 个月项目目标是把 content moderation 从人工 review 改成 rule-based 自动化。3 个月后 build 完 v1，发现：规则只能 cover 30% case，剩 70% 需要 understand context（讽刺、隐喻），规则系统 architecture-wise 解决不了。

**T**：作为 tech lead，要做艰难决定：继续推 v1（已 sunk 3 个月），还是 pivot 到 ML（要从 0 重来）。

**A**：
1. **不情绪决策**：花 1 周做 data analysis —— 用历史数据模拟 v1，得出 precision/recall。结果：v1 precision 65%，远低于 production threshold 95%。
2. **写一份 "honest assessment" doc**：列 (a) v1 当前进度 (b) v1 完成后能达到的 ceiling (c) ML 方案需多久达到同 ceiling (d) ML 长期 ceiling。
3. **跟 stakeholders 提 pivot**：先 1:1 跟 manager + PM 同步。他们也认 v1 ceiling 不够。
4. **重启 + 复用**：pivot 不是完全 throw away。v1 的 labeled data + rule infrastructure 在 ML 方案里复用 (作为 weak supervision + heuristic feature)。
5. **诚实 communicate** team：team meeting 公开 "v1 won't ship as planned"。承认这是 tough call。给团队 emotional space。

**R**：Pivot 后 2 个月 ML v2 ship 到 staging。Precision 92%，recall 75%。比 v1 在每个指标都好。半年后 production cover 80% case（比 v1 计划的 30% 多）。Team 没有人离职 —— 反而 senior 工程师后来跟我说"那次诚实 pivot 让我相信这 team 是 truth-seeking 的"。

## 关键展示点

### 1. Data-driven 而非情绪决策

不是"觉得 v1 不 work"，是用数据证明。

### 2. Sunk cost 不阻挡决策

3 个月 sunk cost 不该影响 forward decision。Senior 标志。

### 3. Pivot 不是 0-1

v1 的 part（data、infrastructure）在 v2 复用。**没浪费**。

### 4. 诚实 communicate

不掩盖问题，公开"v1 ship 不了"。短期不舒服，长期建立信任。

### 5. Team well-being

承认对 team 是 setback。给情绪空间。

## 加分项

- 提到**自己曾 reluctant to admit v1 limitation**（自我反思）
- 提到 **manager support** 在 pivot decision 中的关键
- 提到 **如何 prevent 类似情况**（v3 计划在前 4 周就 prototype 关键 risk）

## 易错点

> [!pitfall]
> ❌ "我立即知道要 pivot" —— too perfect，不真实；
> ❌ Pivot 完全 throw away v1 —— 浪费 + 显得没规划；
> ❌ 没数据支撑 pivot decision —— 显得 emotional；
> ❌ 没 manage team emotion —— 缺人维度；
> ❌ Pivot 后没 ship —— 失败的 pivot 故事除非有 strong lesson。

> [!key]
> Pivot 不丢人，**用 data 证明 + 复用过去 + 诚实沟通** 才是好的 pivot。Sunk cost fallacy 是 Senior 工程师常见 trap。

> [!followup]
> - "Why didn't you see this in month 1?"
> - "What if your manager had said no to pivot?"
> - "How did you maintain credibility after the pivot?"
> - "When do you pivot vs persist?"
