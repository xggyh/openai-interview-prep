## 题目本质

设计 **Photo Search Application**：用户上传 photo / type text → 搜索类似 photo。Pinterest 反向搜索 / Google Images / 个人 photo library。

## 解法

**向量索引 (ANN)** 是核心。每 photo embed 为高维 vector，搜索 = nearest neighbor lookup。

## 整体架构

```ascii
   Photo upload                Text query
       │                            │
       ▼                            ▼
  ┌──────────────┐         ┌──────────────┐
  │ Image        │         │ Text → Image │  CLIP
  │ Encoder      │         │ Encoder      │
  │ (CLIP / DINO)│         └──────┬───────┘
  └──────┬───────┘                │
         │                        │
         ▼                        ▼
       Embedding (768-dim)     Same space
         │                        │
         └──────┬─────────────────┘
                ▼
         ┌──────────────┐
         │ Vector Index │  Faiss / ScaNN / Vespa
         │ (ANN search) │  100M+ embeddings
         └──────┬───────┘
                │
                ▼
         Top-K photo IDs → metadata → return URLs
```

## 核心组件

### 1. Image encoder

CLIP ViT-L 或 DINOv2。每 photo → 768-dim normalized vector。

### 2. Vector index

100M+ vectors 不能 brute force search (cosine sim O(N))。**ANN (Approximate Nearest Neighbor)**:
- **Faiss IVF**：clusters + only search nearest clusters → O(√N)
- **HNSW**：graph-based，state-of-art
- **ScaNN**：Google 自家，accuracy 优

Trade-off：recall vs latency vs memory。

### 3. 文本到图片搜索 (CLIP)

CLIP 把 text 和 image embed 到同一空间。User type "red dog on beach" → text embed → 搜 image embedding。完全无需 image tags。

### 4. 反向图片搜索 (image-to-image)

User upload photo → image embed → ANN search。同框架。

### 5. Filter

ANN search + metadata filter（"jpegs only from 2024"）。两种方式：
- Pre-filter：先按 metadata 缩 candidate，再 ANN（candidate 少时快）
- Post-filter：ANN top-K 后 metadata filter（candidate 多时快）

Hybrid：metadata distribution decide。

### 6. Sharding

100M vectors / 256d × 4 bytes = 100 GB。Split 跨多 nodes：
- 按 vector hash 分 shard
- Query 每 shard 都查 → merge top-K

### 7. Indexing pipeline

新 photo upload → ML pipeline 算 embedding → write to vector index。

ANN index 通常需要 batch rebuild（少量新增 OK，大量需要 reindex）。Hot 写入用 flat list，每天 incremental merge into ANN graph。

### 8. Caching

热门 query embeddings cache。同一 query 短时间内重复时返回 cached result。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Embedding | CLIP / DINO | Custom CNN：训练贵 |
| ANN | HNSW / Faiss IVF | Brute force：O(N) |
| Search type | Vector + filter | Pure text tag：semantic 弱 |
| Index | Static + incremental | Real-time：复杂 |

## 容量估算

- 100M photos × 768 × 4 bytes = 300 GB embedding
- Query QPS: 100k → ANN search ~5 ms each on optimized index
- Encoding cost: GPU 100 photo/sec per A100

## 易错点

> [!pitfall]
> ❌ Brute force search → TLE；
> ❌ Index 不 normalize vectors → cosine sim 不对（应 L2 normalize 后用 dot product）；
> ❌ 文本搜索单 keyword match → 错过 semantic；用 CLIP；
> ❌ 不 filter spam / NSFW → 搜出违法内容；
> ❌ 不版本化 embedding model → 切模型时无法 reindex。

> [!key]
> 三大要点：(1) **CLIP-style embedding** 让 text & image 同空间；(2) **HNSW / Faiss ANN** scale to 100M+；(3) **Hybrid metadata filter** for precision。

> [!followup]
> "视频搜索？" → 提关键帧 embed + 查；"特定物体 search？" → object detection + crop + embed；"face search？" → 专用 face model + per-user cluster (privacy)；"How handle adversarial images？" → robustness training + filter。
