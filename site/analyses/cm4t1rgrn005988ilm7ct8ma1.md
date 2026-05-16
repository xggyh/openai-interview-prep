## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Blob storage / S3** | 存大文件（图片 / 视频）的云服务，按对象 key 访问 | 自助仓储 |
| **Multipart upload** | 把大文件切成小块分别上传，最后合并 | 大象切块装冰箱 |
| **Presigned URL** | 时效性 token + URL，让 client **直接上传到 S3** 而无需走 backend | 一次性入场券 |
| **CDN** | 把文件缓存到全球边缘节点，用户从最近的取 | 全球连锁加盟店 |
| **EXIF** | 照片元数据（拍摄时间 / GPS / 相机型号），相机自动写入 | 照片"出生证" |
| **WebP / AVIF** | 比 JPEG 更高效的现代图片格式（小 30-50%） | 同样照片用更小盒装 |
| **Thumbnail / Variant** | 缩略图 / 不同尺寸版本（128/512/1024px） | 一张照片印成不同大小 |
| **Worker / Lambda** | 异步执行任务的服务（vs 同步 API） | 后厨而不是前台 |
| **Idempotency** | 同一操作做 N 次结果跟 1 次一样 | 按 N 次按钮 = 1 次电梯 |
| **NSFW** | Not Safe For Work，违规 / 成人 / 暴力内容 | 不雅照片 |
| **Perceptual hash** | 基于图片内容算"视觉指纹"，类似图片 hash 相近 | 油画上的签名 |
| **DRM** | Digital Rights Management，防盗 / 防截图 | 电影院的"禁止录像" |

---

## 1. 题目本质 — 这是什么问题

**Image Uploader** = 让用户从 mobile / web 把图片传到云端 → 服务端处理（多分辨率 / 压缩 / 安全检测）→ 返回 URL 供后续展示。

**典型产品**：
- Instagram / 微信朋友圈 上传
- Google Photos / iCloud 备份
- Slack / WhatsApp 发图片
- 电商 (Amazon / 淘宝) 商品图

**为什么这道题考的多**：

它表面简单（"上传 + 存储 + 返回 URL"），但里面有很多**隐藏复杂度**：

1. **图片大** (5-50 MB)，简单 POST 上传弱网时失败率高
2. **流量集中**（亿用户每天传 10 亿张）→ backend 不能扛流量
3. **后处理重**（生成多分辨率 / 格式转换 / EXIF 提取 / 违规检测）必须 async
4. **存储贵**（PB 级 + 99.999% durability）
5. **客户端需求多样**（thumbnail / 1080p / 原图），不能每次都 download 原图

Google 报告 4 人，是经典 SD 入门题。考点：**Direct-to-S3 upload + async processing pipeline + multi-variant + CDN**。

---

## 2. 需求拆解 — 面试第一步问什么

### 2.1 功能性

**你问**：上传后需要哪些变体（thumbnail, 全屏, 原图）？  
**典型答**：3-4 个 size：thumb (128px), medium (512px), large (1024px), original。

**你问**：支持什么格式上传？  
**典型答**：JPEG / PNG / HEIC (iPhone) / WebP / GIF。

**你问**：上传中断后能恢复吗？  
**典型答**：要。Resumable upload。

**你问**：要不要做内容审核（NSFW 检测）？  
**典型答**：要。violating content 不放出来。

**你问**：要不要去重（同一图重复上传 1 次存储）？  
**典型答**：v1 不需要，v2 可加 perceptual hash dedup。

**你问**：图片用户拥有还是公开？  
**典型答**：默认 private（带 auth）。能 share generate public URL。

### 2.2 非功能性

**你问**：用户量 / 上传频率？  
**典型答**：1B users, 1B uploads/day (avg)。Peak 5x。

**你问**：图片大小？  
**典型答**：avg 3 MB，max 50 MB。

**你问**：上传延迟感知？  
**典型答**：< 5 秒 (5MB / 1 Mbps 上传带宽)。

**你问**：处理后 ready 多久？  
**典型答**：< 30 秒可访问 thumbnail (用户期望立即看到自己刚传的)。

### 2.3 需求清单

```
功能：
- Mobile / Web 上传 (3-50 MB)
- Resumable (中断恢复)
- 生成 thumb / medium / large variants
- NSFW 审核
- 返回 URL
- private / public sharing

非功能：
- 1B uploads/day (avg 12k QPS, peak 60k)
- 上传 < 5s
- 处理完 < 30s 可访问
- 99.999% durability
- 全球延迟 < 100ms 加载 thumbnail
```

> [!key]
> 关键观察：**上传流量 vs 下载流量 = 1:100+**。一张图被传一次但可能被看几千次。所以 read path 优化（CDN）比 write 重要。

---

## 3. 容量估算

### 3.1 流量

```
上传 QPS:
  1B / 86400 = 12k QPS avg
  Peak 5x = 60k QPS

每张 3 MB:
  60k × 3 MB = 180 GB/sec
```

→ 如果 upload 走 backend → 180 GB/s 带宽，全球需几百 server。**不行**。必须 client 直传 S3。

### 3.2 存储

```
1B uploads/day × 3 MB = 3 PB/day raw
+ 3 variants 各占 30% = ~5 PB/day total
× 365 day = 1.8 EB/year
```

→ 用 hot/warm/cold tiering 控成本（hot 1 month 在 S3 Standard，warm 90 day 在 S3 IA，cold 1+ year 在 Glacier）。

### 3.3 下载

```
每图 avg 1000 views/year (Instagram-style social)
= 1B images × 1000 = 10^12 views/year
= 30M views/sec
```

→ 必须 CDN，99%+ hit rate，origin 实际 ~300k QPS。

### 3.4 估算清单

```
上传：60k QPS peak, 180 GB/s → 必须 direct-to-S3
处理：60k QPS × 3 variants = 180k tasks/sec → async worker pool
存储：1.8 EB/year → hot/cold tiering
下载：30M QPS → CDN 99% hit
```

---

## 4. 整体架构 step by step

### 4.1 第 0 步：朴素方案（走 backend）

```ascii
   Client (5 MB image)
       │  POST /upload (multipart/form-data)
       ▼
   ┌──────────────┐
   │ Backend      │  接收 5 MB 流，处理，写 S3
   └──────────────┘
```

**问题**：
- 60k QPS × 3 MB = 180 GB/s 流量打 backend → 网卡爆 + 服务慢
- Backend 必须接完整个 image 才能返回成功 → 弱网用户超时
- 不能 resumable → 5 MB 传到 4.9 MB 断了重头来

### 4.2 第 1 步：Direct-to-S3 + Presigned URL

让 client **直接传到 S3**，backend 只生成上传凭证。

```ascii
   Step 1: Client → POST /upload/init
         → Server 调 S3 API 创建 multipart upload session
         → Server 返回：
           - upload_id
           - 多个 presigned URLs (one per part, 5 MB chunk)
   
   Step 2: Client → PUT each chunk directly to S3
         (并发上传多个 chunk)
   
   Step 3: Client → POST /upload/complete
         → Server 调 S3 CompleteMultipartUpload
         → Server: enqueue async processing
         → Server: return image_id 给 client
```

**这个流程的好处**：

✅ Backend **不接图片流量**，只生成 token + 数据库记录  
✅ Multipart 天然 **resumable**（断了 chunk 重传）  
✅ Client 可**并发** upload chunks，加速上传  
✅ 可扩展（backend 可以处理 1M QPS metadata，不受图片流量限制）  

### 4.3 第 2 步：Async Processing Pipeline

上传成功后 Server **不直接处理图片**，扔队列让 worker async 处理：

```ascii
   Upload complete event
         │
         ▼
   ┌──────────────┐
   │ S3 Event /   │  S3 上传完触发 event 或 Kafka 写入
   │ Kafka topic  │
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────────────┐
   │ Image Worker Pool            │
   │ 每 worker 做：                │
   │ 1. Download original         │
   │ 2. 生成 3 variants (resize)  │
   │ 3. Format convert → WebP     │
   │ 4. EXIF extract              │
   │ 5. NSFW check (ML model)     │
   │ 6. Upload variants to S3     │
   │ 7. Update DB record          │
   └──────┬───────────────────────┘
          │
          ▼
   DB: image record status='ready'
```

**为什么 async**：处理一张图可能 5-30 秒（generate 3 variants + ML inference）。**绝不能 sync 让用户等**。

用户上传立即返回 image_id + URL（thumbnail status='pending'）。前端先显示 loading，几秒后 poll 或 push 通知 ready。

### 4.4 第 3 步：URL 设计 + CDN

```
存储路径:
  s3://images/{user_id}/{image_id}/original.jpg
  s3://images/{user_id}/{image_id}/large.webp
  s3://images/{user_id}/{image_id}/medium.webp
  s3://images/{user_id}/{image_id}/thumb.webp

返回 URL:
  https://cdn.example.com/{user_id}/{image_id}/medium.webp
```

CDN 缓存所有 variant（图片是 immutable，可 TTL = 永久）。99%+ hit rate。

### 4.5 第 4 步：完整架构

```ascii
┌────────────────────────────────────────────────────────────┐
│                     Client                                 │
│   1. POST /upload/init → get presigned URLs                │
│   2. PUT chunks directly to S3 (并发)                      │
│   3. POST /upload/complete → backend enqueue processing    │
└────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
   ┌─────────┐     ┌────────────┐    ┌──────────────┐
   │ Upload  │     │ S3         │    │ DB           │
   │ API     │     │ (original) │    │ (metadata)   │
   └─────────┘     └─────┬──────┘    └──────┬───────┘
                         │                  │
                         │ S3 event         │
                         ▼                  │
                   ┌──────────────┐         │
                   │ Kafka topic  │         │
                   │ image.uploaded│        │
                   └──────┬───────┘         │
                          │                 │
                          ▼                 │
                   ┌──────────────────┐     │
                   │ Image Worker     │     │
                   │ Pool (lambda /   │     │
                   │ k8s job)         │     │
                   │ - resize         │     │
                   │ - format         │     │
                   │ - NSFW check     │     │
                   │ - upload variants│─────┘
                   └──────┬───────────┘     update DB
                          │
                          ▼
                   ┌──────────────┐
                   │ S3 (variants)│
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ CDN (global) │
                   └──────┬───────┘
                          │
                          ▼
                       Viewers
```

---

## 5. 每个组件深挖

### 5.1 Direct-to-S3 详细

```python
# Client → backend
POST /upload/init
{
  "filename": "vacation.jpg",
  "size_bytes": 5000000,
  "mime_type": "image/jpeg"
}

# Backend response
{
  "image_id": "img_abc123",
  "upload_id": "S3_multipart_xxx",
  "parts": [
    {"part_number": 1, "url": "https://s3...?part=1&token=xxx"},
    {"part_number": 2, "url": "https://s3...?part=2&token=xxx"},
    ...
  ]
}

# Client uploads chunks
PUT https://s3...?part=1&token=xxx  → 5 MB chunk
PUT https://s3...?part=2&token=xxx  → 5 MB chunk
...

# Each successful PUT returns ETag
PUT response: ETag: "abc123..."

# Client → backend
POST /upload/complete
{
  "image_id": "img_abc123",
  "upload_id": "S3_multipart_xxx",
  "parts": [
    {"part_number": 1, "etag": "abc"},
    ...
  ]
}

# Backend
- 调 S3 CompleteMultipartUpload(upload_id, parts)
- DB: INSERT images (id, user_id, original_url, status='processing')
- Kafka: produce {image_id, original_url} to image.uploaded topic
- Return: {image_id, status='processing'}
```

**Resumable trick**：上传失败的 chunk 可以**只重传那个 chunk**，已成功的 chunk S3 已记 ETag，不必重传。

### 5.2 Image Worker 详细

```python
from PIL import Image
import asyncio

async def process_image(event):
    """Triggered by Kafka event after S3 upload complete."""
    image_id = event['image_id']
    s3_key = event['original_url']

    # 1. Download original
    img_bytes = s3.get(s3_key)
    img = Image.open(io.BytesIO(img_bytes))
    
    # 2. Extract EXIF
    exif = img._getexif() or {}
    taken_at = parse_exif_datetime(exif)
    gps = parse_exif_gps(exif)
    
    # 3. Generate variants (parallel)
    variants = await asyncio.gather(
        resize_and_upload(img, 128, image_id, 'thumb'),
        resize_and_upload(img, 512, image_id, 'medium'),
        resize_and_upload(img, 1024, image_id, 'large'),
    )
    
    # 4. NSFW check (async, parallel with variants)
    nsfw_score = await ml_nsfw_classifier(img)
    
    # 5. Update DB
    db.update(image_id, {
        'status': 'ready' if nsfw_score < 0.5 else 'flagged',
        'variants': dict(zip(['thumb', 'medium', 'large'], variants)),
        'exif': {'taken_at': taken_at, 'gps': gps},
        'moderation': {'nsfw_score': nsfw_score},
    })
    
    # 6. Notify client (push notification / WebSocket)
    notify_user(image_id, 'ready')

async def resize_and_upload(img, target_width, image_id, name):
    """Resize 后转 WebP 上传到 S3."""
    aspect = img.size[1] / img.size[0]
    target_h = int(target_width * aspect)
    resized = img.resize((target_width, target_h), Image.LANCZOS)
    
    buf = io.BytesIO()
    resized.save(buf, 'WEBP', quality=85)
    
    key = f"images/{user_id}/{image_id}/{name}.webp"
    s3.put(key, buf.getvalue())
    return f"https://cdn.example.com/{key}"
```

### 5.3 Database schema

```sql
CREATE TABLE images (
  id              UUID PRIMARY KEY,
  user_id         UUID NOT NULL,
  original_url    TEXT,                  -- S3 path
  variants        JSONB,                 -- {thumb: url, medium: url, large: url}
  status          TEXT,                  -- 'uploading' / 'processing' / 'ready' / 'flagged' / 'failed'
  bytes           BIGINT,
  width           INT,
  height          INT,
  format          TEXT,
  exif            JSONB,
  moderation      JSONB,                 -- {nsfw_score, manual_review_status}
  uploaded_at     TIMESTAMPTZ DEFAULT now(),
  is_public       BOOLEAN DEFAULT false,
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_user_images ON images(user_id, uploaded_at DESC) 
WHERE deleted_at IS NULL;
```

**新手 question**：

❓ **variants 为什么 JSONB 而不是单独表？**  
variants 数量固定 (3-4 个)，每条 image 都有。Single JSONB column 减少 JOIN。

❓ **为什么 soft delete (deleted_at) 而不是 DELETE?**  
用户误删可以恢复（30 天 grace period）；compliance 需要 audit。

### 5.4 NSFW / Moderation Pipeline

```ascii
   Image uploaded
       │
       ▼
   ┌──────────────────┐
   │ Fast ML model    │  ResNet / EfficientNet, < 100ms
   │ - nsfw_score     │
   │ - violence_score │
   └──────┬───────────┘
          │
   ┌──────┼──────┐
   ▼      ▼      ▼
  score   score   score
  < 0.3   0.3-0.7 > 0.7
   │      │      │
   │      │      └→ Auto-block, status='flagged'
   │      └────────→ Manual review queue (human moderator)
   └──────────────→ status='ready'
```

**Gray zone (0.3-0.7)**：进人工 review 队列。审核员每天看几千张。

### 5.5 CDN + Hot/Cold Tiering

```
S3 Standard:  最近 1 个月内的图，CDN 频繁访问
S3 IA:        1-3 月，访问频率低，每月 retrieve 费
S3 Glacier:   1+ 年，几乎不访问，retrieve 几分钟到几小时
```

CDN cache 永久（图片 immutable）。CDN miss → S3 (Standard) hit。如果用户访问超老照片，S3 Standard miss → 触发 retrieve from Glacier → 用户等几秒 → 通知 ready。

### 5.6 Deduplication (可选 v2)

不同用户上传同图（meme, 风景画），存 3 份浪费。

```python
def upload(file):
    phash = perceptual_hash(file)   # 64-bit hash
    existing = db.query("SELECT id FROM images WHERE phash=? AND deleted_at IS NULL", phash)
    if existing and similar(existing, file):
        # 不重新存储，只 link reference
        return create_user_reference_to(existing.id)
    # 正常 upload
```

**Save 30-50% storage** for social platforms (大量 meme reshare)。

### 5.7 Resumable Upload 详细

Multipart upload 已经天然 resumable，但需要 client SDK 配合：

```javascript
// Client SDK
async function upload(file) {
  const session = localStorage.getItem(`upload:${file.name}`);
  let uploadInfo;
  
  if (session) {
    uploadInfo = JSON.parse(session);
    // Server check 已上传 chunks: HEAD multipart upload
    const completed = await checkProgress(uploadInfo.upload_id);
    uploadInfo.parts = uploadInfo.parts.filter(p => !completed.includes(p.part_number));
  } else {
    uploadInfo = await fetch('/upload/init', {...});
    localStorage.setItem(`upload:${file.name}`, JSON.stringify(uploadInfo));
  }
  
  for (const part of uploadInfo.parts) {
    await uploadPart(part);
  }
  await fetch('/upload/complete', {...});
  localStorage.removeItem(`upload:${file.name}`);
}
```

弱网下断了，下次再传只续传剩余 chunk。**用户体验关键**（uploaded 80% 不愿意全重传）。

---

## 6. 面试节奏 — 45 分钟怎么讲

```
0:00 - 0:05  Clarifying Questions
  - 哪些 variants？
  - Resumable？
  - Moderation?
  - QPS / 用户量

0:05 - 0:10  Capacity Estimation
  - 60k QPS upload peak
  - 180 GB/s 流量 (强调 backend 不能扛)
  - 1.8 EB/year 存储
  - 30M QPS download (CDN 99% hit)

0:10 - 0:15  High-Level Architecture
  - Direct-to-S3 + presigned URL
  - Async worker pipeline
  - CDN serving variants

0:15 - 0:30  Deep Dive
  ★ Direct upload 流程详细 (3-step protocol)
  ★ Resumable multipart
  ★ Worker pipeline + NSFW
  ★ Hot/cold storage tiering

0:30 - 0:38  Follow-ups
  - Deduplication
  - Moderation appeal flow
  - Cost optimization
  - Mobile-specific optimizations

0:38 - 0:45  Wrap-up
```

---

## 7. 面试样板讲解

> "OK 这是图片上传。我先确认几件事：变体是 thumbnail/medium/large 加原图，对吧？Resumable 需要，因为 mobile 弱网常断。NSFW 审核需要。
> 
> 估算：60k QPS upload peak × 3 MB = 180 GB/s。这一秒就告诉我 **backend 不能接图片流量** —— 这是 trillion-dollar mistake，必须 direct-to-S3。
> 
> 流程是 **3-step**：(1) Client POST /upload/init，server 调 S3 创建 multipart session，返回 presigned URL；(2) Client 直接 PUT chunks 到 S3；(3) Client POST /upload/complete，server 触发 async 处理。
> 
> 异步处理是关键。Server 在 step 3 立刻 return，用户不等。Image worker pool 从 Kafka 消费 event：download → 生成 thumb/medium/large（PIL resize）→ NSFW ML 检测 → 写 DB → 通知用户。整个流程通常 5-30 秒，用户先看 loading 占位，ready 后 push 通知 / WebSocket 推送。
> 
> CDN serve 所有 variants —— 图 immutable，TTL 设永久，99%+ hit rate。S3 hot/cold tiering 节省成本：1 月内热数据 S3 Standard，1 年后下沉到 Glacier。
> 
> Resumable 关键在 multipart —— 失败 chunk 单独重传不必全重。Client SDK 用 localStorage 记 upload_id + part 状态。
> 
> 想 deep dive moderation 还是 dedup？"

---

## 8. Follow-up 演练

### Q1: 同时多端上传相同图（手机 + 平板同步备份）？

**答**：Server 检测 user_id + perceptual hash + size 完全一致 → 视为 duplicate，返回已有 image_id（idempotent）。

### Q2: 用户撤销上传到一半？

**答**：S3 multipart upload 有 abort API。Server 检测到 client 取消（idle 超时 / explicit cancel）→ 调 abort → S3 释放未完成 part 的存储。

### Q3: 上传后用户立即看不到 thumbnail（worker 还没处理完）？

**答**：UI 显示 placeholder + spinner。前端长 poll / WebSocket。Worker 处理顺序：thumbnail 优先（先生成，先 push 给用户）。

### Q4: NSFW 误判 (false positive)？

**答**：Appeal queue。用户 click "申诉" → 进人工 review → 验证后恢复 + 用 user feedback 改 ML model。

### Q5: 怎么防 abuse (用户大量传图占空间)？

**答**：
- 配额：免费 user 15 GB，超过需付费
- Rate limit：每分钟 100 张
- 检测垃圾内容（黑/白图、纯色图、文件大小异常）→ 直接拒绝

### Q6: HEIC (iPhone) 格式怎么办？

**答**：Worker 支持 HEIC decode → 转 JPEG / WebP 后再生成 variants。或前端 SDK 在 client side 转换（更省 server 算力）。

### Q7: 怎么 detect 同一 image 多用户上传（dedup）？

**答**：phash + Bloom filter 大概率检测，再做完整比较。dedup 后存储节省，但要 careful per-user 权限 reference count。

### Q8: GDPR 删除？

**答**：删除有 30 天 grace period (soft delete) → 物理 delete S3 object + variants + CDN cache invalidation + DB hard delete。

---

## 9. 常见易错点

> [!pitfall]
> ❌ **上传走 backend** —— 流量爆 + 不能 scale；必须 client 直传 S3；  
> ❌ **不用 multipart** —— 大文件断了全重传，体验差；  
> ❌ **Sync processing** —— 用户等 30 秒；必须 async；  
> ❌ **Variant URL hardcode 进 schema** —— 加新 size 要 alter table；用 JSONB；  
> ❌ **不做 moderation** —— legal 风险；  
> ❌ **不区分 hot/cold storage** —— 成本爆；  
> ❌ **CDN cache 不设 immutable** —— 浪费 origin QPS；  
> ❌ **不做 resumable** —— 弱网用户怒卸 app；  
> ❌ **同步 EXIF / NSFW** 在 upload critical path —— 慢。

---

## 10. 加分项

- **AI tagging / auto-album**：ML extract scene/people/object → 自动相册分类
- **Smart compression**：根据图片复杂度自适应 quality（plain image 高压缩、详细图低压缩）
- **Adaptive variant size**：基于 client device 自动 pick 合适尺寸（mobile 用 medium，desktop 用 large）
- **Encryption at rest** + **per-user key**（高安全场景）
- **Watermark**：可选自动加水印保护版权
- **Burst upload (live photo)**：100 张连拍优化批量上传
- **Video extension**：同框架扩展到视频上传（HLS 多分辨率）

---

## 11. 总结：你应该记住的 3 件事

1. **Direct-to-S3 是必修**。Backend 接图片流量不可扩展。Presigned URL + multipart 是工业标准 (AWS / GCP / Azure / Aliyun 都一样)。

2. **上传 + 处理解耦 (async pipeline)**。Worker 池消费 Kafka event 异步处理 → 用户 perceive 即时上传完成 → 几秒后看到生成完毕。

3. **CDN + multi-variant + tiered storage 是成本三件套**。Image-heavy 系统不做这 3 件成本 10x 涨。

> [!followup]
> **学习推荐**：(a) 跑一遍 AWS S3 multipart upload tutorial；(b) 看 Instagram engineering blog 关于 image pipeline 的几篇；(c) 自己用 Python + Flask + boto3 实现一个 mini image uploader；(d) 学 Cloudflare Images / imgproxy 这种"动态 image resize" 替代预生成 variant 的思路；(e) 读 EXIF 标准，理解 GPS 隐私问题（很多 app 默认 strip 上传图的 GPS）。
