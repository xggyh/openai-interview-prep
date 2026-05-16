## 题目本质

**"Tell me about a problem you had to solve that required in-depth thought and analysis"** —— Googlyness。考察：**deep technical thinking + 系统性分析方法**。

不要选 "我 google + stack overflow 解决了某个 bug" 这种浅故事。选**真正花时间 reason about** 的、可能含**有创造性洞察**的问题。

## 选故事的标准

- **数据 + 分析驱动**（不是凭直觉）
- **结论 non-obvious**（一开始 hypothesis 是错的）
- **影响够大**（值得这么多分析）
- **过程可拆解**（你能讲清"先想 X，然后发现 Y，所以 Z"）

## 高质量故事：Latency Tail 调查

**S**：去年 search service 突然 P99 latency 从 80ms 涨到 180ms，但 P50/P90 都没变。整个 team 几周都没找到 root cause —— 加机器没用、回滚最近 deploy 也没用、cache hit rate 正常。被指派给我深挖。

**T**：找出 P99 tail 异常的根因 + 修复。

**A**：
1. **明确假设空间**：列了 7 个可能假设 —— GC 抖动 / cache miss / slow query / 网络 / OS scheduling / 罕见 path / 数据偏斜
2. **第一波数据收集**：分别 instrument 每个假设。GC 看 jstat、cache 看 hit rate、slow query 看 95th percentile slow log
3. **关键洞察**：发现 P99 慢请求**都集中在某 5 分钟窗口**而非均匀分布。于是 hypothesis 7（数据偏斜）变成主嫌
4. **第二波**：按 user_id 分布看 P99 请求 —— 95% 集中在 0.1% 用户。这些用户有什么特殊？
5. **数据深挖**：这 0.1% 用户的 query 含一个特殊 filter (region=APAC-PRE)，trigger 一个 historical fallback 路径
6. **Reproduce + Fix**：本地复现，发现 fallback 路径有个 N+1 query bug；fix 加 batch loading
7. **验证**：staging 测 + 5% canary，P99 回到 75ms

**R**：3 周修复（前 2 周分析，1 周修复 + 验证）。P99 从 180ms 到 75ms。我把方法论写成 doc "tail latency debugging playbook"，后来 team 多次复用。

## 关键展示点

### 1. 假设空间 + 排除法

不是"瞎 debug"，而是先列假设空间，逐一 instrument。这是**科学方法**。

### 2. 数据驱动 hypothesis revision

第一波数据让你 update beliefs 而不是固守原假设（"我觉得是 GC"）。

### 3. 关键洞察点（非线性进展）

故事里要有一个"我之前以为是 X，但数据让我意识到 Y" 的 turn。这是 deep analysis 的标志。

### 4. Reproduce → Fix → Verify

不是"我猜是这个 fix"。复现 + 修复 + 数据验证三步缺一不可。

### 5. 沉淀方法论

把单次调查抽象成 playbook，让 team 受益。这是 Senior+ 信号。

## 加分项

- 提到**reading code / paper** 帮你形成假设
- 提到**写脚本 batch analyze** 几 TB log
- 提到**与领域专家咨询**（DB / kernel / networking）
- 提到**自己之前曾走错路**，怎么修正方向

## 易错点

> [!pitfall]
> ❌ "我冷静思考了一周然后想到答案" —— 没具体过程；
> ❌ 故事的"分析"其实是直觉猜测 + 试错 —— 不算 in-depth；
> ❌ 没数据 / 没数字 —— Senior 故事必须有数字；
> ❌ 结论很 obvious —— 显得问题不够深；
> ❌ 全 process 没人协作 —— 显得不会借力。

> [!key]
> Google 想看：**你能不能用数据 + 假设排除法，从 N 个可能中找到非显然的真因**。这是 SRE/系统性能 工程师的核心能力。

> [!followup]
> - "Why did the standard team approach fail?"
> - "What if your hypothesis had been wrong?"
> - "How long would you spend before escalating?"
> - "Did you have to convince anyone of your hypothesis?"
> - "What did the team learn from this?"
