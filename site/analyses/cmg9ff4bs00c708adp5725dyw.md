## 题目本质

设计 **Block Storage System** (AWS EBS / GCP Persistent Disk)：给 VM / container 提供持久 block device。读写 raw block，VM 之上看是 disk。

## 需求

- 容量：1GB-16TB per volume
- IOPS：1k-256k per volume
- Latency：< 1ms read/write
- Durability：99.999%（11 9s）
- Snapshot / clone

## 整体架构

```ascii
   VM
    │ block read/write
    ▼
  ┌──────────────┐
  │ Volume       │  hypervisor-attached block dev
  │ Attachment   │
  └──────┬───────┘
         │ iSCSI / NVMe-oF / proprietary protocol
         ▼
  ┌──────────────────────────┐
  │ Distributed Block Server │  分布式 + replicated
  │ - chunk = 4-16 MB        │
  │ - 3 copies per chunk     │
  │ - 跨 AZ 副本             │
  └──────┬───────────────────┘
         │
         ▼
  ┌──────────────┐
  │ Backing      │  HDD / SSD pool
  │ Storage      │  per-rack distributed
  └──────────────┘
```

## 核心组件

### 1. Volume → Chunk mapping

Volume 切成 4-16 MB chunks。每 chunk 有 unique ID。Volume metadata = chunk list + ordering。

Lookup: `volume[offset] = chunk[offset // chunk_size][offset % chunk_size]`。

### 2. 3-way replication

每 chunk 3 copies on 不同 rack / AZ。Write：
- Primary 接 client → forward to 2 replicas → wait majority ack → ack client

读：直接 primary 或 nearest replica。

### 3. Consistency

Strong consistency：write 必须 majority ack。Quorum (R+W > N，2+2 > 3) 保证 read 看到 latest。

### 4. Snapshot

**Copy-on-write**：snapshot = chunk pointer 复制（O(1) 时间）。后续 volume 写时把 chunk copy 出来再写新版本。Snapshot 看的是原 chunk pointer。

Snapshot 后 incremental backup → S3。

### 5. Clone

Clone = snapshot + new metadata。新 volume 共享 chunk pointer，CoW on write divergence。

### 6. Tiering

Hot chunks → SSD pool；cold chunks → HDD pool。
- Track access time per chunk
- 周期 migration job 把冷 chunk 下沉

### 7. Encryption

每 volume 一个 key（来自 KMS）。Chunk read 时即时 decrypt（AES-NI 硬件加速）。

### 8. Failure handling

- Replica fail：检测后自动 spawn 新 replica（复制 chunk from healthy copies）
- Network partition：写不能达 majority → block 写 + return error，避免 split-brain

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Chunk | 4-16 MB | KB：metadata 爆；GB：恢复慢 |
| Replication | 3 sync majority | Async：丢数据 |
| Snapshot | CoW pointer | Full copy：贵 |
| Tiering | Hot/cold by access time | All SSD：贵；All HDD：慢 |
| Protocol | iSCSI / NVMe-oF | Custom：兼容差 |

## 易错点

> [!pitfall]
> ❌ Async replication → power fail 丢数据；
> ❌ 不 majority quorum → split-brain；
> ❌ Snapshot 直接 copy → 贵；
> ❌ Single rack replicas → AZ fail 全丢；
> ❌ No encryption at rest → compliance fail。

> [!key]
> 三大要点：(1) **Chunk + 3-way sync replication** 提供 durability；(2) **CoW snapshot** O(1) 时间；(3) **Tiering + KMS encryption** 实战必备。

> [!followup]
> "Multi-attach (多 VM 同 volume)？" → 需要 distributed lock / cluster filesystem；"Object storage (S3) 兼用？" → 不同 API，不同需求 (object 大，no random write)；"NVMe-oF 走 RDMA？" → < 100μs latency 可能。
