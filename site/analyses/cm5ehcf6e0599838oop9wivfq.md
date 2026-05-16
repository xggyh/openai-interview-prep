## 题目本质

**"Tell me about a time you had a conflict with a coworker. How did you resolve it?"** —— Googlyness，报告 3 次。与"conflict at work" 同类但更聚焦**人际间**而非 cross-team。

参考主题：[[cmbhko677005iad09y02ykfyv]] (Tell me about a conflict you had at work) 的详细 STAR 框架。这里讲一个**更聚焦同事关系**的示例。

## 故事：与平行同事的代码风格分歧

**S**：team 里有个同 senior 级别的同事 Alex，code review 总是给我提"过度严格"的 nit，平均每个 CL 30+ comments。其他人也有类似抱怨。但 Alex 在团队里影响力大，没人直接说。

**T**：我自己 CL throughput 受影响 + 跟 Alex 关系紧张。我想 fix 这个问题但又不想破坏关系。

**A**：
1. **私下约面**：不在 review 里 push back，而是约咖啡。开门见山："我注意到你 review 我 CL 时给很多 nit。我想理解你的标准 + 看看怎么改进合作。"
2. **承认部分合理**：他有些 nit 确实是合理 style 改进。我先 acknowledge 这些。
3. **明确 cost**：然后说"但每 CL 30+ comment 让 review cycle 平均 4 天，我们 team velocity 受影响"。给数字。
4. **共同 propose 改进**：他承认有时"过度"。我们一起定 "rule of 5"：nit 上限 5 个/CL，更多 nit 写成 follow-up CL（不阻塞 merge）。
5. **试用 + 反馈**：用 1 个月，效果好。后来扩展到全 team review 规范。

**R**：我 CL 周期降到 1.5 天。Alex 反馈 "他自己也省了时间"。我们后来还合作了一个大项目。Team review velocity 平均提升 40%。

## 关键展示点

- **不在 public review 里发飙**（emotional intelligence）
- **私下 1:1 直说**（不是 passive-aggressive）
- **共同找方案**（不是"你改"，是"我们改"）
- **数据 + 影响**（不是凭感觉抱怨）
- **改进 systemic** 而非 ad-hoc（rule of 5 推广到全 team）

## 加分项

- 提到**先理解对方动机**（他不是恶意，他 perfectionist）
- 提到**自己也有 part 责任**（我有些 CL 确实可以写更好）
- 提到**长期 net positive**（最终 team 都受益）

## 易错点

> [!pitfall]
> ❌ "我 escalate 给 manager 处理" —— 应该自己尝试解决；
> ❌ "我也开始给他挑刺 retaliate" —— 大忌；
> ❌ 故事的 conflict 是"他态度差/语气"—— 不专业；
> ❌ 没数据 / 没影响 —— 抱怨而非问题解决；
> ❌ 解决后没 sustain —— 长期来看效果如何。

> [!key]
> 同事冲突最有效解决 = **direct conversation + acknowledge their POV + propose systemic fix**。Senior 不是 "avoid conflict" 是 "handle conflict elegantly"。

> [!followup]
> - "What if Alex had refused to change?"
> - "Did your relationship with Alex recover?"
> - "Did you tell your manager?"
> - "Have you been on Alex's side of a similar conflict?"
