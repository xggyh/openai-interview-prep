## 题目本质

**"Tell me about a time when you had to make tradeoffs between quality and cost"** —— Googlyness，报告 2 次。考察：**工程 judgment + business sense + 沟通取舍**。

## STAR 框架

## 故事：launch deadline 下的 test coverage 权衡

**S**：我 lead 一个 feature 要在 marketing event 前 4 周 ship。完整 test coverage（unit + integration + e2e）需要 3 周写，留 1 周 buffer 不够安全。

**T**：要在 quality（完整 test）vs cost（赶 deadline）权衡。

**A**：
1. **不 binary 选择**：先把 test 分级 —— P0 (核心 user flow / 数据完整性) / P1 (常见 edge case) / P2 (rare case)。
2. **数据估计**：每级 test 写多久 + bug 类型 / 风险 estimation。P0 2 天写完，P1 5 天，P2 7 天。
3. **跟 PM + manager 讨论 trade-off**：proposal = P0 + P1 + 上线后 2 周内补 P2。给数字：launch 后 bug 概率 estimate（P0 完整 5%，加 P1 1%，加 P2 0.3%）。
4. **明确 commitment**：launch 后 2 周必须补 P2，写进 Q+1 roadmap，manager sign-off。
5. **加 safety net**：launch 前 1 天 manual smoke test 关键 flow + 1% canary 监控 5 天再 ramp。

**R**：按 deadline launch。Launch 后 14 天发现 2 个 minor bug（P1 catch）+ 0 个 critical。Launch 后第 3 周完成 P2 test。这之后 team 把"test priority framework" 写成 doc 给其他 project 用。

## 关键展示点

### 1. 不 binary

Quality vs cost 不是 0-1。**Tier 化**让 quality 部分让步而非全无。

### 2. 数据 inform decision

不是凭感觉。Bug 概率 estimate 让 trade-off visible。

### 3. Stakeholder buy-in

不是你单方面决定。PM + manager sign-off。

### 4. Commitment to repair

不是"先 ship 再说"，明确"2 周内补完"。Written commitment。

### 5. Safety net

承认 P2 缺失风险，加 canary + manual smoke 兜底。

## 加分项

- 提到 **以前类似 trade-off 出过事的教训**（你不是第一次想这事）
- 提到 **你 manager 的 reaction**（他认可你的 trade-off framework）
- 提到 **如何 prevent future deadline crunch**（不只是这次，是 process change）

## 易错点

> [!pitfall]
> ❌ "我熬夜把 test 都写了" —— 没真 trade-off；
> ❌ "我们 cut 了 test 然后 ship 了 bug 但没人发现" —— 不专业；
> ❌ 没 stakeholder communicate —— 你单方面决定；
> ❌ 没 commitment to repair —— 显得不负责；
> ❌ "我们 lower 了 quality"—— 缺 nuance。

> [!key]
> Quality vs Cost trade-off 不是"两选一"，是"**分级 + tier 化 + stakeholder align + commitment to repair**"。Senior+ 必备的 engineering judgment。

> [!followup]
> - "What if you'd shipped with critical bug?"
> - "How do you decide priority levels?"
> - "Have you ever pushed back on a deadline?"
> - "What's the most expensive trade-off you've made?"
