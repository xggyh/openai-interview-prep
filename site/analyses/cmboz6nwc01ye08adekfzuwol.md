## 题目本质

设计 **Anti-Phishing System**：检测 + 阻断 phishing URLs / emails / domains。保护用户。Google Safe Browsing / 邮件 spam filter 同类。

## 需求

- Real-time URL check (< 50ms)
- 10B+ URL DB
- High recall (catch most phishing)
- Low FP (不阻 legit)
- Multi-source signal (URL, content, sender)

## 整体架构

```ascii
   Browser / Mail client
       │ URL / message
       ▼
  ┌──────────────┐
  │ Real-time    │  check vs Safe Browsing API
  │ Check API    │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Phishing DB  │  Bloom filter + Redis + Spanner
  └──────┬───────┘
         │
   ┌─────┼──────────────┐
   ▼     ▼              ▼
  Threat intel sources Crawler  ML classifier
  (vendor feeds)       (active phish hunt)
```

## 核心组件

### 1. Real-time check

Browser SDK 把 URL → hash → check **client-side Bloom filter** (small, distributed offline)。Bloom hit → query server (encrypted prefix) → confirm or deny。

**Privacy-preserving**：client sends only 4-byte hash prefix (k-anonymity)，server returns all full hashes matching prefix → client local compare。

```python
# Client-side check
hash = sha256(url)
prefix = hash[:4]  # 4 bytes
if prefix in client_bloom:   # cached locally
    server_response = server.lookup_prefix(prefix)
    if hash in server_response:
        block(url)
```

### 2. Phishing DB

100M+ known phishing URLs / domains。Update 每分钟新加 from sources：
- Vendor feeds (PhishTank, OpenPhish, internal threat intel)
- User reports
- ML classifier real-time
- Honeypot crawler

### 3. ML detection

URL features:
- Domain age, TLD, IP vs domain
- Lexical (lookalike domain "goog1e.com")
- Content features (after fetching page)
- Cert anomalies

Model: 离线 retrain daily on labeled examples。

### 4. Email-specific signals

- SPF / DKIM / DMARC fail
- Sender reputation
- Body content (suspicious URLs + urgency keywords + image-based content)

### 5. Lookalike domain detection

```python
def is_lookalike(domain):
    legit_brands = load_protected_brands()
    for brand in legit_brands:
        if edit_distance(domain, brand) <= 2:
            return True
    return False
```

Plus Unicode homograph detection (paypal.com vs pаypal.com with Cyrillic 'а').

### 6. Active crawler / honeypot

主动爬 suspicious URLs（from spam / phish reports）。Sandbox 渲染 → 看是否登陆窃取信息。Found → add to DB。

### 7. False positive 处理

User / domain owner appeal → manual review。Whitelist 误判 domain。Track FP rate to retrain model。

### 8. Distributed delivery

10B+ URLs。Bloom filter 客户端只装 popular subset；rare URLs 必须 server-side check。每天分发 incremental Bloom updates。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Privacy | k-anonymity prefix | Send full URL：privacy leak |
| Speed | Bloom + Redis + Spanner | DB-only：50ms+ |
| Detection | ML + signature + crowdsource | Single signal：low recall |
| FP | Appeal + ML retrain | None：user backlash |

## 容量估算

- 10B URLs hashed → 10B × 32 bytes = 320 GB (full hash)
- Bloom filter client-side: 1M popular URL × 8 bits = 1 MB (low overhead)
- Check QPS: 100M URL/sec aggregate worldwide → mostly client-bloom local

## 易错点

> [!pitfall]
> ❌ Server logs all URLs → privacy disaster；
> ❌ Single ML signal → FP / FN 都高；
> ❌ 不快速 incremental update → 新 phish 几小时 unprotected；
> ❌ Block 后用户没 reason → confused；显示 warning 解释。

> [!key]
> 三大要点：(1) **k-anonymity prefix** privacy-preserving check；(2) **Multi-signal ML + signature + crowdsource**；(3) **Active crawler** find new phish。

> [!followup]
> "Mobile app phishing？" → in-app SDK check before render；"Encrypted DoH / VPN bypass？" → 影响有限，主要 URL 还需 client-side check；"如何应对 AI-generated phishing emails？" → content semantic ML + sender behavior。
