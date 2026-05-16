## 题目本质

设计 **Data Migration Service for GCP**：把客户的 on-premise / 其他云的数据迁移到 GCP（BigQuery / GCS / Spanner 等）。PB 级数据，多种 source format。

## 需求

- 支持各种 source：SQL DB / NoSQL / S3 / HDFS / FTP
- TB-PB 规模
- 增量 + full migration
- 可验证（checksum / row count）
- 不影响 source 系统 SLA

## 整体架构

```ascii
   Source (on-prem DB / S3 / etc.)
        │
        │ pull
        ▼
   ┌──────────────┐
   │ Connector    │  source-specific reader
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Pipeline     │  → Dataflow / Spark
   │ (transform + │
   │  validate)   │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Sink         │  → BigQuery / GCS / Spanner
   └──────────────┘

   Control plane:
   ┌──────────────────────┐
   │  Migration Job DB    │  state, progress, errors
   │  Web UI + API        │
   └──────────────────────┘
```

## 核心组件

### 1. Source connectors (pluggable)

每 source 一个 connector：
- SQL DB：JDBC + offset pagination
- S3：list objects + parallel download
- HDFS：DistCp-like
- FTP / SFTP：streaming download

每 connector 实现统一 interface `read_chunk(checkpoint) -> (records, next_checkpoint)`。

### 2. 增量 migration

- SQL DB：based on updated_at timestamp 或 binlog (CDC)
- NoSQL：change stream API
- Object store：list by modification time + new-files-only

第一次 full sync，之后增量。

### 3. Pipeline (Dataflow)

并行 ingest 多个 source partition。Transform：
- Schema mapping (source schema → target schema)
- Type conversion
- PII redaction
- Validation rules

### 4. Sink

- BigQuery：streaming insert API or batch load via GCS
- GCS：multipart upload
- Spanner：DML batched

### 5. Checkpoint + resume

每 chunk 完成后写 checkpoint to migration job DB。Job crash recovery from last checkpoint。

### 6. Verification

- Row count match
- Checksum (HASH(rows)) per chunk
- Spot check：抽样 100 row deep compare

### 7. Throttling

不能把 source DB 打挂。Connector 自己 rate limit + monitor source CPU 自适应。

### 8. Multi-tenant control plane

- 每客户每 source 一个 job
- Job state: pending / running / paused / completed / failed
- Web UI 显示 progress
- 可配置 schedule（每天增量 sync）

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Pipeline | Dataflow (Apache Beam) | Spark：less GCP integrated |
| Increment | CDC where available | Full re-sync：浪费 |
| Validation | Checksum + sample | Full deep compare：太慢 |
| Throttle | Adaptive based on source CPU | Fixed：source overload |

## 易错点

> [!pitfall]
> ❌ 不 checkpoint → crash 重头开始；
> ❌ 不 throttle source → 把客户 prod DB 打挂；
> ❌ Schema mismatch silently → 数据破坏；
> ❌ 不验证 → 客户不放心 cutover；
> ❌ Full sync 太频繁 → 网络成本爆。

> [!key]
> Data migration 的三个柱子：(1) **incremental + CDC** 减传量；(2) **checkpoint + resume** robust；(3) **verification + dry run** 让客户 trust。

> [!followup]
> "如何 schema evolve mid-migration？" → 版本化 schema map + pause / restart；"客户要 zero-downtime cutover？" → dual-write + lag monitor + switchover；"PII compliance？" → field-level encryption + redaction rules；"成本？" → 算 ingress + egress + compute；选 region 近 source。
