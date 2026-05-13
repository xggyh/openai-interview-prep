## 题目本质

实现 **Authentication Manager**（custom 版本，区别于 LC 1797）：处理用户 login、logout、session 管理，validate credentials，maintain active sessions。

OpenAI Staff 级，1 人报告。这题更**像生产 AuthN 服务**而非纯算法。考点：**密码哈希 + session token + 安全特性**。

## 题目语义

```python
auth.register(username, password)       # 注册
auth.login(username, password) -> token # 登录 → 返回 session token
auth.is_valid(token) -> bool             # token 是否有效
auth.logout(token)                       # 注销
auth.list_active_sessions(user) -> list  # 列出用户活跃 session
```

## Python 实现

```python
import secrets
import hashlib
import hmac
import time
from dataclasses import dataclass

@dataclass
class Session:
    token: str
    user_id: str
    created_at: float
    last_seen_at: float
    expires_at: float
    user_agent: str = ''
    ip: str = ''

class AuthenticationManager:
    """生产级 auth manager：密码哈希、session token、TTL、可注销。"""

    SESSION_TTL = 3600 * 24 * 7   # 7 days
    PEPPER = b'global_secret_pepper'  # 应来自环境变量 / KMS

    def __init__(self):
        # username -> (salt, password_hash)
        self.users: dict[str, tuple[bytes, bytes]] = {}
        # token -> Session
        self.sessions: dict[str, Session] = {}
        # user -> set of active tokens
        self.user_sessions: dict[str, set[str]] = {}

    # ----- 注册 / 登录 -----
    def register(self, username: str, password: str) -> bool:
        if username in self.users:
            return False
        salt = secrets.token_bytes(16)
        pwd_hash = self._hash_password(password, salt)
        self.users[username] = (salt, pwd_hash)
        self.user_sessions[username] = set()
        return True

    def login(self, username: str, password: str,
              user_agent: str = '', ip: str = '') -> str | None:
        rec = self.users.get(username)
        if not rec:
            # constant-time pretend hash to avoid leaking "user exists" by latency
            secrets.compare_digest(b'\x00' * 32, b'\x00' * 32)
            return None
        salt, stored_hash = rec
        candidate = self._hash_password(password, salt)
        if not hmac.compare_digest(candidate, stored_hash):
            return None
        return self._create_session(username, user_agent, ip)

    # ----- session -----
    def is_valid(self, token: str) -> bool:
        s = self.sessions.get(token)
        if not s:
            return False
        now = time.time()
        if now >= s.expires_at:
            self._revoke(token)
            return False
        s.last_seen_at = now
        return True

    def logout(self, token: str) -> None:
        self._revoke(token)

    def logout_all(self, username: str) -> int:
        """注销该用户所有 session（密码改了 / 撞库怀疑时调用）"""
        tokens = list(self.user_sessions.get(username, set()))
        for t in tokens:
            self._revoke(t)
        return len(tokens)

    def list_active_sessions(self, username: str) -> list[Session]:
        now = time.time()
        return [self.sessions[t] for t in self.user_sessions.get(username, set())
                if t in self.sessions and self.sessions[t].expires_at > now]

    # ----- internal -----
    def _hash_password(self, password: str, salt: bytes) -> bytes:
        # PBKDF2-HMAC-SHA256：100k iterations + pepper
        # 生产应用 Argon2id，但 stdlib 提供 pbkdf2 + scrypt
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode() + self.PEPPER,
            salt,
            iterations=100_000,
            dklen=32
        )

    def _create_session(self, username: str, user_agent: str, ip: str) -> str:
        token = secrets.token_urlsafe(32)  # 32 字节 → 43 字符 base64url
        now = time.time()
        sess = Session(
            token=token,
            user_id=username,
            created_at=now,
            last_seen_at=now,
            expires_at=now + self.SESSION_TTL,
            user_agent=user_agent,
            ip=ip,
        )
        self.sessions[token] = sess
        self.user_sessions.setdefault(username, set()).add(token)
        return token

    def _revoke(self, token: str) -> None:
        s = self.sessions.pop(token, None)
        if s and s.user_id in self.user_sessions:
            self.user_sessions[s.user_id].discard(token)
```

## 复杂度

所有操作 **O(1)** 或 O(1) 摊销（除了 `logout_all` 是 O(K)，K = 用户活跃 session 数）。

## 安全要点（面试官期待你说）

### 1. 密码不能明文存

用 **盐 (salt) + 慢 hash（PBKDF2 / scrypt / Argon2）**：
- Salt：每用户独立随机 16 字节，防 rainbow table
- 慢 hash：让暴力破解每次猜测耗时长（100k iterations ≈ 100ms）

**不要用** MD5 / SHA1 / 无 salt 的 SHA256 —— 1 张消费级 GPU 每秒 10B+ hash。

### 2. Pepper（额外秘密）

代码里 / 环境变量里有 PEPPER，DB 泄漏后单单 DB 不能破解密码（攻击者还需要 application server 的 secret）。

### 3. Constant-time comparison

`hmac.compare_digest` 比 `==` 抗时序攻击（==' 短路返回，可以根据耗时推断匹配前 N 位）。

### 4. Session token 随机性

`secrets.token_urlsafe(32)` → 32 字节 = 256 bit 熵，撞库不可行。**绝不能** 用 `random.choice` 或 `uuid4` 之外的可预测来源。

### 5. Session 不在 URL 里

token 放 HttpOnly cookie（防 XSS）+ SameSite=Strict（防 CSRF）。不放在 URL 路径或 query string（会进 server log / refer header）。

### 6. Logout 真的失效

`logout` 必须 **服务端撤销 token**，不能只删客户端 cookie。本实现把 token 从 `self.sessions` 移除，下次 `is_valid` 直接 False。

### 7. 密码改了 → 撤销所有 session

`logout_all(username)` 必须在密码 reset 之后调用。

## 工业级延伸

| 特性 | 说明 |
|---|---|
| **JWT** | 自包含 token，无需 DB 查询。但**不易撤销**（需 deny-list） |
| **Refresh + Access token** | Access token 短 TTL（15 分钟），refresh token 长 TTL（30 天）。Access 不可撤销但短命，refresh 可撤销 |
| **2FA** | 登录时除密码还要 TOTP 或 WebAuthn |
| **Rate limit** | 同 IP / 同 username 一分钟内 5 次失败后锁定 / captcha |
| **Login alert** | 异地登录通知邮件 |
| **Device fingerprint** | 记录 user_agent + ip + browser 指纹，可疑设备 step-up |

## 易错点

> [!pitfall]
> ❌ 密码哈希用 SHA256 不加 salt —— rainbow table 秒破；
> ❌ Session token 用 `uuid4().hex` —— 仍有 122 bit 熵，但语义上不是 cryptographically random；用 `secrets`；
> ❌ `==` 比较哈希 —— 时序攻击；
> ❌ Logout 只清客户端 cookie —— 服务端不撤销，token 仍然有效；
> ❌ 密码改了不 invalidate 其他设备 —— 旧密码泄漏的攻击者可以继续登录。

> [!key]
> 实现 auth 不是"写完 CRUD"，是**展示对密码哈希、token 熵、安全比较、session 撤销的理解**。这些是 OpenAI 面试官想看的安全敏感度。

> [!followup]
> "如何对接 OAuth (Google login)？" → 用户走 OAuth 流程，拿到 google id_token → 我们 verify google JWT → 创建本地 user record + session。"如何防止 session hijacking？" → IP/UA binding（变化时 step-up 验证）+ HTTPS + HttpOnly。"如何 100M 用户扩展？" → users 表分 sharding by username hash；sessions 放 Redis（自带 TTL 不需要 heap）。
