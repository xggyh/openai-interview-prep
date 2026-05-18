## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **IAM (Identity & Access Mgmt)** | 谁能访问什么的系统 | 大楼门禁 + 卡片权限 |
| **Principal** | 被认证的"主体" (user/service/agent) | 一张工卡背后的人/物 |
| **Authentication (AuthN)** | 验证"你是谁" | 验工卡照片 |
| **Authorization (AuthZ)** | 决定"你能做什么" | 看权限表 |
| **OAuth2 / OIDC** | 业界标准 auth 协议 | 国际通用通行证规则 |
| **JWT (JSON Web Token)** | 短期凭证，含 claims 的签名 token | 临时通行证 |
| **API Key** | 长期 token，简单不安全 | 万能钥匙（要保密） |
| **mTLS** | 双向 TLS，client 也有 cert | 双向身份证检查 |
| **RBAC** | Role-Based AC，按角色分配权限 | 部门职位分门禁 |
| **ABAC** | Attribute-Based AC，按属性更精细 | "只有财务、夜班、A 大楼"才能进 |
| **Capability token** | 包含具体权限的 token | 工卡上写明"只能进 5 楼" |
| **Audit log** | 谁做了什么的不可篡改记录 | 监控录像 |
| **Agent** | AI 代理：LLM driven 自动 worker | 自动化助理 |
| **Delegation** | user 把权限委托给 agent 用 | 我让助理替我办事，授权一部分 |
| **Scope** | 权限范围 (e.g., "read email only") | 工卡限定"仅 3 楼" |
| **Short-lived credential** | 短期 token，到期失效 | 24h 临时通行证 |

---

## 1. 题目本质

**IAM for AI Agents** = 给 AI agent（LLM-powered automated worker）一套**identity + 访问权限管理**系统。AI agent 代用户调内部 API / 外部 service，需要安全 auth + auditable + revocable。

**典型场景**：
- **ChatGPT plugin** —— 代你查 Expedia / Slack
- **Anthropic Claude agents** —— 代你处理 email
- **Google Bard** —— 代你查 Gmail 信息
- **Internal AI assistant** —— 代员工查公司 internal docs
- **AI customer support** —— 代理用户做客服操作

**为什么这是 STAFF 题（前沿，1 ppl 报告但每家 frontier lab 都做）**：

考的是 **AuthN/AuthZ + agent-specific 挑战**：

1. **Agent identity** ≠ user identity（agent acts on behalf of user）
2. **Scoped delegation**（只给 agent 部分权限）
3. **Short-lived credentials**（防 token 泄露后长期可用）
4. **Audit trail**（agent 干了什么必须可追溯）
5. **Prompt injection 防护**（agent 被 hack 后限制爆炸半径）

考 STAFF 关键：**OAuth2 + capabilities + audit + 防 agent abuse 的完整系统**。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `RegisterAgent(name, owner, capabilities) -> agent_id` | 创建 agent identity |
| `Authenticate(agent_id, secret) -> token` | 登录 |
| `GrantDelegation(user, agent, scopes, ttl) -> grant_id` | 用户授权 agent 权限 |
| `RevokeDelegation(grant_id)` | 撤销 |
| `CheckPermission(token, action, resource) -> allow/deny` | 调用时检查 |
| `GetAuditLog(filter) -> events[]` | 审计查询 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Latency** | AuthZ check < 10 ms (调用 API 前) |
| **Scale** | 1M agents, 100M users, 1B requests/day |
| **Audit** | 100% requests logged, immutable |
| **Revocation** | < 30 s for token revocation to propagate |
| **Token TTL** | minutes-to-hours (NOT days) |
| **Availability** | 99.999% (auth 挂 = 系统 down) |

---

## 3. 容量估算

- 1M agents × avg 100 requests/day = 100M req/day = **1.2k QPS sustained, 10k peak**
- Audit log: 1B events/day × 500 B = 500 GB/day → cold tier (~6 months retention min for compliance)
- Token issuance: 100M tokens/day issued (most short-lived)

---

## 4. 高层架构

```
┌──────────────────────────────────────────────┐
│  User (granting delegation)                   │
└──────────────────────────────────────────────┘
            │ OAuth-style consent
            ↓
┌──────────────────────────────────────────────┐
│  IAM Service                                  │
│   ├── Identity Registry (agents, users)       │
│   ├── Delegation Manager (grants, scopes)     │
│   ├── Token Service (issue/verify JWT)        │
│   ├── Policy Engine (RBAC / ABAC)             │
│   └── Audit Logger                            │
└──────────────────────────────────────────────┘
            │
            ↓
┌──────────────────────────────────────────────┐
│  AI Agent (e.g., Claude, GPT)                 │
│   - Holds short-lived token                   │
│   - On API call: include token                │
└──────────────────────────────────────────────┘
            │
            ↓
┌──────────────────────────────────────────────┐
│  Target API (Gmail, Slack, Internal Docs etc.) │
│   - Validate token via IAM                     │
│   - Enforce scopes                             │
│   - Log to audit                               │
└──────────────────────────────────────────────┘
```

### Step 1: Agent registration

```python
agent = {
  "agent_id": "ai-assistant-v3",
  "owner": "openai",
  "capabilities_requested": ["read_email", "send_email_with_user_confirm"],
  "trust_tier": "verified",  # gating for fast track
}
```

Agent provider (OpenAI / Anthropic) registers agent ahead of time with capability list. User-facing then asks for delegation.

### Step 2: User delegation flow (OAuth-like consent)

```
User → "Authorize Claude to read my Gmail"
   → IAM shows: "Claude wants read_email scope. Continue?"
   → User clicks "Allow"
   → IAM creates Grant(user, agent, [read_email], ttl=24h)
   → Returns auth_code → agent exchanges for short-lived token
```

### Step 3: Token issuance

Token = **JWT** signed by IAM:
```json
{
  "iss": "iam.openai.com",
  "sub": "agent:claude-v3",
  "act": "user:alice",      // act-as user
  "scope": ["gmail.read"],
  "exp": 1715000000,         // 15 min
  "jti": "unique-token-id"
}
```

Sign with rotating EC256 key (JWKS endpoint exposes pub key).

### Step 4: API call

Agent calls Gmail API:
```
GET /gmail/messages
Authorization: Bearer <jwt>
```

Gmail server:
1. Verify JWT signature (cached JWKS pub key)
2. Check `exp`, `scope`, `act`
3. Check **agent token has read_email scope** AND **user (act-as) has gmail account**
4. Apply user-level row-level security
5. Log to audit

### Step 5: Revocation

Two-track:
- **Short TTL** (15 min) → wait it out
- **Immediate**: write revocation to **block list** (Redis SET of `jti` revoked)
- Gmail / target servers query block list on each request → < 30s propagation

---

## 5. 组件深挖

### Deep Dive 1: Why Short-Lived Tokens

15-min JWT vs 1-year API key:

| Aspect | API key | Short JWT |
|---|---|---|
| 泄露 impact | full access until rotation | max 15 min |
| Revocation | manual rotation needed | natural expiry |
| Auditability | per call (key always same) | per token jti |
| User experience | need rotation reminder | automatic |

**STAFF 答**：default short JWT, refresh via OAuth refresh_token (longer-lived but server-side stored).

### Deep Dive 2: Scoped Delegation

User grants Claude "read_email" but **not** "send_email"。

**Granular scopes**:
```
gmail.read
gmail.send_with_user_confirm  # requires user click
gmail.send_unattended          # full autonomy
calendar.read
calendar.write_with_confirm
```

**Hierarchical scopes**: `gmail.*` implies all gmail。Use prefix matching at policy check。

**Capability ranking**: user choose trust tier per agent。Agent escalates → user re-consent。

### Deep Dive 3: Audit Logging

Every action logged immutable:
```json
{
  "timestamp": "2026-05-18T10:00:00Z",
  "actor": "agent:claude-v3",
  "on_behalf_of": "user:alice",
  "action": "gmail.send",
  "resource": "message_id",
  "result": "success",
  "ip": "...",
  "session_id": "...",
}
```

**Storage**:
- Immediate: Kafka (event sourcing)
- Hot 30 days: Elasticsearch (for query)
- Cold 5 years: S3 (compliance retention)

**Tamper-proof**:
- Append-only Kafka topic
- Hash-chain blocks (like blockchain): block N hash includes block N-1 hash → 改老的会破链
- Periodic root hash anchored to immutable external system

### Deep Dive 4: Policy Engine

Decide allow/deny per request。

**Open Policy Agent (OPA)** style — write policies in Rego:
```rego
allow {
    input.token.scope[_] == "gmail.read"
    input.action == "gmail.read"
    input.resource.owner == input.token.act
}
```

**ABAC**: attribute-based (time, IP, device, geo)
```rego
allow {
    input.token.scope == "internal_doc.read"
    input.time.hour >= 9
    input.time.hour < 18
    input.ip_range == "office"
}
```

**Caching**: policy evaluated < 1ms with cached compiled policy (Rust/Go runtime).

### Deep Dive 5: Token Revocation at Scale

100M tokens active, revocation < 30s:

**Strategy 1: Centralized revocation list**:
- Redis SET of revoked `jti`
- All validators query on each request
- 100M tokens × N TPS check = high read QPS → cache in app server with TTL

**Strategy 2: Short TTL + no list**:
- 15-min TTL means worst-case 15 min for revocation
- For most use cases, OK

**Strategy 3: Push-based invalidation**:
- IAM publishes revocation events to Kafka
- All API servers subscribe → local invalidation cache
- Propagation < 1 s

**Hybrid**: Strategy 2 + 3 (short TTL for cleanup, push for immediate compliance).

### Deep Dive 6: Prompt Injection Defense

Attacker tricks LLM into using its capabilities maliciously.

**Defenses**:
1. **Capability scoping**: agent only has minimum scopes (least privilege)
2. **User confirmation required** for high-risk actions (send email, transfer money)
3. **Rate limiting**: max N "destructive" actions per user per day
4. **Anomaly detection**: agent suddenly做 unusual pattern → require re-auth
5. **Action review**: high-risk actions queued for human review (e.g., approving $1k transactions)
6. **Sandbox per session**: token scoped to specific session, can't reuse for other intents

### Deep Dive 7: Agent Identity vs User Identity

**Key distinction**: token carries both
- `sub` (subject) = agent (`claude-v3`)
- `act` (acting on behalf of) = user (`alice`)

**Why both matter**:
- Audit: know "Claude did X for Alice" not just "Alice did X"
- Trust: agent identity has its own trust tier
- Billing: charge agent provider, not user
- Compliance: if agent misbehaves, action is "Alice's request" but "Claude's responsibility"

**Token format**: extends OAuth2 with `act` claim (RFC 8693 — Token Exchange spec).

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：scope（internal vs external API）, audit retention, anomaly detection |
| 5-10min | 容量：1M agents, 1B req/day, 10k QPS peak |
| 10-15min | OAuth2 + JWT 标准协议建议 |
| 15-25min | 高层架构：IAM Service + Agent + Target API |
| 25-40min | Deep dives: short token / scope / audit / policy / revocation / prompt injection |
| 40-45min | trust tier / billing / compliance |

---

## 7. 样板讲解稿

> AI agent IAM 跟普通 user IAM 主要区别：(1) agent 代用户 act, 双重 identity; (2) prompt injection 攻击面更大; (3) 需要 fine-grained capability + audit。
>
> **架构**：
> 1. **Identity Registry**: agents 注册 by provider (OpenAI/Anthropic), users 注册 by your platform
> 2. **Delegation flow**: OAuth-like consent — user 看到 scope list, 同意 → grant created with TTL
> 3. **Token issuance**: short-lived JWT (15 min) signed by IAM, contains `sub=agent, act=user, scope=[...]`
> 4. **Target API**: validate JWT (cached JWKS pub key) + check scope + enforce
> 5. **Audit**: every action → Kafka → Elasticsearch (30d hot) → S3 (5y cold), append-only + hash chain
> 6. **Revocation**: Redis revoke list + Kafka push to API servers
>
> **Defenses against prompt injection**:
> - Least-privilege scoping
> - User confirmation for high-risk actions
> - Rate limiting + anomaly detection
> - Action queue for human review
>
> **Numbers**: 1M agents × 100 req/day = 100M req/day = 10k peak QPS, 500 GB/day audit log.

---

## 8. Follow-up Q&A

### Q1: "Long-lived API key vs short-lived JWT, 真有区别吗？"

**A**：huge。Long-lived key: leak = full access until manual rotate (months)。Short JWT: leak = 15 min impact + auto-expire。Plus audit log shows exact `jti` of stolen token vs "this key being used in 5 places, which leaked?"。

### Q2: "Agent 突然要更多权限 mid-session 怎么办？"

**A**：**Re-consent flow**:
- Agent calls IAM with "need additional scope X"
- IAM checks if user is online → prompt for additional consent
- If approved: issue new token with extended scope
- If user offline: agent must wait

Never auto-escalate without user consent (security 红线)。

### Q3: "Agent 被 prompt-inject 让它给攻击者发 user 的 email，怎么防？"

**A**：分层防御：
1. **Scope**: `gmail.read` 不含 send → 阻止
2. **User confirmation**: `gmail.send` requires user click "Confirm" → 用户察觉
3. **Anomaly**: agent suddenly send email to never-emailed address → flag
4. **Rate limit**: 10 emails/day max for agent
5. **Audit + retroactive review**: 即使发出，user 能 see audit log 撤销

### Q4: "Audit log 是 source of truth, 怎么保证不被篡改？"

**A**：
1. **Append-only Kafka topic** (compaction disabled)
2. **Hash chain**: block N includes hash(block N-1) → 改老 block 破链
3. **External anchor**: periodically hash root → publish to immutable system (e.g., blockchain or notarization service)
4. **Access control**: only audit-readers can query, no write/delete from anywhere

### Q5: "1B req/day, 怎么 token validate < 10ms?"

**A**：
1. JWT signature verify locally (< 1ms with cached public key)
2. Revocation check: app server-local cache (Kafka invalidation events) 1ms
3. Policy eval: compiled OPA in-process ~1ms
4. Audit: async (Kafka producer non-blocking)
5. Total: 3-5ms typical

### Q6: "Token 在 15 min 内被 leak，怎么紧急 revoke?"

**A**：
- User clicks "Revoke" → IAM writes to Redis revoke list + publish to Kafka `revocations`
- All target API servers subscribe → local cache update (< 1s)
- Next request with this `jti` → reject 401
- Worst case: 1-2s before all servers see revocation

### Q7: "Agent 跨 OpenAI / Anthropic / Google，每家 IAM 不同，怎么 interop？"

**A**：standardize on OAuth2 + JWT + RFC 8693 (Token Exchange)：
- Common OIDC discovery endpoint
- JWKS for public key
- Scope naming convention (gmail.read 全行业一致)
- Cross-platform attestation: agent provider signs "this is Claude v3" → user 信任 chain

**Reality**: working draft, "MCP" (Model Context Protocol) by Anthropic 也是类似思路。

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **Single shared API key for agent** → leak = total compromise
2. **No `act` claim** → audit log 只看到 agent 不知 user
3. **Long TTL (days)** → revoke 难
4. **No scope** → agent 一旦 auth 全权限
5. **No audit** → 不可追溯
6. **Prompt injection 不防** → agent 危险
7. **All-or-nothing consent** → 用户不愿全权限同意

### ✅ 加分项

1. **OAuth2 + OIDC + JWT** 标准协议
2. **RFC 8693 Token Exchange** with `act` claim
3. **Short TTL + refresh token** model
4. **Hash-chain audit log** for tamper-proof
5. **OPA policy engine** with Rego
6. **Capability + scope + ABAC** for fine-grained control
7. **Prompt injection defenses**: scope + confirm + rate limit + anomaly
8. **Cross-platform via OIDC standard**

> [!key] STAFF vs SENIOR：能讲清 **act-as claim + OAuth2 token exchange + hash-chain audit + prompt injection layered defense** 是 STAFF；只说 "JWT + auth check" 是 SENIOR。

---

## 10. Cheat Sheet

```
核心模型:
  Token: short JWT 15 min
  Claims: sub=agent, act=user, scope=[...], jti
  Sign: IAM rotating key (JWKS expose pub)

Flow:
  1. Agent registered ahead (capability list)
  2. User OAuth consent (scope + TTL)
  3. Issue auth_code → exchange for JWT
  4. Agent calls target API with Bearer JWT
  5. Target validate (sig + scope + act) + audit
  6. Refresh via refresh_token before expire

Components:
  Identity Registry (agents/users)
  Delegation Manager (grants)
  Token Service (issue/verify)
  Policy Engine (OPA / Rego, RBAC + ABAC)
  Audit Logger (Kafka → ES → S3, hash-chain)

Revocation:
  Short TTL primary
  Redis revoke list secondary
  Kafka push to invalidate < 1s

Prompt injection defense:
  Least-privilege scoping
  User confirm for high-risk
  Rate limit + anomaly detect
  Human review queue
  Sandbox per session

数字:
  1M agents, 100M users
  1B req/day, 10k peak QPS
  500 GB/day audit log
  Token validate < 10ms
  Revocation < 30s
  TTL default 15 min
```
