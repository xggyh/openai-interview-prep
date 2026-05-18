## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Block storage** | 把存储切成固定大小的"块"（4KB-64KB），按块读写 | 仓库被分成一格格货架 |
| **Volume** | 用户看到的一个"虚拟硬盘"，由很多 block 组成 | 一整个货架（很多格） |
| **EBS / GCP PD** | AWS / GCP 的产品名 | 商用品牌 |
| **VM** | 虚拟机，挂载 volume 使用 | 顾客租用货架的人 |
| **IOPS** | Input/Output Operations Per Second | 一秒能搬多少次货 |
| **Throughput** | 单位时间数据量 (MB/s) | 一秒搬多少 kg 货 |
| **Read-after-write** | 写完立即读保证看到最新值 | 放完货立刻取，必须取到刚放的 |
| **Snapshot** | 某一刻 volume 的快照，用来备份 / 克隆 | 货架的全景照片 |
| **Extent / chunk** | volume 内部切分的中等单位（1GB-4GB） | 货架的一层 |
| **Replication** | 一份数据存多份防丢 | 重要货物在 3 个货架各存一份 |
| **Quorum** | 多数同意才算成功 | 3 个仓管中 2 个签字才能出货 |
| **Failure domain** | 一起挂掉的范围 | 同一栋楼里的所有货架 |
| **Metadata plane** | 管 volume → chunk → 物理位置的映射 | 仓库前台的"货物登记本" |
| **Data plane** | 实际读写数据的路径 | 仓库里的传送带 |
| **Journal / WAL** | 写日志先 append，再 apply 到数据 | 先签收单子，再上货 |
| **Erasure coding** | 比 replication 省空间的容灾编码 | 10 份原文 + 4 份校验，丢 4 份还能恢复 |
| **Copyset placement** | 限制副本只能在固定组合中，降低"多盘同时挂数据全丢"概率 | 备份只放固定几间分行 |

---

## 1. 题目本质

**Block storage** = 给 cloud VM 提供"虚拟硬盘"的分布式存储系统。VM 把它当本地磁盘用（mount 后 `/dev/sdb`），但底层是跨多机的分布式系统。

**典型产品**：AWS EBS / GCP Persistent Disk / Azure Managed Disks / Ceph RBD / 企业 SAN (NetApp).

**为什么这是高频 STAFF 题（2 ppl 报告，Google 内部高频）**：

跟 cache 完全不同 —— 这是**"数据丢一份就是灾难"**的系统。考的是：

1. **Strong consistency**：写完立刻读到新值，不能 eventual
2. **Durability** vs latency 的极限 trade-off：11 个 9 的耐久 + ms 级延迟
3. **Metadata plane**：1B volumes × 1000 chunks = 1T 行 mapping，怎么管
4. **故障恢复**：盘挂了怎么 silent rebuild 不影响前台 IO
5. **Multi-tenant 性能隔离**：noisy neighbor

考 STAFF 关键：**不是知道 EBS 怎么用，而是知道 EBS 内部怎么实现**。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `CreateVolume(size, perf_class, az) -> volume_id` | 申请虚拟硬盘 |
| `AttachVolume(volume_id, vm_id)` | 挂到 VM |
| `Read(volume_id, offset, length) -> data` | 读 |
| `Write(volume_id, offset, data)` | 写 |
| `Snapshot(volume_id) -> snapshot_id` | 快照 |
| `RestoreFromSnapshot(snapshot_id) -> new_volume_id` | 恢复 |
| `DeleteVolume(volume_id)` | 删除 |

### Non-functional

| 维度 | 目标 |
|---|---|
| **延迟** | p99 < 1 ms (in-AZ read/write) |
| **IOPS** | 16k-256k / volume |
| **Throughput** | 250 MB/s - 4 GB/s / volume |
| **Durability** | **11 个 9** |
| **Availability** | 99.95-99.99% |
| **Consistency** | **strong (linearizable)** |
| **Scale** | 1B+ volumes, exabyte total |

> [!key] 跟 cache 最大区别：**durability 是必须的，所有设计要绕这个核心**。

---

## 3. 容量估算

- 1B volumes × 100 GB avg = 100 EB total
- 每 volume 1000 IOPS → 1 万亿 IOPS aggregate
- Hot (10%): 10 EB × 3 replicas = 30 EB → 30万台 100TB 机器
- Cold (90%): 90 EB × 1.4 erasure = 126 EB → 126万台
- **Total ~150万台机器**

Metadata: 1B volumes × 1000 chunks × 200 B = **200 TB metadata** → 必须分布式 metadata plane。

---

## 4. 高层架构

### Step 1: Control plane vs Data plane 分离

```
┌──────────────────────────────────────────┐
│  Control Plane (慢，万级 QPS)              │
│  - CreateVolume / Snapshot                │
│  - Metadata DB                            │
└──────────────────────────────────────────┘
                  │
                  ↓ (metadata cache on VM host)
┌──────────────────────────────────────────┐
│  Data Plane (快，百万级 QPS)               │
│  - VM → Chunk Server direct               │
│  - 不经过 control plane                    │
└──────────────────────────────────────────┘
```

### Step 2: Volume 拆 chunks

100 GB volume → 100 个 1 GB chunk，每个 chunk 分到不同 chunk server。

**好处**：并行 IO、容易 rebalance、故障爆炸半径小。

### Step 3: 每个 chunk 3 副本

```
chunk 0:
  ├── primary → server A1
  ├── replica → server A2 (不同机架)
  └── replica → server A3 (不同 AZ)
```

### Step 4: Metadata plane

- 分布式 KV (Spanner / 自建 Paxos)
- VM host 拉取 metadata cache (lease-based)
- 200 TB 全局 metadata，按 volume_id sharded

### Step 5: VM host agent

每个 hypervisor 上跑 storage agent：拦截 VM disk IO → 查 metadata cache → 直接走 RDMA / NVMe-oF 给 chunk server。

### Step 6: Snapshot — copy-on-write

```
T0: volume V → [c0_v1, c1_v1, c2_v1]
T0: take snapshot S → points to same chunks (refcount += 1)

T1: write to chunk 1
  → new c1_v2 created (COW)
  → V → [c0_v1, c1_v2, c2_v1]
  → S unchanged

→ Snapshot 几乎瞬间，几乎不占空间
```

---

## 5. 组件深挖

### Deep Dive 1: Strong Consistency + Low Latency

**痛点**：3 副本同步写 → 至少 1 个 RTT + 等慢副本 → p99 拖累。

**解法（journal-based quorum write）**：

1. Client → primary
2. Primary write journal entry locally (50μs SSD log)
3. Primary sync journal to 1 replica via RDMA (50μs)
4. **2/3 journal acked → ack client (~150μs total)**
5. (async) Primary apply journal to data block + propagate to 3rd replica

**关键**：journal 是小 IO，复制快；data block 大 IO 但异步。Aurora / GFS 都是这思路。

### Deep Dive 2: Metadata Plane Scale

**1T entries**：

- 按 volume_id sharded SQL (Vitess / Spanner)
- Hierarchical：volume_id → routing → chunk list 在某 metadata server 的 RocksDB
- **Lease-based caching on VM host**：60s lease，过期重新拉

> [!key] Lease 解决一致性：metadata 给 host 发 60s 独占权，过期前 host 本地缓存有效；过期必须重新拉。

### Deep Dive 3: Failure Detection + Rebuild

**检测**：heartbeat + client error report + 后台 scrubber (checksum)

**Rebuild 策略**：
- **优先级队列**：under-replicated (1/3) 最紧急
- **限流**：rebuild bandwidth ≤ 5%，不影响前台 IO
- **跨 failure domain**：新副本放到不同机架/AZ
- **并行 source**：从多个 replica 并行拉

**Math**：100 TB disk fail → 1000 chunks → 5% bandwidth = 500 MB/s → 20 分钟 rebuild。

> [!key] **Copyset placement**：3 副本不能随机放（多盘挂时丢数据概率高），限制到固定 9 个组合 → 概率降 10×。

### Deep Dive 4: Multi-tenant Isolation

**Noisy neighbor**：大批量 IO 的 VM 影响同 chunk server 上其他 VM。

**解法**：
1. **Token bucket per volume**：每 volume 有 IOPS quota
2. **Weighted Fair Queueing**：不同 volume 加权调度
3. **Tiered placement**：高 perf class → NVMe 机器；低 perf class → HDD
4. **Burst credits**：短期 over-quota 允许

### Deep Dive 5: Cross-AZ Trade-off

跨 AZ 延迟 1-2 ms vs 同 AZ 0.1 ms。

**EBS 选择**：
- 默认 3 副本都**在同 AZ**（low latency）
- AZ disaster recovery 通过 **snapshot 跨 AZ 异步复制**
- io2 Block Express 支持 multi-attach 跨 AZ，性能差

### Deep Dive 6: Erasure Coding for Cold Data

90% volumes 是冷数据：

- **(10+4) Reed-Solomon**：10 原 + 4 校验
- 任意丢 4 个可恢复
- 存储成本 **1.4×** (vs 3× replication)，省 53%

Trade-off：read/write 慢（要算 RS），适合 cold。**热冷分层**自动迁移。

### Deep Dive 7: Data Integrity

防 silent corruption (bit rot):
1. **End-to-end checksum**：write 算 SHA256，read 校验
2. **Scrubber**：周期 scan 所有 chunk，错的从 replica rebuild
3. **EC 校验位**自带 detection

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清需求 + NFR（强调 11 个 9） |
| 5-10min | 容量估算（150万台机器，200 TB metadata） |
| 10-15min | API design |
| 15-25min | 高层架构：control/data plane 分离 → chunks → 3 副本 → metadata → snapshot COW |
| 25-40min | Deep dives: journal-quorum / metadata / rebuild / copyset / multi-tenant |
| 40-45min | erasure coding / cross-AZ / monitoring |

---

## 7. 样板讲解稿

> 这道题考"真分布式存储"，跟 cache 不同的是 **durability 必须**，不是 best-effort。
>
> **需求**：CreateVolume / Read / Write / Snapshot / Restore。NFR：p99 写 1ms in-AZ，**durability 11 个 9**，scale 1B volumes / 100 EB。
>
> **关键 trade-off**：durability vs latency。同步 3 副本太慢，异步不够 durable。**用 journal-based quorum write**：journal 同步复制（小 IO），data block 后台 propagate。
>
> **架构**：
> 1. **Control / data plane 分离**：metadata 万级 QPS，IO 百万级
> 2. Volume → 1GB **chunks**，每 chunk 3 副本，spread cross failure domain
> 3. **Metadata**: 1T entries，sharded by volume_id，VM host lease cache
> 4. **Snapshot** = copy-on-write，瞬间完成
>
> **Deep dives**：
> 1. Journal write + quorum (2/3) + RDMA → p99 < 1ms
> 2. **Copyset placement** 减少多盘 fail 概率
> 3. Token bucket + WFQ 多租户隔离
> 4. (10+4) erasure coding for cold data，省 53%

---

## 8. Follow-up Q&A

### Q1: "为什么不默认 multi-AZ replication？"

**A**：跨 AZ 1-2ms vs 同 AZ 0.1ms，**block storage 当本地盘用，latency 是核心体验**。AZ disaster 通过 snapshot 异步复制兜底（RPO ~5min）。EBS gp3/io2 单 AZ 设计。

### Q2: "3 同时挂了存了同一 chunk 怎么办？"

**A**：**copyset problem**。随机放 → 多盘挂概率高。Copyset placement 限制到固定 9 组合，概率降 10×。Defense in depth：跨 failure domain、scrubber 早发现、scrubber + SMART data 预测盘 fail。

### Q3: "Snapshot COW，删 snapshot 怎么 GC？"

**A**：每 chunk 有 **reference count**。delete snapshot → ref--. 后台 GC scan ref=0 的 chunk 物理删。**Lazy GC** 避免删 spike。

### Q4: "p99 写 0.5ms 怎么做到？"

**A**：**Journal-only sync**：
1. Primary 本地 journal append (50μs)
2. RDMA sync journal to 1 replica (50μs)
3. 2/3 journal ack → ack client (~150μs)
4. Data block 异步 propagate

不等数据全部复制。journal 是 source of truth。

### Q5: "Volume 怎么动态扩容？"

**A**：**Thin provisioning**：metadata 直接改大小，新空间是 zero-filled chunks，**lazy-allocate**（实际写时才分配）。VM 看到 1TB 可用，actual usage 100GB。EBS / GCP PD 默认是 thin provisioning。

### Q6: "怎么测试？"

**A**：
1. **Correctness**: chunk checksum
2. **Performance**: `fio` 4k random RW
3. **Durability**: kill -9 多 chunk server
4. **Jepsen**: 注入网络分区验证 linearizability
5. **Long soak**: 30 天跑 fio，看 latency drift

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **跟 S3 / object storage 搞混**：S3 是整对象 PUT/GET，block storage 是 4KB 块
2. **没分 control/data plane**：所有 IO 经 metadata server → 瓶颈
3. **副本随机放**：没考虑 failure domain，多盘 fail 高概率
4. **同步 3 副本全 fan-out**：写延迟 = 最慢副本
5. **忘记 snapshot COW**：以为 snapshot 是 dump 全部数据
6. **Multi-AZ 当默认**：忽略 latency

### ✅ 加分项

1. **Journal-based quorum write** + RDMA
2. **Copyset placement**
3. **(10+4) erasure coding** for cold
4. **Lease-based metadata caching**
5. **Token bucket + WFQ** 隔离
6. **Reference count + lazy GC** for snapshot
7. **Scrubber + SMART** 早期 fail detect

> [!key] STAFF vs SENIOR：**journal + quorum + chain replication** 三种 trade-off 具体场景。

---

## 10. Cheat Sheet

```
架构:
  control / data plane 分离
  volume → 1GB chunks
  3 replicas, cross failure domain
  copyset placement

写路径:
  journal write + quorum (2/3) + RDMA
  p99 < 1ms via journal-only sync
  data block lazy propagate

Metadata:
  1T entries, sharded by volume_id
  lease-based caching on VM host
  Spanner / etcd

Snapshot:
  copy-on-write, immutable refs
  reference count + lazy GC

热冷分层:
  hot: 3x replication
  cold: (10+4) erasure coding, 1.4x cost

Failure:
  scrubber + heartbeat + SMART
  rate-limited rebuild (5% BW)
  cross failure domain

数字:
  11 个 9 durability
  1 ms p99 write
  16k-256k IOPS / volume
  1B volumes, 100 EB, 150万台
```
