## 题目本质

**"Give me an example of when you had to make an important decision and had to decide between moving forward or gathering more information"** —— Googlyness。考察：**decision-making under uncertainty + judgment about info value**。

经典 explore-exploit dilemma。

## STAR 框架

## 故事：要不要等 ML model retraining 结果

**S**：search ranking 上线前一晚，monitoring 显示 staging A/B 微跌 0.8% NDCG（statistical insignificance border）。Plan 是次日 9AM 100% prod cutover。我作为 tech lead。

**T**：决定：(a) 推迟 launch 等 2 周 retrain model (b) 按 plan launch，prod 数据更 reliable

**A**：
1. **Cost of waiting**：每周延期 = $1M 收入损失（marketing dependency）+ team 7 人 stand-down + leader 对 team 信心 erosion
2. **Cost of going**：如果 NDCG 真跌，回滚需 3 天 + brand impact 不大（A/B 数据已 sample 10M users，0.8% 在 stat noise 边界）
3. **Value of more info**：retrain 也只能给 incremental signal，不消除 fundamental risk
4. **判断**：信息 not worth $1M cost。决定 launch，但 hedged：
   - 5% canary 12 小时 instead of 立即 100%
   - 设 abort criteria（实际 NDCG 跌 > 1% 立即回滚）
   - 写 incident playbook 已经 24 小时 standby
5. **跟 manager 同步 decision rationale**：他认可。
6. **Launch**：5% 12 小时数据 +0.3% NDCG（actually 比 staging 好）。Ramp 到 100%。

**R**：launch 成功。Final A/B +1.1% NDCG。$2M Q4 ARR。最重要：**我学到 "stop seeking more info when info won't change decision"**。

## 关键展示点

### 1. Explicit cost-benefit

不是"我觉得 OK"，是 explicit 列出 cost of waiting + cost of going。

### 2. Value of additional info

关键思考：**这个 info 能不能 change 你的决策？** 不能 → 不值得 wait。

### 3. Hedging

Decision 不是 binary。Hedge with canary + abort criteria 降低 risk。

### 4. Manager sync

不 unilateral 决定。Sync rationale。

### 5. Outcome + lesson

数字 + 抽象 lesson ("when info won't change decision")。

## 加分项

- 提到 **类似情况你 chosen wait 的反例**（你 not always "ship!"）
- 提到 **你 update 自己 framework**（之后做 launch decisions 用类似 explicit 分析）
- 提到 **team alignment**（他们不只看你 decide，参与 rationale 讨论）

## 易错点

> [!pitfall]
> ❌ "我直觉就 launch 了" —— 缺 framework；
> ❌ Decision 是 binary（"ship or not"）—— senior 能 hedge；
> ❌ 没量化 cost of waiting —— abstract；
> ❌ 没 manager 同步 —— 失职；
> ❌ Outcome 是 lucky（"幸亏没事"） —— 缺 process robustness。

> [!key]
> Senior+ decision-making：**explicit cost-benefit + value of info + hedge + sync**。Junior 直觉决策，senior framework 决策。

> [!followup]
> - "What if the canary had been negative?"
> - "Have you regretted a 'ship' decision?"
> - "How do you decide when to wait?"
> - "What if your manager had said wait?"
