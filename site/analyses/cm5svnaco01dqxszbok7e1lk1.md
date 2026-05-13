## 题目本质

设计 **URL Shortener**（TinyURL / bit.ly）：长 URL → 短 alias；用户访问短 URL → 301/302 重定向到长 URL。规模：100M URL / 月 + 1B redirect / 月。

经典 SD 入门题。OpenAI 报告 6 次，Senior-Staff / Manager 都问。考点：**ID 生成策略 + KV 存储设计 + 缓存 + 分析**。

## 需求拆解

**功能性：**
- 提交长 URL → 返回短 URL（如 `t.ly/abc123`）
- 访问短 URL → 重定向
- 自定义 alias（vanity URL）
- 过期时间（可选）
- 简单分析（click count / geography / referrer）

**非功能性：**
- 100M 新 URL / 月 = ~38 写 QPS（平均），峰值 5x = ~200 QPS
- 1B redirect / 月 = ~400 读 QPS，峰值 5x = ~2000 QPS
- redirect 延迟 < 50ms
- 99.99% 可用

**容量估算：**
- 5 年存 100M × 12 × 5 = 6B URL
- 每 record ~500 B (long URL + meta) → 3 TB

## 整体架构

```ascii
       User
         │  GET /abc123
         ▼
   ┌──────────────┐
   │   CDN        │  ← cache hot redirects edge-cached
   └──────┬───────┘
          │ miss
          ▼
   ┌──────────────┐
   │  Edge LB     │  geo-routed
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │  API Service │  stateless
   └──┬─────┬─────┘
      │     │
      ▼     ▼
 ┌────────┐  ┌──────────────┐
 │ Cache  │  │ ID Gen       │  Snowflake / KGS
 │ (Redis)│  │ Service      │
 └────┬───┘  └──────┬───────┘
      │             │
      ▼             ▼
   ┌──────────────────────┐
   │   URL Store          │
   │   (sharded NoSQL,    │
   │    DynamoDB / Cass)  │
   └──────────┬───────────┘
              │
              ▼ (async)
       ┌──────────────┐
       │ Click Logger │  → Kafka → Analytics
       └──────────────┘
```

## 核心组件设计

### 1. 短 URL ID 生成（最关键）

三种方案：

**A. Base62(auto-increment ID)** —— 简单：DB 自增 ID 转 base62（[0-9a-zA-Z]）。6 位可表示 62^6 ≈ 568 亿。
- 优点：紧凑、有序、易实现
- 缺点：可枚举（攻击者爬全表）

**B. Hash(long URL) 截断** —— MD5/SHA → 取前 6 位 base62。
- 缺点：碰撞处理麻烦（rehash 或 linear probe）；同 URL 两次提交得同短码（也可能是优点）

**C. KGS (Key Generation Service) 预生成** —— 离线生成 1000 万个唯一短码池，API 来取。
- 优点：无碰撞，预分配的 key 不可猜
- 实现：generator service 把池写 Redis / DB；API 取一个就标 used

**推荐 C** 用于生产 + **A** 作为备选 fallback。

```python
import base64
import random
import string
CHARSET = string.ascii_letters + string.digits  # 62 chars

def encode_id(n: int) -> str:
    """64-bit ID → 11-char base62"""
    if n == 0: return CHARSET[0]
    s = []
    while n:
        n, r = divmod(n, 62)
        s.append(CHARSET[r])
    return ''.join(reversed(s))

class KeyGenService:
    def __init__(self):
        self.pool: set[str] = set()
        self._refill(10000)
    def _refill(self, n):
        while len(self.pool) < n:
            self.pool.add(''.join(random.choices(CHARSET, k=7)))
    def take(self) -> str:
        if not self.pool: self._refill(10000)
        return self.pool.pop()
```

### 2. 数据模型

```python
# DynamoDB / Cassandra
class UrlRecord:
    short_code: str   # PK
    long_url: str
    user_id: str | None
    created_at: datetime
    expires_at: datetime | None
    click_count: int  # eventually consistent counter
```

按 `short_code` hash 分 partition；写入 / 读取都 O(1) by PK。

### 3. 缓存策略

- **CDN 边缘缓存**：热门短 URL 的 301 在 CDN 缓存（TTL 24h），最快路径
- **Redis** 内存：API 查 Redis 命中直接返回；miss 查 DB 后回填
- **DB 是 source of truth**

热门 80/20：top 20% URL 占 80% 流量，Redis hit rate 可以做到 95%+。

### 4. Redirect 301 vs 302

- **301 (permanent)**：浏览器缓存，下次直接跳，**不再发请求** → click count 不准
- **302 (temporary)**：每次都发请求 → click count 准
- 平衡：**302 + cache-control: max-age=3600** —— 短时间缓存，但仍有上报机会

### 5. 自定义 alias

用户请求 `t.ly/mybrand` → 先检查是否已存在 → 不存在直接 insert；存在返回 conflict。

校验：长度 5-30、字符只允许 `[a-zA-Z0-9_-]`、不能撞内置 reserved path（`/api`, `/login` 等）。

### 6. 分析（点击统计）

每次 redirect：API 异步写 `Kafka: click.{short_code, ts, ip, ua}` → 后端 worker 聚合到 Spark / ClickHouse → 出报表。

**不要同步更新 click_count**（DB 写热点）；异步聚合写入足够。

### 7. 过期清理

后台 cron job 扫 `expires_at < now` 标记 deleted；硬删除可以延后到月底 GC 减小写放大。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| ID 生成 | KGS（不可猜） | Auto-increment：可枚举 |
| Redirect | 302 + cache-control | 301：click count 不准 |
| 存储 | DynamoDB / Cassandra | Postgres：sharding 麻烦 |
| Click count | Kafka 聚合 | DB 同步：写热点 |
| 缓存 | CDN + Redis 双层 | 单层：miss 走 DB 太多 |

## 关键技术点

### 写路径
```
POST /shorten { long_url, custom_alias? }
  ↓ 校验 long_url 格式
  ↓ 取 short_code (KGS 或 custom)
  ↓ PUT UrlRecord 到 DynamoDB（条件写：if not exists）
  ↓ 回填 Redis
  ↓ 返回短 URL
```

### 读路径
```
GET /abc123
  ↓ CDN 命中？返回 301/302
  ↓ Redis 命中？返回 302 + 异步 click 上报
  ↓ DynamoDB 查 → 回填 Redis → 返回 302 + 异步 click
  ↓ 不存在？404
```

> [!key]
> 三大要点：(1) KGS 预生成 ID 避免碰撞 + 不可枚举；(2) 双层缓存（CDN + Redis）做 redirect 加速；(3) Click 统计异步上报，绝不同步写 DB counter。

> [!pitfall]
> ❌ 用 hash(long_url) 取前 6 字节做 short_code —— 碰撞概率随规模增大；
> ❌ Redirect 301（不发请求）+ 要 click count —— 自相矛盾；
> ❌ Click count 直接 `UPDATE counter` —— 写热点，热门链接压爆 DB；
> ❌ Custom alias 不校验 reserved path —— 用户可注册 `/api`、`/login` 制造钓鱼；
> ❌ Long URL 不校验 —— 用户写 `javascript:` / `data:` URL 引入 XSS。

> [!followup]
> "如何防 spam（机器人批量造垃圾短 URL）？" → IP rate limit + captcha + 白名单域名（长 URL host 必须可达）。"如何 multi-region 同步？" → DynamoDB Global Tables / Cassandra multi-DC，最终一致足够（短 URL 创建后到生效几秒延迟用户不感知）。"如何审核非法长 URL？" → 提交时调 Google Safe Browsing / 内部 ML 过滤 + 用户举报。
