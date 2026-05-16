## 题目本质

设计 **ANN Index System**：Approximate Nearest Neighbor search 系统。给 query vector 找 top-K nearest from 100M-10B 向量。向量搜索引擎核心组件。

参考 [[cmikmkva406q908adb5780xku]] (photo search) 提到 ANN 概念。这里 deep dive ANN 系统本身。

## 需求

- 1B+ vectors，每 768-3072 dim
- Query latency P99 < 100ms
- Recall >= 95% (vs exact)
- Online ingest (新 vector 实时加入)
- Filter (metadata)

## 整体架构

```ascii
   Vectors + metadata
       │ ingest
       ▼
  ┌──────────────┐
  │ Indexer      │  build / update index
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Vector Index │  Sharded HNSW / IVF / ScaNN
  │ (sharded)    │
  └──────┬───────┘
         │
   Query gateway routes
         │
         ▼
  ┌──────────────────┐
  │ Search Nodes     │  query each shard，merge top-K
  └──────────────────┘
```

## 核心算法

### HNSW (Hierarchical Navigable Small World)

Graph-based。Build：每个 vector add 时连接 M nearest neighbors at each layer。Query：从顶层 entry point 贪心走，下沉到底层。

- 优势：state-of-art recall / latency trade-off
- 缺点：内存大（~1.5x vector size for graph）

### IVF (Inverted File)

K-means cluster vectors → 每 query 只搜 nearest clusters。
- 优势：低内存，scale 到亿级
- 缺点：edge of cluster recall 差

### IVF-PQ (Product Quantization)

IVF + 把 vector compress 到 256 bits (PQ codes)。

- 优势：能 1B vectors fit 在 100GB RAM
- 缺点：精度损失

### ScaNN (Google)

IVF-PQ + anisotropic quantization (优化 high-relevance vector 精度)。

## 系统设计

### 1. Sharding

1B vectors / shard 100M = 10 shards。Sharding by:
- **Random hash**：均衡，但每 query 都要 fan-out 所有 shard
- **Cluster-based**：相近 vector 同 shard，query 只去几个 shard。复杂但 fan-out 少。

### 2. Replication

每 shard 3 replicas。Read 任一 replica，write 同步所有。

### 3. Indexing pipeline

新 vector 到来：
- Direct insert into HNSW（graph build incrementally）
- OR：append to "delta" 索引（flat list），定期 merge into main HNSW (减少 build cost)

### 4. Filter

混合搜索（vector + metadata）：

**Pre-filter**：先按 metadata 缩 candidate (`WHERE category=X`)，再 brute force / ANN candidate set。
- 适合 selective filter (small candidate)

**Post-filter**：ANN top-K' (K' > K) → filter → return top-K
- 适合 broad filter

Hybrid：判断 filter selectivity 选 strategy。

### 5. 多向量（multi-vector）

某些 query 有多 vector（e.g. ColBERT late interaction）。Search by max sim across query vectors。Index支持 multi-vector entity（per-entity 多个 vector）。

### 6. 版本化

Embedding model 升级 → 老 vector incompatible。Index 支持 multi-version：v1 主，v2 后台 backfill，cutover 后 deprecate v1。

### 7. 监控

- Recall@K：周期 sample queries with ground truth 验证
- Latency P50/P99
- QPS / shard utilization

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Algorithm | HNSW for accuracy, IVF-PQ for scale | exact KNN：O(N) |
| Shard | Cluster-based for low fanout | Random：always fanout |
| Filter | Hybrid pre/post | One only：suboptimal |
| Storage | RAM | Disk：latency 高 |

## 容量估算

- 1B × 768 dim × 4 bytes (fp32) = 3 TB raw
- HNSW graph ~50% overhead → 4.5 TB total → distribute 50 nodes × 100GB RAM each
- 1k QPS / shard / replica → 30 shards × 3 replica = 90 nodes total

## 易错点

> [!pitfall]
> ❌ Brute force search for 1B → 不可能 fit latency；
> ❌ Pre-filter for broad filter → 缓存破坏 ANN locality；
> ❌ 不 normalize vector → cosine sim 错；
> ❌ 不 monitor recall → silent quality degrade；
> ❌ Index 不版本化 → model upgrade 时灾难。

> [!key]
> 三大要点：(1) **HNSW for accuracy** / **IVF-PQ for scale**；(2) **Hybrid pre/post filter**；(3) **Sharding + replication for QPS**。Vector DB 是新 hot DB category（Pinecone, Weaviate, Milvus）。

> [!followup]
> "如何 delete vector？" → HNSW 不易，标记 deleted + periodic rebuild；"GPU 加速？" → GPU-friendly index (FAISS-GPU)；"Hybrid sparse + dense search？" → BM25 + dense vector → rerank。
