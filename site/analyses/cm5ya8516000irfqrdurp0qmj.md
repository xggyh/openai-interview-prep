## 题目本质

**"Describe a time when you brought different perspectives together to solve a problem"** —— Googlyness。考察：**facilitation + synthesis + cross-functional leadership**。

不是"我 + 一同事 disagree"。是**多方 (3+) 不同视角**你 facilitate 找到 unified solution。

## 故事：跨 4 组的 mobile app perf 战役

**S**：mobile app 启动时间 P95 从 1.8s 涨到 3.2s 用户 retention 下降 5%。涉及 4 个 team：
- iOS team：app cold start
- Backend：API latency  
- ML team：on-device model load
- DevOps：CDN / network

每个 team 都说"不是我的问题"。

**T**：我作为 cross-team Tech Lead，被指派 driving 这个问题。

**A**：
1. **召集 unified meeting**：所有 4 team 的 senior + tech lead 一起。我用 1 小时把所有"已知问题"画在一张 flow 图上：cold start → API call → model load → 渲染。
2. **共建 metrics**：之前每 team 用自己的 metrics。我们一起定 unified end-to-end latency breakdown：每段时间打 distributed trace。
3. **数据破 silos**：trace 显示瓶颈 60% 是 model load + 30% 是 API + 10% 是 cold start。这分配让每 team 知道自己 share。
4. **每周 sync 把 progress 公开**：dashboard 每 team 该有的目标 + 当前。Public commitment 提升 accountability。
5. **庆祝小胜**：每段时间降 10% 就在 team chat 公开庆祝。让协作有正反馈。

**R**：6 周 P95 降到 2.1s。Retention 回升。最重要：**4 个 team 之后有了共同 trace + dashboard**，跨组 perf 工作变 routine。

## 关键展示点

- **画图 unify mental model**：每 team 之前看局部，我画 end-to-end 让他们看到全图
- **共建 metrics**：避免"我家指标 vs 你家指标"
- **数据破 finger-pointing**：让每 team 看到自己客观贡献了多少 latency
- **Sync rhythm + public commitment**：从 ad-hoc 到 systematic
- **正反馈循环**：庆祝小胜让 team 愿意 continue

## 加分项

- 提到**会前准备**（你不是开会才开始，你提前跟每 team 1:1 了解他们的 perspective）
- 提到**自己是 outsider** 反而是优势（没 silos bias）
- 提到 **遗留的 process**（建立的 dashboard / sync 之后仍在用）

## 易错点

> [!pitfall]
> ❌ "我让 manager 来 align" —— 没体现你的 facilitation；
> ❌ 故事中你最有专长 —— 不是 cross-functional 是 individual lead；
> ❌ 没数据 —— "我们 align 了" 但没 outcome 数字；
> ❌ 没说会后 sustained 改善 —— 一次性 fix 不算。

> [!key]
> Senior+ 跨组协作信号：**facilitator that produces shared understanding through artifacts (diagrams, metrics, dashboards), not authority**。

> [!followup]
> - "What if one team refused to participate?"
> - "How did you build credibility with teams that didn't know you?"
> - "Did anyone resist the new metrics?"
> - "Have you ever failed at unifying perspectives?"
