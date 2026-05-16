## 题目本质

**"Tell me about a time when you had a conflict with your manager and you were wrong"** —— Googlyness。考察：**self-awareness + humility + 处理认知失调**。

特别难答 —— 你需要承认错误且不破坏自我形象。最忌"假错"（"我太追求完美"）。

## STAR 框架

## 故事：技术决策被 manager 否决

**S**：我推动用 GraphQL 替换 REST API，写了 3 周 design doc，跟 team 多次讨论。Manager review 后说"不"，理由是 GraphQL 对我们 use case（少量 mobile client + heavy backend internal）不 worth complexity。

**T**：我当时强烈不同意，认为 manager 不懂技术。我觉得他保守。

**A**：
1. **当时的 push back**：我做了 1 小时 deep dive presentation 反驳他。他听完后说"我们 talk later"。
2. **冷静后的 reflection**：那天晚上我重读 manager argument，发现他列的几点我确实**没仔细 evaluate**：
   - GraphQL N+1 query 问题
   - 我们 mobile team 只 2 个工程师，learning curve cost
   - 已有 REST monitoring 完备 vs GraphQL 重建
3. **第二天 1:1 主动承认**："我重新想了一下，你对几个点是对的。我之前太聚焦 GraphQL benefits 没充分评估 cost。"
4. **重新提方案**：保留 REST + 在某些 high-fan-out endpoint 用 BFF (Backend for Frontend) pattern，享受 GraphQL-like benefit 但不全 swap。
5. **跟 team 也承认**：在 team meeting 上说"我之前推 GraphQL 时的 cost analysis 不够。Manager push back 是对的"。

**R**：BFF pattern 6 个月后效果良好。Manager 在我之后 perf review 里特别提到"willing to update conclusion based on new info"。我自己也意识到自己有"喜欢新技术"的 bias，之后做技术决策时主动用 checklist 评估 cost。

## 关键展示点

### 1. 错误是真实的（technical judgment）

不是"我态度差"那种 superficial 错误。是**实质性技术判断错误**。

### 2. 承认过程是 reflective 的

不是"立刻被说服"，而是冷静后自己 update。这显得不是 surrender 而是 reasoned change。

### 3. 主动 admit + 公开

不只是私下承认，在 team 也承认。建立"willing to be wrong" 的文化。

### 4. 提出更好方案

不是"manager 是对的我做 nothing"，而是"我学到了再 propose 升级版"。

### 5. 长期 self-improvement

意识到 own bias（"喜欢新技术"），用 checklist 自我 calibrate。

## 加分项

- 提到 **Manager 的 reaction**（"他没 gloat，反而 thanked me for the openness"）
- 提到 **这影响后续合作**（manager 更愿意 trust 你的判断）
- 提到 **specific bias** 你识别到（避免 "I learned to listen better" 的虚词）

## 易错点

> [!pitfall]
> ❌ "假错"（"I was too aggressive in defending my idea"）—— 显得 dishonest；
> ❌ 错误是 cosmetic（"I missed a typo in the doc"）—— 不够 substantial；
> ❌ "manager was actually right, I admitted" 没说怎么 admit —— 缺过程；
> ❌ 没 long-term reflection —— 失败 = success without takeaway is failure；
> ❌ Manager 在故事里没 grace（"他炫耀我错了"）—— 不专业 framing。

> [!key]
> Senior+ 的 self-awareness 标志：**能识别 own bias，能在 evidence 面前 update belief，能公开承认错误且不破坏自信**。"我曾经错"比"我永远对"更 senior。

> [!followup]
> - "What's a current bias you're working on?"
> - "How do you know when you're wrong vs your manager is wrong?"
> - "Have you had a manager who was wrong and you were right?"
> - "How do you raise disagreement going forward?"
