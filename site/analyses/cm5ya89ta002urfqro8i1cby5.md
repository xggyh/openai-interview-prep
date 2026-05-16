## 题目本质

**"Tell me about a time when you uncovered a significant problem in your team"** —— Googlyness。考察：**洞察力 + ownership + 触发改变的能力**。

类似"proactive change" 但更聚焦"problem discovery"。

## STAR 框架

## 故事：team 的"silent failures"

**S**：加入 team 3 个月后，我开始 oncall。发现一个奇怪现象：每周 page 量正常，但用户 support tickets 量在涨。Manager 没注意，team 也没人提。

**T**：我没被让 investigate。但我作为 oncall 应该 understand。

**A**：
1. **Cross-correlate 数据**：写脚本对比 last-90-days：oncall pages 数 vs support tickets 数。发现 tickets 涨了 40%，pages 没涨。
2. **挖出 root cause**：sample 100 个 tickets，发现 60% 是"data delay" 投诉 —— 用户看到 stale data 但**没有 alert 触发** 因为 pipeline 是 best-effort 没设 SLO。
3. **私下 1:1 manager**：先不抛 "我发现 problem" 而是问 "我注意到 ticket 量涨，你有顾虑吗?"。Manager 表示没仔细看。
4. **写 short doc**：(a) 现象数据 (b) root cause hypothesis (c) 提议 fix (add SLO alerts + data freshness monitor)。
5. **跟 team 公开**：在 weekly meeting 上 share。但 framing 是 "I found this curious pattern" 而不是"You all missed this"。
6. **认领 fix**：自己花 2 周做 monitoring + 设 SLO。然后跟 staff 工程师共同 review。

**R**：1 个月后 stale data ticket 量降 80%（因为 alert 提早发现 + 修复）。Manager 之后 perf review 提到 "high signal hire"。我也 build 起在 team 里 trust。

## 关键展示点

### 1. Curiosity from observable signal

ticket 量涨 → 你 cared enough to look。Many people would ignore。

### 2. Data correlation 而非 anecdotal

不是"我感觉有问题"，是真做 cross-correlation 数据。

### 3. Diplomatic surfacing

Manager 漏看你不 blame。Framing as "I found something curious"。

### 4. Own the fix

不是"指出问题让别人 fix"。自己花 2 周做 monitoring。

### 5. Long-term trust

建立 reputation 而不仅仅是单次 fix。

## 加分项

- 提到 **你也 worried about 是否 overstepping**（new joiner finding 老问题）
- 提到 **结果让 manager 主动 thank you**（不是你 self-promote）
- 提到 **这件事改变 team 的 culture**（monitoring 文化）

## 易错点

> [!pitfall]
> ❌ "我发现 team 都在做错事，所以..." —— 显得 arrogant；
> ❌ "我跟管理层 escalate 让他们处理" —— 越过 team；
> ❌ Problem 是 obvious 的（任何人能发现）—— 缺信号；
> ❌ 没自己 own fix —— 显得只 critic；
> ❌ 没数据 —— problem discovery 必须 data-driven。

> [!key]
> "Problem discovery" 信号：**curiosity → data → diplomatic surfacing → ownership of fix**。Senior+ 必备。Junior 抱怨，Senior 改正。

> [!followup]
> - "Why didn't anyone else notice?"
> - "What if your manager had brushed it off?"
> - "How did you handle people who felt called out?"
> - "What's a problem you've spotted recently?"
