## 题目本质

**"Can you share an example where you resolved a significant conflict between different teams or departments?"** —— Googlyness。考察：**cross-functional leadership + facilitation + 系统思维**。

不是"我跟某个同事 conflict"。是**两个/多个组织 entity 之间**的冲突你 driving 解决。

## STAR 框架

参考 [[cm5ya8516000irfqrdurp0qmj]] (Bringing different perspectives together) framework。这里 angle 是 **conflict 而非 perspectives**。

## 故事：Mobile vs Backend SLA 战争

**S**：mobile team 抱怨 backend API P95 latency 太高（300ms+），影响 app retention。Backend team 反驳"我们 SLA 是 500ms，你们 mobile 太挑了"。两组 leadership 在 monthly review 上隔空 finger-pointing 3 个月。Director 让我作为 staff 工程师 facilitate。

**T**：作为 third-party Tech Lead，driving solution。

**A**：
1. **Initial 1:1 私下 conversation**：分别约 mobile EM + backend EM 各 30 分钟。listen each side full grievance。
2. **找 root cause not blame**：跟 senior 工程师们 deep dive 数据。发现：(a) backend P95 确实 320ms (b) 但同时 mobile retry policy 在 timeout 1s 上 too aggressive，引起 cascading retry。**两边都有 contribute**。
3. **Joint debug session**：4 hours，两组 senior 同坐一桌。我 facilitate。共同 distributed trace。
4. **共建 unified SLO**：从前各家 SLA 独立 → 共同定义 end-to-end SLO（用户 page load）。Each team 知道 own bucket。
5. **Joint commitment**：mobile 改 retry policy + backend 优化两个 hot endpoint。一起写 commitment doc，两 EM 签字。
6. **30 天 review meeting**：跟踪数据 + 庆祝改善。

**R**：30 天 P95 从 320ms 降到 110ms。Mobile retention 回升。最重要：**两 EM 之后建立了 monthly cross-team perf sync**，避免 future conflict。

## 关键展示点

### 1. 你不是 stakeholder 是 facilitator

第三方 role 让你 neutral。Senior+ Tech Lead 经常做此 role。

### 2. 1:1 listening 先于 group meeting

让每方 feel heard。这是 facilitation 第一原则。

### 3. Root cause 不 blame

最关键洞察：**双方都 contribute**。让 finger-pointing 停。

### 4. Joint artifact

End-to-end SLO + commitment doc。让 abstract "我们合作" 变 concrete。

### 5. Sustained mechanism

不只是 fix 这次 incident，建立 monthly sync 防止 future conflict。

## 加分项

- 提到 **director / VP 的 role**（你不抢他们 spotlight，但 keep them informed）
- 提到 **emotional aspect**（两 EM 个人也 frustrated）
- 提到 **personal cost**（这事占了你 30% time 3 个月）

## 易错点

> [!pitfall]
> ❌ 站队（"我 obviously 觉得 mobile 是对的"）—— 失败 facilitator；
> ❌ "我让 VP 来 align" —— escalate 失败；
> ❌ Joint action 没数据支撑 —— 听起来 abstract；
> ❌ 没 sustained mechanism —— 一次性 fix；
> ❌ 故事 fix 后两组关系仍紧张 —— missing closure。

> [!key]
> Cross-team conflict 解决 = **listen separately → find shared root cause → joint artifact (SLO, doc) → sustained mechanism (recurring sync)**。Senior+ 必备。

> [!followup]
> - "What if one team had refused to participate?"
> - "How did you build trust with both teams?"
> - "What would you do differently?"
> - "Have you escalated to leadership before?"
