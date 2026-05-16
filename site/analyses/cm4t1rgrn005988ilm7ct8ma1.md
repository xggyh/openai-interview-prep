## 题目本质

设计 **Image Uploader**：用户上传图片到云端，服务端处理（resize / format / CDN distribute），返回 URL。亿级用户，TB 级 image。

## 需求

- 上传：mobile + web，最大 50 MB / image
- 处理：生成多种尺寸（thumb / medium / large / original）
- 存储 + CDN 分发
- 上传可恢复（resumable）+ 进度反馈

## 架构

```ascii
   Client
     │ POST /upload/init  → presigned S3 URL
     │ PUT chunk to S3 directly (multipart)
     │ POST /upload/complete
     ▼
   ┌──────────────┐
   │ Upload API   │  → metadata in DB
   └──────┬───────┘
          │ enqueue
          ▼
   ┌──────────────┐
   │ Image Worker │  ← Lambda / K8s job
   │ pool         │     - thumb / med / large
   └──────┬───────┘     - format conversion (webp)
          │             - metadata extract (EXIF)
          ▼
   ┌──────────────┐
   │ S3 (variants)│
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ CDN          │  CloudFront / Cloudflare
   └──────────────┘
```

## 核心机制

### 1. Direct-to-S3 multipart upload

```
1. POST /upload/init → server creates multipart upload + presigns N URLs
2. Client PUTs each chunk (5MB) parallel to S3 directly
3. POST /upload/complete → server calls S3 CompleteMultipartUpload
```

**关键**：client → S3 directly。Backend server 不接流量 → 可以 scale 上传带宽。

### 2. Resumable + progress

Multipart 天然 resumable：失败 chunk 重传，已成功 chunk 不必重。

Progress：client 本地累积 bytes uploaded / total。或 server-side WebSocket。

### 3. Image processing pipeline

```
S3 upload complete → S3 Event → Lambda / Kafka → Worker
Worker:
  1. Download original
  2. Generate 3 sizes (e.g., 128x128, 512x512, 1024x1024)
  3. Convert to WebP for smaller size
  4. Extract EXIF metadata
  5. Optional: ML moderation (NSFW detection)
  6. Upload variants to S3
  7. Update DB record with variant URLs
```

### 4. URL design

```
https://cdn.example.com/{user_id}/{image_id}/{size}.{format}
e.g. .../abc123/def456/medium.webp
```

按 user_id 分目录便于 bucket lifecycle。CDN cache 长 TTL（image immutable）。

### 5. Database schema

```sql
CREATE TABLE images (
  id              UUID PRIMARY KEY,
  user_id         UUID,
  original_url    TEXT,
  variants        JSONB,           -- {thumb: url, medium: url, ...}
  status          TEXT,            -- 'uploading'/'processing'/'ready'/'failed'
  exif            JSONB,
  uploaded_at     TIMESTAMPTZ,
  bytes           BIGINT,
  moderation      TEXT             -- 'pending'/'ok'/'flagged'
);
```

### 6. Moderation

ML model (NSFW / illegal content)：上传完成后 async run。可疑的 manual review。Flag 后 image 不返回 CDN URL。

### 7. Deduplication（可选）

计算 image hash (perceptual hash)。如果用户上传重复 image，直接 link 已有 record 而非重新存储。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Upload path | Client → S3 direct | 走 backend：带宽爆 |
| Processing | Async after upload | Sync：上传慢 |
| Format | 多 variant (thumb/med/large/orig) | 单一：客户端浪费 |
| Format change | WebP optional + JPEG fallback | All WebP：老设备 |
| Storage | S3 + CDN | DB blob：贵 |

## 易错点

> [!pitfall]
> ❌ Upload 走 backend —— scale 不上去；
> ❌ 不做 multipart —— 50 MB 一次性 fail 全重；
> ❌ Sync processing —— 用户等 30 秒；
> ❌ Variant URL hardcoded —— 加新 size 时 schema break；用 JSONB；
> ❌ 不做 moderation —— legal 风险。

> [!key]
> 三大要点：(1) **Client 直传 S3 + presigned URL** 把流量从 backend 摘开；(2) **Async pipeline + S3 events** 解耦上传 / 处理；(3) **多 variant + CDN** 优化 client 加载。

> [!followup]
> "如何 detect duplicate？" → perceptual hash + lookup table；"如何处理 batch upload 几百张？" → client SDK 并发 + queue；"AR / 3D model upload？" → 同 pipeline 但 variants 不同；"端到端 encryption？" → client-side encrypt 后上传，server 只见密文。
