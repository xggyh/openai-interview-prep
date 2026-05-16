## 题目本质

**"Discuss a time when you had conflicting perspectives with teammates and how you handled it"** —— Googlyness，报告 3 次。与"conflict at work" 相似但更聚焦"**同事间技术 / 方向上的分歧**"。

## STAR 框架

## 故事模板：技术方案分歧

**S**：team 在重构 user profile service 时，我和另一个 Senior 工程师在 schema 设计上分歧 —— 我主张用 flexible JSON column（schema-on-read），他主张严格 typed column。这会影响后续 3 年的开发模式。

**T**：作为 co-leads 我们要在 2 周内确定方案，否则 downstream team 无法 plan。

**A**：
1. **不立即辩论**：先约 1:1 让对方完整讲完他的方案 + 担忧，我做笔记不打断
2. **写下双方观点**：联合写 design doc，**每个观点都用 first principles 论证**而不是 appeal to authority
3. **找共同评估维度**：开发速度 / 维护成本 / 演化灵活性 / 查询性能 / 隐私合规
4. **跑数据**：分别 prototype 两方案 3 天，跑真实 query workload 对比性能
5. **结论混合**：数据显示 typed column 在 read 上快 4x，但开发周期长 3x。最终方案 = typed core fields + JSON extension column（hybrid）
6. **共同 present**：两人一起跟 team 讲方案，对方先讲他的初始观点，我讲我的，最后讲 hybrid 怎么综合

**R**：方案 1 周内 sign-off。1 年后看：hybrid 经受住了 3 次大需求变更（用 JSON 扩展）+ 关键 read path 仍快（typed core）。我们俩之后多次合作。

## 关键展示点

### 1. Listen before argue

第一步先听对方完整观点。这让对方"被听到"，后续 collaborate 容易。

### 2. First principles 论证

不是"我以前在 X 公司这么做"，而是"为什么这么做"。

### 3. 数据 break tie

意见不一 → 跑数据。让事实而非 ego 决定。

### 4. 综合方案 > 单方案

很多 disagreement 实际是"trade-off 取舍点不同"。Hybrid 是常见出路。

### 5. 共同 present

不是"我赢了"或"他赢了"，而是"我们一起决定"。这保留双方 dignity 和 buy-in。

## 加分项

- 提到**你曾经被对方说服**（"原以为 A，听完对方发现 B 更合理"）
- 提到**约 mentor / staff 仲裁**（如果僵持）
- 提到**长期合作改善**（这次冲突后我们之后怎么协作）

## 易错点

> [!pitfall]
> ❌ "我有理由 + 数据，他没有 → 他被说服了" —— 显得 winner-loser 心态；
> ❌ "我们 split 一半" —— 折中而非 synthesize；
> ❌ 没数据 break tie —— 听起来 ego 之争；
> ❌ 故事中你 100% 是 right side —— 不现实；
> ❌ 没说 long-term outcome —— missing closure。

> [!key]
> Senior+ 信号：**能把 disagreement 转化为更好的方案 + 维护长期关系**。不是"赢辩论"，是"team 进步"。

> [!followup]
> - "What if data didn't resolve it?"
> - "When do you escalate to manager?"
> - "Have you ever been on the wrong side of such a debate?"
> - "How do you keep the relationship after a heated disagreement?"
