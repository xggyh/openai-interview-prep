## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **AirTag** | Apple 的物品追踪小硬件 (button battery, BLE) | 钥匙扣大小的追踪器 |
| **BLE (Bluetooth Low Energy)** | 低功耗蓝牙，AirTag 用它广播 | 短距离低能耗的"喊话" |
| **UWB (Ultra-Wideband)** | 厘米级精度定位 | 精准到几厘米 vs BLE 几米 |
| **Find My network** | Apple 用全球 1B+ iPhone 中继他人 AirTag 位置 | 全球 Apple 用户帮你找物 |
| **Crowdsourcing location** | 用海量 device 提供数据 | 全民众包 |
| **E2EE (End-to-End Encryption)** | 只有 owner 能解密位置 | 信封封口，只 owner 钥匙打开 |
| **Anonymous beacon** | AirTag 广播的 ID 是匿名的、rotate 的 | 假名身份证，定期换 |
| **Rolling identifier** | ID 每 15 min 换一次防 track | 间谍代号每天换 |
| **Stalker protection** | 防 AirTag 被恶意贴到他人身上 | 反追踪报警 |
| **Find My item** | 通用 API，第三方设备也能加入 | 开放给第三方加入"找你"网络 |
| **NFC / iCloud** | AirTag 用 NFC 配对，iCloud 同步 | 近距离握手 + 云端登记 |

---

## 1. 题目本质

**Proximity Alert System for Apple Tags** = 物品丢失时 owner 看到位置。**关键**：AirTag 自己没 GPS / 没 cellular，全靠 **附近的 1B+ Apple devices 匿名中继**。

**典型产品**：
- **Apple Find My** —— AirTag, AirPods, MacBook, iPhone
- **Tile** —— 早期市场，加入 Amazon Sidewalk
- **Samsung SmartTag** —— Galaxy 生态
- **Google Find My Device network** —— Android version (2024+)
- **Chipolo, Pebblebee**

**为什么这是 STAFF 题（前沿，1 ppl 报告）**：

考的是**privacy-preserving distributed location reporting**:

1. **No-GPS device**: AirTag 自身只有 BLE，怎么知道位置
2. **Anonymous relay**: 附近 iPhone 报告 AirTag 位置，但**不能让 Apple 知道这是哪个 user**
3. **E2EE location**: Apple server **解不开** location（只 store ciphertext）
4. **Crowd density**: 城市好用，乡野差
5. **Anti-stalking**: AirTag 被恶意贴到陌生人身上，要 alert 那个陌生人

考 STAFF 关键：**privacy-preserving crowdsourcing** — 这是 Apple 真实部署 1B+ devices 的系统。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `RegisterTag(owner, tag_id)` | 注册 tag 给 user |
| `FindTag(owner) -> last_locations` | owner 查找位置 |
| `MarkLost(tag_id, contact_info)` | 标记丢失，捡到的可联系 |
| (Implicit) AirTag → 附近 iPhone → Apple → owner |
| `StalkerAlert(unknown_tag_id)` | 提醒被追踪的人 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Privacy** | Apple **不知** AirTag → user mapping (no plaintext access) |
| **Update latency** | Tag 位置 < 1 hour 后 owner 可见 (typical) |
| **Coverage** | 城市 > 95%，乡野 > 50% |
| **Battery** | AirTag 1 year on coin cell |
| **Scale** | 100M+ AirTags, 1B+ relay devices |
| **Anti-stalk** | Foreign AirTag near you > 8h → alert |

---

## 3. 容量估算

- **AirTags**: 100M active
- **Relays**: 1B iPhones globally
- **Each AirTag broadcasts every 2 s**, each iPhone scans nearby BLE periodically
- **Reports/day**: each AirTag detected ~10-100 times/day (in populated area)
- → 100M × 50 reports/day = **5B reports/day = 58k QPS sustained**
- Each report: ~200 B encrypted payload → 1 TB/day → 365 TB/year

---

## 4. 关键设计：Privacy-Preserving Architecture

### 4.1 The puzzle

If Apple **knows** AirTag 位置 + AirTag 关联 owner → Apple knows owner location everywhere.

**Apple 的承诺**: cannot know owner's location even if subpoenaed.

**怎么做到**:

### 4.2 Public key cryptography per AirTag

AirTag has private key `priv_T`, public key `pub_T`. Owner also stores `pub_T`。

**AirTag broadcasts (every 15 min, rotated)**:
- A pseudonym `pseudo_id = HMAC(priv_T, time_window)` — 不可逆 derive
- Not directly identifying — different every 15 min

### 4.3 Anonymous relay

Nearby iPhone scans BLE:
- Detects pseudo_id (doesn't know which AirTag)
- Encrypts location with **pub_T** (key the iPhone derives from the broadcast somehow)
- Wait — but iPhone doesn't know `pub_T`!

**Solution (real Apple design)**:
- AirTag broadcasts use a key derivation: each rotated `pseudo_id_i` corresponds to a `pub_T_i`
- Both AirTag (knows priv) and owner (knows priv) can derive both
- iPhone uses `pseudo_id_i` as **the public key itself** (or derives pub key from it)
- iPhone encrypts location with `pub_T_i` → reports `(pseudo_id_i, encrypted_location)` to Apple

### 4.4 Apple server's view

Sees: `(pseudo_id_i, encrypted_location, reporter_iPhone_id_hashed)`
- Cannot decrypt location (no private key)
- Cannot link pseudo_id to AirTag identity
- Just stores tuples indexed by pseudo_id

### 4.5 Owner查询

Owner phone:
- Derives all possible `pseudo_id_i` for last 7 days (knows priv_T)
- Queries Apple: `give me reports for these pseudo_ids`
- Apple returns encrypted_location tuples
- Owner phone decrypts using priv_T → see locations

**Apple still doesn't know** what was queried or returned → just stored ciphertext + handed back。

---

## 5. 高层架构

```
┌────────────────────────────────────────┐
│  AirTag                                 │
│   - Private key priv_T                  │
│   - BLE broadcast every 2s              │
│   - Rotates pseudo_id every 15 min      │
└────────────────────────────────────────┘
              │ BLE
              ↓
┌────────────────────────────────────────┐
│  Nearby iPhone (relay)                  │
│   - Scans BLE periodically              │
│   - Encrypts (its location) with        │
│     pseudo_id-derived pub key           │
│   - Sends (pseudo_id, ciphertext) → Apple│
└────────────────────────────────────────┘
              │ HTTPS
              ↓
┌────────────────────────────────────────┐
│  Apple Find My Service                  │
│   - Stores reports indexed by pseudo_id │
│   - Cannot decrypt (no priv key)        │
│   - Retention 7 days                    │
└────────────────────────────────────────┘
              │ Owner queries
              ↓
┌────────────────────────────────────────┐
│  Owner iPhone                           │
│   - Derive past pseudo_ids               │
│   - Fetch matching reports               │
│   - Decrypt locations                    │
│   - Show on map                          │
└────────────────────────────────────────┘
```

### Step 1: AirTag pairing

User taps AirTag on iPhone (NFC):
- iPhone generates `priv_T / pub_T`
- Writes `priv_T` to AirTag (via secure NFC) and to user's iCloud Keychain (encrypted with user's iCloud key)
- AirTag starts broadcasting

### Step 2: BLE broadcast

Every 2 seconds: AirTag emits BLE packet:
```
[Apple BLE manufacturer-specific]
[pseudo_id_i derived from priv_T, current 15-min window]
[battery level]
[lost flag — 1 if lost mode]
```

Power: 2-3 mA peak, ~10 μA avg → 1 year on CR2032 battery (220 mAh)。

### Step 3: Relay iPhone scans

iPhone in BG scans BLE every 30s-1min (varies by foreground/background):
- Detect AirTag pseudo_ids
- iPhone has own location (GPS + WiFi)
- Encrypt location + timestamp using pseudo_id-derived key
- Send to Apple over HTTPS (`POST /reports`)

**Privacy**: iPhone doesn't store these — just relay。

### Step 4: Apple server storage

```
table: reports
  pseudo_id (indexed, sharded by hash)
  encrypted_location (ciphertext bytes ~200 B)
  reporter_hash (anonymized iPhone id for spam detection)
  timestamp
  TTL: 7 days
```

### Step 5: Owner查询

Owner opens Find My app:
- iCloud Keychain provides priv_T
- For each AirTag, derive past 7 days of `pseudo_id_i` (~672 values)
- Query Apple: `GET /reports?pseudo_ids=[...]`
- Receive ciphertext list → decrypt locally
- Show on map

---

## 6. 组件深挖

### Deep Dive 1: Why pseudo_id rotation 15 min

**Why rotate**:
- 防 cross-day tracking by attacker scanning continuously
- If pseudo_id stable: attacker logs "I saw pseudo_X at coffee shop Mon 9am, Tue 9am... that's same person's commute"
- Rotated: each session shows different pseudo_id → can't link

**Why 15 min and not shorter**:
- Battery: more crypto ops per broadcast = more power
- Server storage: more unique pseudo_ids
- 15 min is enough for "lost AirTag won't be found within 15 min anyway"

### Deep Dive 2: Server cannot decrypt — guarantees

Apple internal:
- Reports DB encrypted at rest (Apple key)
- Even Apple employees with full DB access see only ciphertext
- Owner phone is **only** entity with priv_T → only entity that can decrypt
- **External attacker breaching Apple DB** still see only ciphertext
- **Government subpoena**: Apple can produce ciphertext only — useless without priv_T

This is **E2EE at infrastructure level**, not just transport。

### Deep Dive 3: Anti-Stalker Protection

Threat: someone hides AirTag in your bag/car → tracks you.

**Defense**:
1. **Unknown AirTag detection**: iPhone tracks AirTag pseudo_ids it sees over time. If same AirTag (clustered by physical proximity heuristics, since pseudo rotates) is with you > N hours without being its owner → **alert: "AirTag found moving with you"**
2. **Sound alarm**: After 8-24 hours separated from owner, AirTag plays sound → discoverable by victim
3. **Disable / NFC ID**: victim can tap AirTag with phone (NFC) → reveal partial ID + serial → report to authorities
4. **Pre-configured allowlist**: owner can mark "shared use" so co-located people don't get alerts (e.g., couple sharing keys)

**Challenge**: iPhone clustering "same AirTag" with rotating ID is non-trivial — uses signal pattern + co-occurrence + ML。

### Deep Dive 4: Reporting Frequency vs Battery

iPhone battery is precious — frequent BLE scan drains。

**Background scan throttling**:
- Foreground app: scan every 1s
- Background: scan every 30-60s (iOS controls aggressively)
- "Find My" app open: aggressive scan

**Crowd density**: in city, many iPhones contribute → each one scans less often, aggregated coverage 仍 high。In rural area, fewer relays → updates sparse。

### Deep Dive 5: Adaptive Lost Mode

When AirTag is "lost":
- Owner marks lost via Find My app
- Apple notifies AirTag through BLE next time it's relayed (via signed message back to AirTag)
- AirTag enters "lost mode": broadcast includes lost flag + URL for finder
- Stranger taps AirTag with phone → NFC + URL shows owner contact info

### Deep Dive 6: Cross-Vendor Open Network

**Google Find My Device** (2024) joins:
- Cross-platform spec for AirTag-like devices
- Anti-stalker alerts work across iPhone + Android
- Open spec: third-party makers (Chipolo, Pebblebee) make devices that work in both Apple and Google networks
- Privacy-preserving same way

**Architectural impact**:
- iPhone relays Android tags too (with separate keys)
- Servers (Apple and Google) interoperate via anti-stalker API
- Standard format for tag broadcasts

### Deep Dive 7: Scale of Reports

5B reports/day:
- Storage 1 TB/day × 7 days = 7 TB hot
- Sharded by pseudo_id hash
- Owner query: 672 pseudo_ids → multi-shard parallel fetch
- Most queries return < 100 hits → small payload back to owner

**Reporter spam**: bot creates fake reports? Mitigate:
- Reporter device must be authenticated iPhone (Apple ID)
- Rate limit reports per device
- Anomaly detect: same device reports for many different pseudos in short period

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：privacy要求, crowd network 假设, stalker protection |
| 5-10min | 容量：100M AirTags × 1B relays, 5B reports/day |
| 10-15min | 关键设计：E2EE + anonymous relay, why server 解不开 |
| 15-25min | 高层架构: AirTag → BLE → iPhone relay → Apple server → owner phone decrypt |
| 25-40min | Deep dives: pseudo_id rotation / anti-stalker / battery / cross-vendor / scale |
| 40-45min | adaptive lost mode / spam |

---

## 8. 样板讲解稿

> 这题核心是 **privacy-preserving crowdsourced location**。AirTag 没 GPS / 没 cellular，靠 1B+ Apple device crowd 中继。
>
> **关键约束**：Apple 自己**不能知道** AirTag 在哪 (privacy promise) → 必须 E2EE。
>
> **架构**：
> 1. AirTag has priv key, broadcasts rotated `pseudo_id` every 15 min via BLE
> 2. Nearby iPhone scans BLE, encrypts its location with `pseudo_id`-derived pub key, posts (pseudo_id, ciphertext) to Apple
> 3. Apple server stores ciphertext indexed by pseudo_id — **cannot decrypt**
> 4. Owner phone derives past pseudo_ids (has priv) → fetch reports → decrypt locally
>
> **Privacy guarantees**:
> - Apple sees only ciphertext (E2EE infra-level)
> - Rotating pseudo_id prevents tracking across sessions
> - Reporter iPhone identity hashed (anonymous)
>
> **Anti-stalker**:
> - Foreign AirTag near you > 8h → alert
> - AirTag plays sound after 8-24h separation from owner
> - NFC reveal for victim
>
> **Scale**: 5B reports/day, 7-day retention = 7 TB hot。
>
> **Battery**: BLE every 2s, ~10μA avg → CR2032 1 year。

---

## 9. Follow-up Q&A

### Q1: "iPhone doesn't know AirTag's pub key, how does it encrypt?"

**A**：Brilliant Apple trick: the rotated `pseudo_id` itself serves as **the public key** (or short-form: pub key is derivable from pseudo_id given some shared parameters)。 Specifically, the cryptographic scheme uses **elliptic curve point** as both pseudo_id (broadcast) and pub key — iPhone encrypts with this point, owner who has priv can decrypt。

### Q2: "How does the iPhone cluster same AirTag with rotating pseudo_id (for anti-stalker)?"

**A**：Heuristics:
- Same physical co-location over time
- Signal pattern (RSSI) consistency
- Time-based: pseudo_id_t and pseudo_id_t+1 (15 min later) share key derivation → iPhone can store last seen pseudo_id and check next one
- Apple's actual algorithm has cryptographic tweaks to allow trusted relays to link without full identity disclosure

### Q3: "Lost mode 怎么 owner 把消息 push 回 AirTag？"

**A**：reverse channel via relay:
- Owner marks lost → Apple writes signed "lost" message in ciphertext tied to AirTag's future pseudo_ids
- Next time iPhone relays an report for this pseudo_id, server pushes signed message back through iPhone via BLE write
- AirTag verifies signature (owner's pub key) → enters lost mode + plays sound

### Q4: "如果 Apple 想偷偷解密 AirTag 位置呢？"

**A**：cryptographically impossible without owner's priv key。Apple does have iCloud Keychain — priv keys ARE there but they're encrypted with **user's** iCloud key (derived from user's password + secure enclave)。Apple doesn't have plaintext access to keychain。

**Defense in depth**：
- iCloud Keychain Advanced Data Protection: Apple cannot access even if it wanted to
- Subpoena: Apple can hand over encrypted blobs, useless without password

### Q5: "5B reports/day storage 怎么 efficient?"

**A**：
- Sharded by `pseudo_id[:n]` prefix → 1000 shards
- Each report ~200 B encrypted + 32 B metadata = 232 B → 5B × 232 B = 1.1 TB/day raw
- 7-day retention → 7.7 TB hot in S3 / Cassandra
- TTL deletion automatic at 7d

### Q6: "Rural area coverage 差，怎么改善？"

**A**：
- Encourage AirTag plus on cars (always-on relay)
- Future: pair with low-orbit satellite networks (Find My satellites?)
- Tile / SmartTag join Apple network = denser crowd
- Apple Watch / AirPods also relay = more devices on body

### Q7: "Anti-stalker 误判怎么办？"

**A**：whitelist + UX:
- Owner can mark "shared use" (couple sharing keys, family)
- iPhone alert: "Unknown AirTag traveling with you" + option to view / dismiss / mark friendly
- Repeat alerts only daily, not every hour
- Children's iPhones: stricter alerting (school staff don't accidentally trigger)

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **Server stores plaintext location** → privacy violation
2. **Static pseudo_id** → trackable across sessions
3. **Owner phone constantly polls** → battery drain
4. **No anti-stalker** → AirTag 被恶意 weaponized
5. **Tag broadcasts identifying info** → privacy leak
6. **AirTag has GPS / cellular** → battery dies in days
7. **Pure server-side detection** without crowd network → impossible at scale

### ✅ 加分项

1. **E2EE infrastructure** (server cannot decrypt)
2. **Rotated pseudo_id** for unlinkability
3. **Crowdsourced anonymous relay**
4. **Anti-stalker layered**: alert + sound + NFC reveal
5. **Cross-vendor open spec** (Google Find My Network)
6. **Lost mode signed message back-channel**
7. **Battery 1 year** via BLE-only + crypto-light per packet
8. **Whitelist for shared use** UX

> [!key] STAFF vs SENIOR：能讲清 **E2EE + rotating pseudo_id + crowd relay + anti-stalker** 完整 stack 是 STAFF；只说 "tag → server → owner" 是 SENIOR。

---

## 11. Cheat Sheet

```
核心: Privacy-preserving crowdsourced location
  AirTag: BLE-only, no GPS, no cellular
  Relay: nearby iPhones (1B+)
  Server: stores ciphertext only

Crypto:
  AirTag has priv_T; owner has priv_T via iCloud Keychain
  Broadcast rotated pseudo_id every 15 min
  pseudo_id derivable as pub key for encryption
  Owner derives past pseudo_ids → fetch → decrypt locally

Privacy guarantees:
  Apple server: cannot decrypt locations
  Rotated ID: cannot track across sessions
  Reporter iPhone: anonymized

Anti-stalker:
  Detection: foreign AirTag near you > 8h → alert
  Sound: AirTag plays after 8-24h separation
  NFC: tap reveals identity (for victim/authorities)
  Whitelist: shared/family use

Battery:
  CR2032 ~220 mAh
  BLE 2s broadcast, 10 μA avg
  ~1 year life

Scale:
  100M AirTags × 1B relays
  5B reports/day = 58k QPS
  1.1 TB/day, 7-day retention = 7.7 TB hot
  Sharded by pseudo_id prefix

Storage:
  Reports table (pseudo_id, ciphertext, ts)
  TTL 7 days
  Sharded 1000 ways
  No PII server-side

Cross-vendor:
  Google Find My Network (2024+)
  Common standard for tags
  Anti-stalker works cross-platform
```
