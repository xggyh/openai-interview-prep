## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Image embedding** | 图片 → 高维向量 (e.g., 512 维) | 图片的"指纹" |
| **CNN (ResNet/EfficientNet)** | 卷积神经网络，从像素学 visual feature | 视觉系统 |
| **CLIP** | OpenAI 模型，把 image 和 text embed 到同一空间 | 让"狗"文本和"狗"图片向量接近 |
| **ANN (Approximate Nearest Neighbor)** | 近似最近邻搜索，亿级向量秒级查 | "找最像的"快速查 |
| **FAISS / Milvus / Pinecone** | 业界主流 vector DB | 向量数据库品牌 |
| **HNSW** | Hierarchical Navigable Small World，最常用 ANN 算法 | 图结构搜索 |
| **Reverse image search** | 上传图找类似图 | Google 图片识图 |
| **Text-to-image search** | 文字描述找图 | "夕阳海边" → 找到相关图 |
| **OCR** | 图中提取文字 | 看图认字 |
| **Object detection** | 检测图中物体并 bounding box | 找出"猫在哪格" |
| **Semantic search** | 按"含义"搜，非关键词 | 搜"快乐" 找到笑脸 |
| **Multi-modal** | 跨模态 (text + image) 检索 | "用文字找图 / 用图找文字" |
| **Quantization (PQ)** | Product Quantization，向量压缩节省内存 | 把高清画变低分辨率指纹 |

---

## 1. 题目本质

**Photo Search Application** = 用户上传 photo 或输入 text → 搜索匹配的 photos。

**典型产品**：
- **Google Photos** —— 个人相册，"找海边照片"
- **Google Images** —— web 反向图搜索
- **Pinterest visual search** —— "更多类似的"
- **Apple Photos** —— device-local + iCloud 索引
- **Bing visual search** / **Yandex** —— web image
- **eBay / Amazon visual product search**

**为什么这是 STAFF 题**：

考的是**ML system + vector search at scale**：

1. **Image embedding pipeline**：用什么模型？ResNet vs CLIP？
2. **Vector index at billion scale**：HNSW vs IVF？memory budget？
3. **Multi-modal search**：text + image 同一索引怎么搞
4. **Personal vs global**：个人相册 vs 全网索引模型不同
5. **Real-time vs offline indexing**

考 STAFF 关键：**你懂 embedding pipeline + ANN index + multi-modal**，不只是 elasticsearch on metadata。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `SearchByImage(image) -> similar_images[]` | 反向图搜 |
| `SearchByText(query) -> images[]` | 文字搜图 |
| `UploadImage(image, metadata) -> image_id` | 索引新图 |
| `GetSimilar(image_id) -> similar[]` | "更多类似" |
| `FilterByObject(query="dog")` | 物体过滤 |
| `OCRSearch("invoice 2024")` | 图中文字搜 |

**澄清要点**：
- Scope：personal album（10k photos）还是 web global（10B photos）？
- 是否需要 OCR / object detection？
- Image vs video?
- Privacy: device-local vs cloud?

### Non-functional

| 维度 | 目标 |
|---|---|
| **查询 latency** | p99 < 500 ms |
| **Scale** | 10B images (web) or 10k-1M per user (personal) |
| **Index latency** | new upload searchable in 5 min |
| **Recall@10** | > 90% (top 10 中有 90% 真正相关) |
| **Storage** | image bytes + embeddings + index |

---

## 3. 容量估算

### Personal Album (Google Photos)

- 1B users × 5k photos avg = **5T total images**
- 5 KB / image embedding (512 floats × 4 B + index overhead) = **25 TB embeddings**
- Image bytes: 1 MB avg × 5T = **5 PB**
- Index growth: 1B × 5 photos/day = **5 GB embeddings/day**

### Web Global (Google Images)

- **10B images** indexed
- Embedding storage: 10B × 2 KB compressed = **20 TB**
- Image thumbnails: 10B × 10 KB = **100 TB**

---

## 4. 高层架构

### Step 1: Indexing pipeline

```
Image source (upload / crawler)
   ↓
Image queue (Kafka)
   ↓
Feature extraction worker
   ├── Embedding model (CLIP)
   ├── Object detection (YOLO)
   ├── OCR (Tesseract / Vision API)
   └── Metadata extraction (EXIF: GPS, date, camera)
   ↓
Vector DB (FAISS / Milvus) + Metadata DB (Spanner/DynamoDB)
   ↓
Searchable
```

### Step 2: Query pipeline (text-to-image)

```
Text query → CLIP text encoder → text_vec [512]
                                       ↓
                              ANN search in vector DB
                                       ↓
                              top-1000 candidates
                                       ↓
                              re-rank (DNN with more features)
                                       ↓
                              top-100 results
```

### Step 3: Query pipeline (image-to-image)

```
Image upload → CLIP/ResNet vision encoder → image_vec [512]
                                                  ↓
                                          ANN search → ranked results
```

### Step 4: Storage

```
Vector DB: FAISS IVF-PQ index, sharded by image_id
Metadata: Spanner (image_id, owner, upload_time, GPS, objects, OCR text)
Image bytes: S3 (cold), CDN edge (hot)
```

### Step 5: Personal vs Global separation

- **Personal album**: per-user FAISS index (在 device 或 per-user server)
- **Global web search**: shared FAISS cluster with sharding by image_id

Personal 用户查询时只搜自己的 index → privacy + 准确度。

---

## 5. 组件深挖

### Deep Dive 1: Embedding Model — CLIP vs ResNet

**ResNet 系列 (pre-2021)**:
- ImageNet 训练，1000 类别
- 拿 last conv layer 当 embedding (2048 dim)
- 强 visual feature，弱 semantic

**CLIP (2021+)**:
- Train on 400M image-text pairs
- Image 和 text 同一 vector 空间
- 512 dim
- Zero-shot：任意 text 都能查 image

**STAFF 答**：default 用 CLIP，强 multi-modal。如果只做 visual similarity 用 ResNet/EfficientNet 更便宜（更小模型）。

**Inference cost**:
- CLIP ViT-B/32: ~50ms / image on GPU
- 1M images/day → 1 GPU 处理够，10B all-history → batch 处理几周

### Deep Dive 2: ANN Index — HNSW vs IVF-PQ

| 算法 | 内存 | 速度 | Recall |
|---|---|---|---|
| **HNSW** | 高 (~4× raw) | 极快 | 95-99% |
| **IVF (FAISS)** | 中 | 快 | 90-95% |
| **IVF-PQ** | 低 (16× compress) | 中 | 85-90% |
| **DiskANN / SPANN** | 极低 (用 SSD) | 中 | 90% |

**10B images full embedding**: 10B × 512 × 4 = **20 TB**。HNSW 4× = 80 TB → 几十台机器内存。

**PQ 压缩**: 10B × 32 B (PQ-compressed) = **320 GB** → 5 台机器 RAM。Recall ~90%。

**STAFF 答**: IVF-PQ for global scale (cost), HNSW for hot tier / per-user index (small).

### Deep Dive 3: Indexing Sharding

10B vectors / 1B per shard → 10 shards.

**Sharding by what**:
- Random shard ID → 查询时 scatter-gather 到全部 10 shard
- Locality shard (e.g., by region) → 减少 inter-region 流量

**Query**:
- Send to all shards (scatter)
- Each returns top-K
- Merge top-K of top-K → final top-K
- Latency = max(shard latency) + merge

### Deep Dive 4: Cold Start for New Image

New upload → searchable in 5 min:

1. Image stored → trigger embedding worker (Kafka)
2. CLIP infer 50ms on GPU
3. Insert to ANN index → "add new vector" 通常 < 10ms
4. **Index rebuild**: HNSW 支持 incremental add；IVF 需要定期 retrain

**Streaming index update**:
- Append to "delta" index (small, incremental)
- 定期 merge delta into main index
- Query searches both, merge results

### Deep Dive 5: OCR + Object Detection

Many photos 有可读文字 (receipt, screenshot, sign):

- **OCR**: Tesseract / Google Vision API → text
- Text 进 Elasticsearch (separate index)
- Query: "invoice 2024" → text search by OCR + image search by embedding union

**Object detection** (YOLO / DETR):
- 每图 detect 物体 → "dog, cat, person, car"
- Object tags 写入 metadata DB
- "show me dog photos" → filter by tag

### Deep Dive 6: Personalization

**Personal album**:
- Per-user FAISS index (small, ~5k photos)
- Filters: by face (face recognition cluster) / by GPS / by date

**Face clustering**:
- FaceNet embedding per detected face
- DBSCAN cluster faces in user's library
- User labels cluster name "Alice"
- "Alice 2023 birthday" → filter by face + date

### Deep Dive 7: Privacy

**Personal photos**:
- E2EE option: user's images encrypted with user key
- Embeddings 在 device 上 compute (Apple Photos 这么做)
- Index on device for privacy
- Cloud sync 加密图片，不传 raw

**vs Web global search**:
- Crawler 只索引 public images
- Honors `robots-noimageindex`
- Right-to-be-forgotten (GDPR)：删除原图 + 索引 + cache

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：personal vs web global? text+image? OCR? |
| 5-10min | 容量：10B images, 20 TB embeddings, 5 PB images |
| 10-20min | 高层架构：indexing pipeline + query pipeline |
| 20-35min | Deep dives: CLIP / IVF-PQ / sharding / OCR / face |
| 35-45min | privacy / cold start / personalization |

---

## 7. 样板讲解稿

> Photo search 关键是 **embedding + vector search**：图 → CLIP embed → ANN index → 查询。
>
> **架构**：
> 1. **Indexing pipeline**: Kafka → CLIP worker → write FAISS index + metadata DB
> 2. **Query pipeline**:
>    - Text query: CLIP text encoder → ANN search → re-rank → top results
>    - Image query: CLIP image encoder → 同上
> 3. **Vector DB**: IVF-PQ for cost (10B vectors → 320 GB compressed)，HNSW for hot/personal tier
> 4. **Additional**: OCR for text-in-image, object detection for tags
>
> **Personal vs Web** 两套独立 index:
> - Personal: per-user FAISS, 在 device 或 per-user server
> - Web: 10B 共享 sharded
>
> **Trade-offs**:
> - CLIP > ResNet for multi-modal (text+image 同空间)
> - IVF-PQ vs HNSW: cost vs recall
> - Index sharding: scatter-gather query
> - Real-time index: delta index + periodic merge
>
> Numbers: 10B images, 20 TB compressed embeddings, p99 < 500 ms.

---

## 8. Follow-up Q&A

### Q1: "10B images，怎么扛 ANN search 的内存？"

**A**：**Product Quantization (PQ)**：512 维 float = 2KB → 32B (16x compress)，recall 90%。10B × 32B = 320 GB → 单 cluster (5 台 64GB 机器) 装下。

进阶：**SPANN / DiskANN** 把大部分 vector 放 SSD，只 hot 部分在 RAM，1B image 单 machine 都行。

### Q2: "Text query 跟 image 怎么映射到同一向量空间？"

**A**：**CLIP** training 把 image 和 text 同时 embed 到 512 维：通过 contrastive loss 让"狗"文本和"狗"图片 cosine 接近。Query text → CLIP text encoder → 跟 image embeddings 算 cosine 找最近。

### Q3: "user 上传新图，几秒后可搜，怎么实现？"

**A**：
1. Image → S3 → Kafka event
2. Worker pull → CLIP infer (50ms on GPU)
3. Embed insert to **delta FAISS index** (separate small index, fast write)
4. Query: search delta + main index, merge
5. Background: 每 6h merge delta → main

End-to-end 5 sec - 1 min。

### Q4: "Recall 90% 不够准，怎么提升？"

**A**：
1. Two-stage: ANN 先取 top-1000，**DNN re-rank top-100** with more features
2. Multiple embeddings: 用 CLIP + ResNet + 自己 fine-tuned 模型，late fusion
3. User feedback loop: click data 训练 re-ranker
4. HNSW (高 recall) for top tier，IVF-PQ for cold tail

### Q5: "10B images 怎么 batch index 一遍？"

**A**：
- 1 GPU 跑 CLIP，每张图 50ms → **20 images/sec**
- 1000 GPU 并行 → 20k images/sec → 10B / 20k = 50万秒 = ~6 天
- 实际：分布式 dataflow (Spark + GPU executors)，6-10 天 batch index 完成

### Q6: "如果用户删除图片，怎么从 index 删除？"

**A**：
- HNSW 不支持 efficient delete (graph 结构) → mark tombstone, query 时 filter
- IVF：rebuild inverted list 时跳过 tombstone
- 定期 (每周) full rebuild 整理 tombstones

GDPR 要求：tombstone + scheduled physical delete within 30 days.

### Q7: "Multi-modal: text query 'sunset by beach with two people' 怎么处理？"

**A**：
- CLIP encode full sentence → 512 vec
- ANN search 直接出结果
- 如果需要更精确：**compositional retrieval**：
  - 切片 "sunset", "beach", "two people"
  - 每段 CLIP encode
  - 查多 vec 取交集 (re-rank by all match)

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **Elasticsearch on metadata only** → semantic search 不 work
2. **不知道 vector DB** → 答案在错误的轨道
3. **CLIP 当唯一方案** → 不知道 ResNet 在 visual-only 任务更便宜
4. **Full embedding storage** → 10B × 2KB = 20TB 太贵
5. **Sync indexing** → upload 慢
6. **不分 personal / global** → architecture confused

### ✅ 加分项

1. **CLIP** for multi-modal
2. **IVF-PQ** for cost (10× memory save)
3. **HNSW** for hot tier
4. **Delta + main index** for real-time
5. **Two-stage retrieve + rerank**
6. **Face clustering** for personal album
7. **OCR + object detection** for keyword search
8. **DiskANN / SPANN** 前沿

> [!key] STAFF vs SENIOR：能讲 CLIP + IVF-PQ + delta indexing + two-stage rerank 是 STAFF；只说 "vector DB" 是 SENIOR。

---

## 10. Cheat Sheet

```
Pipeline:
  Image → CLIP/ResNet → embedding → FAISS index
  Text  → CLIP text encoder → query vector

Vector DB:
  Personal (10k): HNSW (high recall, in-memory)
  Web (10B): IVF-PQ (compressed, scattered shards)
  Future: DiskANN / SPANN (SSD-based)

Storage:
  Raw images: S3 (5 PB for 5T images)
  Embeddings: 20 TB compressed
  Metadata + OCR text: Spanner / ES
  Index: FAISS cluster

Additional features:
  OCR: Tesseract / Vision API → ES
  Object detect: YOLO/DETR → metadata tags
  Face: FaceNet + DBSCAN cluster

Query path:
  Text/Image → encode → ANN top-1000
            → DNN rerank top-100
            → filter (object tag / face / date / GPS)

Real-time:
  Delta FAISS index for new uploads
  Periodic merge into main

数字:
  10B web images / 1B users × 5k personal photos
  20 TB compressed embeddings
  p99 < 500 ms
  Recall@10 > 90%
  Cold start: 5 min searchable
```
