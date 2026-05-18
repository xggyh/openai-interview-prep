## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **WORM (Write-Once Read-Many)** | 数据写后**不可修改 / 删除** | 印刷在书上的字，不可改 |
| **Immutability** | 数据一旦写入永不变 | 雕刻在石碑上 |
| **Append-only log** | 只能在末尾添加，不能改 | 流水账 |
| **Append-only file** | 文件只追加，不 truncate | 通讯录最后加新人 |
| **Tape / LTO** | 磁带存储，传统 archival 介质 | 老式磁带 |
| **Object lock** | S3 / GCS 强制 WORM 的功能 | "这箱货 7 年不许动" |
| **Compliance** | 法律 / 法规要求的保存 | 法律规定保留 |
| **Retention period** | 数据必须保留的时长 | "财务记录 7 年内不删" |
| **Legal hold** | 法律调查期间的强制保留 | 暂时不许动 |
| **Erasure coding** | 用算法把数据 + 校验位分散，丢部分可恢复 | "10 份原文 + 4 份校验" |
| **Checksum / hash** | 数据完整性指纹 | DNA 比对 |
| **Cold storage** | 不常用，便宜慢的存储 | 仓库 vs 桌面 |
| **Audit trail** | 所有访问 / 操作 immutable 记录 | 监控录像 |

---

## 1. 题目本质

**File System for Write-Once Media** = WORM 存储系统，数据写后**绝对不可修改**。

**典型场景**：
- **金融 / 银行 transaction log** —— SEC 17a-4 要求 7 年 immutable
- **HIPAA medical records** —— 患者数据保留 +20 年
- **Blockchain** —— 链上数据不可篡改
- **Cryptocurrency exchange order book** —— 监管要求
- **GDPR audit log** —— 数据访问可追溯
- **Legal e-discovery archive** —— legal hold

**典型产品**：
- **AWS S3 Object Lock** —— compliance mode (不可删) + governance mode (root 才能删)
- **AWS Glacier Vault Lock**
- **Azure Immutable Blob Storage**
- **NetApp SnapLock**
- **Centera (EMC)**
- 历史：CD-R, DVD-R, magneto-optical, LTO tape

**为什么这是 STAFF 题（前沿合规场景）**：

考的是 **"如何保证 immutability"** 这个分布式系统硬题：

1. **No-delete enforcement** — 即使 admin / root 也不能删
2. **Long-term durability** — 7 年 / 100 年存储
3. **Verification** — 取出时能证明没改过
4. **Erasure coding** for cost
5. **Cold tier retrieval** — 几小时 vs 几秒
6. **Replication + integrity** 协同

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `Write(path, data, retention_until) -> object_id` | 写入新对象 |
| `Read(object_id) -> data` | 读 |
| `Delete(object_id)` | **写入后** 即使是 owner 也不能 delete 直到 retention 到期 |
| `ApplyLegalHold(object_id)` | 法律 hold，更难删 |
| `Verify(object_id) -> {valid, checksum}` | 完整性校验 |
| `ListVersions(path)` | 同 path 历史版本（每次 write 是新 object） |

### Non-functional

| 维度 | 目标 |
|---|---|
| **Durability** | 11 个 9 (或更高，archive 通常 14 个 9) |
| **Retention** | 7-100 年（合规） |
| **Immutability guarantee** | 绝对 — root / OS bypass 都不允许 |
| **Write throughput** | varies by use; for log: 100k events/s |
| **Read latency** | hot: ms; archive: minutes-hours |
| **Cost** | minimize for cold (10 PB scale) |
| **Verification** | < 1s per object |

> [!key] **Immutability 是这道题灵魂**。任何 design 不能依赖"约定不删"，必须是**机制上无法删**。

---

## 3. 容量估算

- **金融 transaction log**: 1 大行 1B txn/day × 1 KB = 1 TB/day = **365 TB/year**
- 保留 7 年: **2.5 PB** per institution
- 100 institutions: **250 PB total**
- 12 个 9 durability + 7-year retention → cold tier is necessary

---

## 4. 关键设计：Immutability 机制

### 4.1 Why "约定" 不够

Naive：API 不暴露 delete operation → 但 admin SSH 到机器可以 rm。**Not enough for compliance**。

### 4.2 Mechanical immutability strategies

**Strategy 1: Hardware WORM media**
- CD-R / DVD-R: 物理只写一次 (commercial-grade)
- LTO tape with WORM cartridges: 写后磁条物理 locked
- 缺点: 慢、不便

**Strategy 2: Object Lock with Compliance Mode (S3)**
- Object 被 lock 后 **even AWS account root cannot delete** until retention expires
- Implementation: enforce at storage system level — special bit in metadata + service refuses delete API
- AWS 是公司层面 commit；客户信任 AWS won't bypass

**Strategy 3: Cryptographic chain**
- Each object 包含 prev object hash → 形成 hash chain
- Tamper with old object → 后续所有 hash 不对
- 配合 **external anchor**: periodic root hash published 到不可篡改外部系统 (blockchain / time stamp authority)
- 这是 blockchain 灵感

**Strategy 4: M-of-N consensus deletion**
- 删除 require N 个 trusted parties 同意（key sharding）
- 单 admin 不能删
- 实际：S3 governance mode 用 IAM 策略实现

**STAFF 推荐**：combination
- Service-level enforcement (refuses delete API)
- Hash chain for tamper detection
- M-of-N for governance mode if customer wants admin recovery path

---

## 5. 高层架构

```
┌──────────────────────────────────────┐
│  Client (write request)               │
└──────────────────────────────────────┘
              │ Write(data, retention)
              ↓
┌──────────────────────────────────────┐
│  Ingestion / Validation Service      │
│   - Compute SHA256 of data            │
│   - Get prev object hash              │
│   - Compute chained hash              │
│   - Issue object_id                   │
└──────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────┐
│  Storage Layer (tiered)               │
│   ├── Hot: 3x SSD (last 30 days)      │
│   ├── Warm: 3x HDD (1 year)           │
│   └── Cold: erasure-coded S3/Glacier  │
└──────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────┐
│  Metadata Index                       │
│   - path → object_id chain            │
│   - retention_until per object        │
│   - hash chain links                  │
└──────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────┐
│  Background Services                  │
│   - Verifier (周期 checksum scan)     │
│   - Tier mover (hot → warm → cold)    │
│   - Anchor service (publish roots)    │
│   - GC for expired (only after retention)│
└──────────────────────────────────────┘
```

### Step 1: Write path

```python
def write(data, retention_until):
    # 1. Compute data hash
    data_hash = sha256(data)
    
    # 2. Get latest object's hash (from index)
    prev = get_latest_object_id()
    prev_hash = get_hash(prev)
    
    # 3. Compute chained hash
    chain_hash = sha256(data_hash + prev_hash)
    
    # 4. Allocate new object_id (monotonic + UUID)
    object_id = f"{timestamp}_{uuid4()}"
    
    # 5. Write to hot storage (3 replicas)
    storage.write(object_id, data, chain_hash, retention_until)
    
    # 6. Update metadata
    index.append(object_id, prev, chain_hash, retention_until)
    
    # 7. Async: anchor root
    return object_id
```

### Step 2: Read path

```
Client: Read(object_id)
  → Metadata lookup → which tier? 
  → If hot/warm: direct read 
  → If cold: trigger restore (Glacier 3-5 hour) or restored cache
  → Verify checksum on read
  → Return data
```

### Step 3: Tier movement

Background job:
- Object aged > 30 days + not accessed in 7 days → move hot → warm
- Object aged > 1 year → move warm → cold (erasure coded S3 Glacier)
- Object's `retention_until` reached → enable GC (still requires multi-party for compliance mode)

**Key**: object_id never changes. Only physical location changes.

### Step 4: Verifier

Daily background:
- Scan random sample (1%) of objects
- Read + verify chained hash
- If mismatch detected → trigger investigation + alert

Anchor service:
- Daily compute global root hash (hash of all today's chained hashes)
- Publish to **immutable external system** (blockchain timestamp, or notarization API)
- Provides "global checkpoint" — anyone can later verify "as of date X, system had this hash"

---

## 6. 组件深挖

### Deep Dive 1: Erasure Coding for Cold Tier

10 PB scale, 3× replication = 30 PB → expensive。

**(10+4) Reed-Solomon**:
- 10 chunks original + 4 parity chunks
- Survive any 4 lost chunks
- Storage overhead: 1.4× (vs 3×) → save 53%
- Read slower (need to decode if a chunk missing)

For archive (rarely read), this is great trade-off。

### Deep Dive 2: Hash Chain Tampering Detection

Object N points to N-1 via hash:
```
obj_0: data_0, chain_hash_0 = sha256(data_0_hash || genesis)
obj_1: data_1, chain_hash_1 = sha256(data_1_hash || chain_hash_0)
obj_2: data_2, chain_hash_2 = sha256(data_2_hash || chain_hash_1)
...
```

If attacker modifies obj_1's data → data_1_hash changes → chain_hash_1 should change → but stored chain_hash_1 still old → mismatch → detected.

**Verification cost**: O(N) to verify whole chain. Better: **Merkle tree** — group N objects into tree, verify chain is O(log N)。

### Deep Dive 3: External Anchoring

Even hash chain in your own system → if attacker compromises your system, they can rewrite chain.

**Anchor to external trusted system**:
1. Daily root hash → publish to **Bitcoin / Ethereum** transaction (small fee, immutable timestamp)
2. Or **Google Trust Authority** / **DigiCert TSA**
3. Or **Lightning Network / mass time stamping**

This gives **cryptographic proof of pre-existence** — "this hash existed on date X" verifiable independently。

### Deep Dive 4: Retention Enforcement at Storage Level

**S3 Object Lock COMPLIANCE mode**:
- Object metadata includes `Retain-Until-Date`
- Internal API check on every DELETE / OVERWRITE / DELETE-MARKER
- AWS internally enforces: cannot bypass even with root creds

**Our implementation**:
```python
def delete(object_id):
    obj = metadata.get(object_id)
    if obj.retention_until > now():
        raise RetentionViolation
    if has_legal_hold(object_id):
        raise LegalHoldViolation
    # All checks pass → physical delete
    storage.delete(object_id)
```

**Key**: this check is in the **only** code path that can issue physical delete commands。No back door.

### Deep Dive 5: Legal Hold

Indefinite hold during legal investigation。

- Set `legal_hold = true` on object → delete blocked even after retention expires
- Multiple legal holds can coexist (different cases)
- Only specific privileged role can remove hold
- Removal audited

### Deep Dive 6: Disaster Recovery

7-year data — disasters guaranteed in that window。

**Defense in depth**:
1. **3+ replicas** (or erasure coded with sufficient parity)
2. **Cross-region** replication (different geographic disasters uncorrelated)
3. **Cross-provider** (one copy in AWS, one in GCP for true独立)
4. **Cross-medium** (one tape-based offline copy)
5. **Periodic integrity scan** + repair from healthy replicas

### Deep Dive 7: Read Latency Tiers

| Tier | Latency | Cost | Use case |
|---|---|---|---|
| Hot (SSD) | 1-10 ms | $0.10/GB/mo | last 30 days, fresh access |
| Warm (HDD) | 10-100 ms | $0.02/GB/mo | 1-year, occasional access |
| Cold (Glacier) | 3-5 hours | $0.001/GB/mo | archive, rare retrieval |
| Deep archive (Glacier Deep Archive) | 12-48 hours | $0.0004/GB/mo | compliance archive |

**Tier transition automated** based on access pattern + retention age。

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：compliance scope (SEC/HIPAA?), retention period, throughput |
| 5-10min | 容量：2.5 PB per inst × 100 inst = 250 PB |
| 10-15min | Immutability mechanism (机制 vs 约定) |
| 15-25min | 高层架构：ingest → hash chain → tiered storage → metadata |
| 25-40min | Deep dives: hash chain / anchoring / EC / retention enforcement / legal hold |
| 40-45min | DR / cost optimization |

---

## 8. 样板讲解稿

> WORM 存储核心是 **immutability must be mechanical, not 'we promise'**。
>
> **关键设计**:
> 1. **API 层**: 只有 `Write/Read/Verify`，无 modify/delete (until retention expires)
> 2. **Storage 层**: S3 Object Lock COMPLIANCE mode — root 也不能 delete
> 3. **Hash chain**: each object 链接前一个 hash → 改老 detect 链断
> 4. **External anchor**: daily root hash to immutable system (e.g., blockchain timestamp / TSA)
> 5. **M-of-N for emergency**: governance mode needs multiple key holders agree
>
> **架构**：
> 1. Write → ingestion compute SHA256 + chained hash + retention → store
> 2. Tiered: SSD (30d) → HDD (1y) → Glacier EC (long-term)
> 3. Metadata: path → object chain
> 4. Verifier: daily 1% sample check
> 5. Anchor: daily root → external timestamp service
>
> **DR**: 3+ replicas cross-region, optionally cross-provider/cross-medium。
>
> Numbers: 250 PB scale, 11+ 个 9 durability, 7-year+ retention。

---

## 9. Follow-up Q&A

### Q1: "S3 Object Lock 真的不能被 AWS root 删？"

**A**：是 AWS commitment level enforcement。Code 层面 S3 API server 实现 strict check + audit。AWS doesn't have a "secret backdoor" delete API (would invalidate SEC certification)。If AWS root really wanted to delete: would require source code change + deploy + audit trail visible。**信任 AWS engineering integrity**。

For higher security: cross-provider replication (also store in Azure / GCP)。

### Q2: "Hash chain 攻击者重写所有 N 个 hash 也可以？"

**A**：如果只有 your system → 可以。**External anchor** 防：daily root hash published 到 Bitcoin txn → attacker would have to also rewrite Bitcoin chain (computationally infeasible)。

### Q3: "10 PB cold storage cost 多少？"

**A**：
- Glacier Deep Archive: $0.00099/GB/mo → 10 PB × $0.00099 × 12 = **$120k/year**
- vs Glacier: $0.004/GB/mo → $480k/year
- vs S3 Standard: $0.023/GB/mo → $2.8M/year

Right tier choice 10× cost。

### Q4: "Retention 7 年到期后，怎么 GC？"

**A**：
- Daily job scan objects with `retention_until < now`
- 如果 governance mode: 需要 M-of-N key holder approve delete batch
- 如果 compliance mode: auto-delete + log
- 物理 delete 不可逆，先 verify no legal hold + 关键 metadata kept (audit, hash chain entry)

### Q5: "Object 1 万亿条，metadata 怎么存？"

**A**：
- 1T × 100 B metadata = 100 TB → sharded SQL / Spanner
- 按 path 前缀 / time bucket 分 shard
- 索引 by (path, object_id) for version listing
- 索引 by (retention_until) for GC sweep

### Q6: "Tape storage 还有用吗？"

**A**：是。LTO-9 tape: $0.005/GB/mo physical (no cloud)，better for super-long retention。但运维麻烦，多数公司用 S3 Glacier Deep Archive 代替。Tape 主要 enterprise on-prem。

### Q7: "GDPR 'right to be forgotten' 跟 WORM 冲突怎么办？"

**A**：合规冲突。**Resolve**:
- 法规优先级: WORM (SEC) > GDPR for financial systems
- 对其他系统：tokenize user data + scrub original after retention
- Some systems: WORM data + scrub PII fields → archive de-identified version

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **"我们 promise 不删"** → admin 仍可 SSH 删，不合规
2. **没 hash chain** → 个别 object 篡改无法 detect
3. **All hot SSD** → 10 PB 几百万美元 / 年
4. **没考虑 legal hold** → 法律调查时不能 freeze
5. **Anchor 不外部化** → 全系统 compromise 仍 rewritable
6. **Retention enforcement 不机械** → 依赖 IAM 策略不够
7. **没 tiered storage** → cost 失控

### ✅ 加分项

1. **Mechanical immutability** (S3 Object Lock COMPLIANCE)
2. **Hash chain + external anchor** (blockchain / TSA)
3. **Erasure coding** for cold tier (1.4× vs 3×)
4. **Tiered storage** with auto-migration
5. **Legal hold** model
6. **M-of-N governance** for admin path
7. **Cross-provider replication** (AWS + Azure)
8. **Daily verifier + repair**

> [!key] STAFF vs SENIOR：能讲清 **"mechanical not promised" + hash chain + external anchor** 是 STAFF；只说 "store in S3 + don't delete" 是 SENIOR。

---

## 11. Cheat Sheet

```
核心: Immutability must be mechanical
  - S3 Object Lock COMPLIANCE mode
  - Code path enforces retention check
  - No back-door delete API
  - M-of-N governance for emergency

Hash chain:
  obj_N hash includes obj_{N-1} hash
  Tamper old → break chain → detect
  Merkle tree for O(log N) verification

External anchor:
  Daily root hash → Bitcoin/TSA
  Independent proof of pre-existence

Tiered storage:
  Hot SSD (30d, $0.10/GB/mo)
  Warm HDD (1y, $0.02/GB/mo)
  Cold Glacier EC (long-term, $0.001/GB/mo)
  Deep archive ($0.0004/GB/mo)

DR:
  3+ replicas cross-region
  Cross-provider (AWS+Azure+GCP)
  Periodic verifier + repair

Retention/Legal:
  retention_until per object
  legal_hold flag (overrides retention)
  Auto-GC after retention + no holds

数字:
  2.5 PB per institution × 100 = 250 PB
  11-14 个 9 durability
  7-100 year retention
  Verifier 1% daily scan
```
