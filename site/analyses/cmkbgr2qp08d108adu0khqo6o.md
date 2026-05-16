## 题目本质

设计 **Google Photos**：用户上传相册，云端 store + organize（按时间 / 人脸 / 地点 / 物体），搜索 ("show me beach photos from 2024")，分享 + sync。

## 需求

- 1B+ users, 10B+ photos
- Upload: < 5 sec for 5 MB photo
- Search: < 1 sec
- ML feature: face recognition, object tag, location grouping

## 整体架构

```ascii
   Mobile / Web client
       │ upload (chunked)
       ▼
  ┌──────────────┐
  │ Upload API   │  → presigned URL → S3-like blob store
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐    ┌──────────────────┐
  │ Photo        │ ── │ ML Pipeline      │
  │ Metadata     │    │ - face embed     │
  │ Service      │    │ - object detect  │
  └──────┬───────┘    │ - OCR / scene    │
         │            └──────────────────┘
         │
         ▼
  ┌──────────────┐    ┌──────────────────┐
  │ Search Index │    │ Embedding Index  │
  │ (ES / Vespa) │    │ (Faiss / ScaNN)  │
  └──────────────┘    └──────────────────┘
```

## 核心组件

### 1. Upload pipeline

参考 [[cm4t1rgrn005988ilm7ct8ma1]] (Image Uploader)。Direct-to-blob multipart upload。

### 2. Photo metadata schema

```sql
CREATE TABLE photos (
  id            UUID PRIMARY KEY,
  user_id       UUID,
  blob_url      TEXT,
  taken_at      TIMESTAMPTZ,         -- from EXIF
  location      GEOGRAPHY,           -- GPS
  device        TEXT,
  variants      JSONB,
  tags          TEXT[],              -- ML inferred
  faces         TEXT[],              -- face cluster IDs
  is_archived   BOOLEAN,
  ...
);
```

### 3. ML pipeline

异步 worker pool 处理每张 uploaded photo：
- **Face detection + embedding**：CNN detect face → 128-dim embedding → cluster (DBSCAN) with other user photos
- **Object / scene tagging**：image classifier → ['beach', 'sunset', 'dog']
- **OCR**：detect text in photos
- **Location**：from EXIF GPS or photo-based geo guess

Tags + embeddings 写入 search index。

### 4. Face clustering

Per-user face clusters。新照片 face embed 后：
- Compare with user's existing face clusters (cosine sim > threshold)
- 命中：assign to cluster
- Miss：create new cluster

UI 让用户给 cluster 命名（"Mom"）→ 之后 search by name。

### 5. 搜索

Query: "beach sunset"
1. 文本 query 走 ES match tags + OCR text
2. Optional: text-to-image embedding (CLIP) → find similar photo embeddings
3. Fuse + rerank by recency / user preference

For natural language: "photos of mom at the beach last summer":
- Entity extract: mom (face cluster), beach (tag), last summer (time filter)
- Compose ES query

### 6. Album / sharing

- Auto-album：grouped by event/trip (location + time clustering)
- Manual album：user create + add photos
- Share：generate URL with token，可加权限（view / edit）

### 7. Sync + offline

Mobile app 本地 cache 缩略图 (~5 MB per 100 photos)。Full photo on-demand。
Offline 拍的照片 queue + 等 wifi upload。

### 8. Storage tiering

- Hot (last 90 days): SSD blob
- Warm: HDD
- Cold (1 year+): object archive (S3 Glacier)

User access cold photo → 触发 rehydrate (几秒延迟)。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Upload | Direct-to-blob | Backend：流量爆 |
| ML | Async worker | Sync：upload 慢 |
| Search | ES tag + embedding | Pure ES：missing semantic |
| Face cluster | Per-user | Global：privacy risk |
| Storage tier | 3 layer | Single：cost or speed 不平衡 |

## 易错点

> [!pitfall]
> ❌ Face cluster 跨 user → 严重 privacy；
> ❌ ML pipeline 不 retry → 偶尔 photo missing tags；
> ❌ Embeddings 不版本化 → 模型 update 后老 embed 不兼容；
> ❌ Cold tier rehydrate 不通知 → 用户等几秒以为 broken；
> ❌ Sharing token 不限制 expire → 永久暴露。

> [!key]
> 三大要点：(1) **Direct-to-blob upload + async ML pipeline**；(2) **Multi-modal search (tag + embedding + entity)**；(3) **Per-user face cluster + privacy isolation**。

> [!followup]
> "如何 detect duplicate photos？" → perceptual hash + similar embedding；"Edit history 保留？" → 每 edit 新 version + chain；"如何节省 cellular 流量？" → 上传只 wifi default；"Family sharing 多人 album？" → group + 权限 model。
