## 题目本质

**"Tell me how you helped someone in your team to get better at some task"** —— Googlyness。考察：**mentorship + skill transfer + 同理心**。

不要讲"我教 junior 写代码"。要讲**有方法、有效果**的 deliberate skill development。

## STAR 框架

## 故事：帮 mid-level 工程师提升 design 能力

**S**：team 里有个 mid-level 工程师 Mike，code 写得好，但 design doc 经常被 review 打回 —— 写了"how" 没写"why"，缺 alternatives 比较，性能数字粗糙。他想升 senior。

**T**：我作为 Senior 不直接是他 manager 但他主动找我做技术 mentor。

**A**：
1. **诊断 gap**：跟他过他过去 3 个 design doc，列出每个被打回原因 —— 发现 80% 是"没解释 why"。
2. **共同看 examples**：找 team 里 3 个最佳 design doc 一起读，让他自己识别"good doc 有什么共同点"。
3. **结构化模板**：给他一个 "design doc skeleton" 模板（Problem → Context → Alternatives → Decision → Rationale → Risks）。
4. **从小做起**：他下一个 task 是改一个小 cache 模块（不是大项目）。让他先写 1 页 design doc 再写代码。
5. **每周 30 分钟 sync** 4 周：每次他写了什么我先 review 私下反馈，再让他自己改后 submit。这样不在 public review 里 expose 他。
6. **逐渐 hands-off**：第 5 周开始我只看他 submit 后的 review，不再 preview。

**R**：3 个月后他 design doc 第一次得到全 LGTM。半年后他升 Senior，promo doc 里特别提到 design skill 改善。我之后帮他建立"自己的 senior mentor"角色。

## 关键展示点

### 1. 诊断 gap（不是 generic 帮助）

具体看他过去的 work 找出 root cause，不是泛泛 "你要多练"。

### 2. Show don't tell

让他自己读 good example 识别 pattern，比我说教更有效。

### 3. Scaffold then remove

先帮多（template、preview），逐渐 hands-off 让他独立。

### 4. Protect public face

不在 public review 里 expose 他的 gap。这是 senior mentor 的 emotional intelligence。

### 5. 量化结果 + 长期 trajectory

不只是 "他变好了"，而是 promo + 自己也成 mentor。

## 加分项

- 提到 **他主动找你**（不是你 paternalistic 强加）
- 提到 **manager loop in**（避免 cross-management）
- 提到 **失败的 try**（"先 4 周用一种方式没效果，换另一种"）
- 提到**接下来你怎么 scale**（不只是 Mike，而是把 template 分享给 team）

## 易错点

> [!pitfall]
> ❌ "我给他讲了一遍他就懂了" —— 太轻；
> ❌ "他后来变好了" 没数字 —— 缺信号；
> ❌ 故事被帮的人完全没 agency —— 显得 patronizing；
> ❌ 没提到 manager 沟通 —— 显得越权；
> ❌ "我帮过很多人" 但没具体一个 —— 不可信。

> [!key]
> Senior+ 的 mentor 标志：**诊断 → 提供结构化工具 → scaffold → 逐渐 remove → 量化结果**。不是"我把答案告诉他"。

> [!followup]
> - "What if Mike resisted feedback?"
> - "How did you balance your own work with mentoring?"
> - "Have you ever failed at mentoring someone?"
> - "Did you ever tell someone they're not ready?"
