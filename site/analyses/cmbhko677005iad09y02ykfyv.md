## 题目本质

**"Tell me about a conflict you had at work"** —— Google "Googlyness" 核心题。报告 6 次（含 Senior、Staff、Manager 各 level）。考察：**冲突处理成熟度 + 同理心 + 解决导向**。

不要回答得让自己显得"无冲突 = 没原则"，也不要"我总是赢"。要展示**有原则 + 有共情 + 找到双赢**。

## STAR 框架

**S**ituation（30 秒）：背景 + 利害关系
**T**ask（10 秒）：你的角色 / 期望
**A**ction（60-90 秒）：你怎么做 —— 这是重点
**R**esult（30 秒）：结果 + 学到什么

## 选故事的标准

- **真实**（面试官嗅得出虚构）
- **冲突 = 工作判断分歧**，不是人际撕逼
- **你的行动是关键变量**（不是"团队最终自己想通了"）
- **结果可量化 / 关系修复 / 长期受益**

## 高质量故事模板

### 模板 A：技术决策冲突（适合 IC / Tech Lead）

**S**：去年 Q3，我和另一位 Senior 工程师在团队 cache 层选型上分歧 —— 我主张 Redis Cluster，他坚持自研 in-memory cache 用现有的 thrift RPC。这影响整个 search infra 6 个月的 roadmap。

**T**：作为 tech lead 我需要做最终决策，但要确保团队达成共识，不能强压。

**A**：我做了三件事：
1. **暂停争论，回到数据**：约他先一起写 design doc，列出两方案的 5 个评估维度（延迟 / 运维成本 / 灾备 / 扩展性 / 学习曲线）。
2. **承认他的合理性**：明确说 "你担心 Redis 在 99.9 percentile 不可控，这点我没充分回应"，让他知道我听到了。
3. **设计实验**：提议用 1 周做 prototype 对比 P99 延迟和 failover 行为，让数据说话。
4. **决策时邀请他主持**：实验结果出来后让他 present 给团队，包括他的反对意见。

**R**：实验显示 Redis P99 47ms vs 自研 89ms（GC 抖动）。他接受了。他还在 design doc 上加了"如何监控 Redis JIT 抖动"的章节 —— 后来真的救了我们一次 incident。3 个月后他成了 Redis migration 的主推手。

**学到**：技术冲突 80% 是因为"对方的顾虑没被听到"。先 acknowledge 再用数据。

### 模板 B：跨组冲突（适合 Manager / Staff）

**S**：我 team 和 platform team 因 SLO ownership 争议 3 个月没解决 —— 我们 service 的 P99 latency 超标，但根因是 platform 提供的 RPC framework 慢。Platform 不承认这是他们的 bug，我们也无法独立 fix。

**T**：作为 EM 我要给我 team SLO；同时不撕破跟 platform 的合作。

**A**：
1. **避免邮件升级**：第一时间 1:1 跟 platform EM 喝咖啡，开门见山："这事拖三个月对两组都不好"。
2. **共建 root cause**：约两个 senior 工程师一周共同 debug，明确 bug 是双方共同的 —— platform 框架有问题 + 我们的 retry policy 也加重了。
3. **承担一半**：先 commit 我们改 retry policy（其实只解决 30% 问题），让对方愿意 reciprocate。
4. **写 joint commitment**：联合 oncall 流程 + 责任分摊 doc，两 EM 签字。

**R**：6 周内 P99 从 280ms 降到 92ms。Platform team 主动重构了 framework。两组之后每月共做 capacity review。最重要：我们组的 mid-level 工程师学到"冲突不是要赢，是要解决问题"。

## 加分项

- 提到**listen-first**（"我先复述了他的担忧"）
- 提到**先 give to get**（先 commit 一些事让对方 reciprocate）
- 提到**长期关系**（不只是解决眼前事，而是怎么改了流程）
- 承认**自己也有 bias / mistake**

## 易错点

> [!pitfall]
> ❌ "对方完全错了，我教育了他" —— 听起来傲慢；
> ❌ "我们最终都同意" 但没说怎么同意 —— 太抽象；
> ❌ 故事的冲突是非工作（pizza 谁付钱）—— 显得幼稚；
> ❌ 没数字 / 没影响 —— "我们最终发布了" 太弱；
> ❌ "我让步了 / 我赢了" 二选一思维 —— 真正的成熟是找第三选项。

> [!key]
> Google 想看的不是"无冲突的人"，是**"有冲突时能让团队变得更好的人"**。把冲突当成 leadership opportunity 而非负担。3-5 分钟讲清一个故事，留细节给追问。

> [!followup]
> 准备这些追问：
> - "What if the other person had refused to compromise?"
> - "Did you escalate to your manager? Why or why not?"
> - "What would you do differently today?"
> - "Have you ever 'lost' a similar conflict? What happened?"
> - "How do you decide when to compromise vs. hold your ground?"
