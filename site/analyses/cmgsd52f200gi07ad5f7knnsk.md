## 题目本质

设计 **Identity and Access Management (IAM) system for AI agents**：管理 AI agent（LLM-powered automated workers）的 identity + 访问权限。AI agent 调用 internal APIs / 外部 service，需 secure auth + audit。

OpenAI / Anthropic / Google 都需要。新兴 problem。

## 需求

- 每 agent 有 unique identity
- 细粒度权限（什么 API 可访问，什么 data 可读）
- Time-bounded credentials（避免永久暴露）
- Full audit log
- Cross-org agent federation

## 整体架构

```ascii
   User / Org
       │ create agent + policy
       ▼
  ┌──────────────────┐
  │ Agent Identity   │  → assign agent_id, attach IAM policy
  │ Service          │
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────┐
  │ Token Issuer     │  STS-like, issue short-lived JWT
  │ (per agent run)  │
  └──────┬───────────┘
         │
   Agent runtime
         │ call with token
         ▼
  ┌──────────────────┐
  │ Resource API     │  → policy check
  └──────┬───────────┘
         │ audit
         ▼
  ┌──────────────────┐
  │ Audit Log        │  immutable, append-only
  └──────────────────┘
```

## 核心组件

### 1. Agent identity

每 agent 一个 stable identity：
- `agent_id` UUID
- Owner (user / org)
- Type (`code-assistant` / `customer-support` / `research`)
- Creator's role 决定 max permission scope

### 2. Policy 设计

IAM policy JSON（类 AWS IAM）：

```json
{
  "agent_id": "...",
  "policies": [
    {"action": "read", "resource": "code/repo:foo", "effect": "allow"},
    {"action": "write", "resource": "*", "effect": "deny"},
    {"action": "call", "resource": "tool:web-search", "effect": "allow",
     "conditions": {"max_calls_per_min": 30}}
  ]
}
```

### 3. Token lifecycle

每 agent run / session 颁发 short-lived JWT (15 min):
```
agent invocation → STS issues JWT (claims: agent_id, policies summary, exp)
agent stores in env → use in API calls
expired → refresh via refresh token (also bounded)
```

Long-running agent run → 周期 refresh。

### 4. Resource server auth check

```python
@require_agent_auth
def api_handler(request):
    token = parse_jwt(request.headers['Authorization'])
    if not policy_engine.allows(token.agent_id, action='read', resource=...):
        raise Forbidden
    # ... handle
    audit.log(agent_id=token.agent_id, action=..., resource=..., result='allowed')
```

Policy engine = OPA (Open Policy Agent) or custom Rego-like。

### 5. Rate limiting per agent

防止 agent runaway 调用：per-agent QPS cap, daily cost cap. 超额 → token revoke + alert owner。

### 6. Audit log

每 agent action 写 immutable log:
- Who (agent_id, owner)
- What (action + resource + parameters)
- When (timestamp)
- Result (allowed / denied)
- Cost ($$/tokens used)

Append-only Spanner / S3 + WORM。Compliance + forensics。

### 7. Agent-to-agent delegation

Agent A 调用 agent B（multi-agent system）：A 把自己 token delegated to B，B 继承 A's scope **intersect** B's policy。Prevent privilege escalation。

### 8. Revocation

Owner 可立即 revoke agent。Resource server 每次 verify token 时 check revocation list (Redis cached)。

### 9. Cross-org federation

Agent 跨 org 调用：OAuth-like consent flow，owner org confirm。Token claim 含 source org + target org。

## 关键安全考虑

- **No long-lived secrets** in agent code
- **Per-invocation tokens** not per-agent
- **Policy review** 强制 human approval for sensitive permissions
- **Anomaly detection** on agent behavior (突然调用 different APIs)

## 易错点

> [!pitfall]
> ❌ Static API key per agent → 泄漏永久；
> ❌ 不 audit → forensics 时无线索；
> ❌ Token lifetime 太长 → 攻击窗口大；
> ❌ Multi-agent delegation 不 intersect policy → privilege escalation；
> ❌ Rate limit only at API → agent 内部死循环消耗自己 budget。

> [!key]
> 三大要点：(1) **Short-lived per-invocation JWT** + STS；(2) **OPA-style policy + audit log**；(3) **Delegation with intersection** 防 privilege escalation。本质是 AWS IAM 应用到 AI agent。

> [!followup]
> "Agent 在 sandbox 里跑 untrusted code？" → 加 process sandboxing (Firecracker)；"Cost attribution per agent？" → 每 token / API call 记 cost + bill owner；"How to deprecate agent？" → revoke + grace period notice。
