## 题目本质

设计 **Netflix / Video Streaming Platform**：videos 上传 → encode 多分辨率 → CDN 分发 → ABR 客户端播放。亿用户级。

参考 [[cm6wu2x3y0000356pl299toa0]] (YouTube) - 整体框架同。这里 angle 是**长尾内容 + 个性化推荐**而非 UGC scale。

## 与 YouTube 区别

| 维度 | Netflix | YouTube |
|---|---|---|
| 内容 | 自制 + licensed (~10k titles) | UGC (billions) |
| Upload 频率 | 慢 / 高质 | 高频 / 杂 |
| Encoding | 顶级（4K HDR per-title optimization） | Mass scale fast encode |
| 推荐 | 重 personalization (CF + content) | recency + engagement |
| 离线 | downloads | 大 limit |
| Live | 少 | 大 |

## 核心组件

### 1. Per-title encoding

Netflix 著名"per-title encoding" —— 不是固定 bitrate ladder。Action movie 复杂场景 high bitrate；卡通 low bitrate 也 OK。每 title encode 时 optimize 参数。

**Encoding pipeline**:
- Master ingest → multi-pass analysis
- 决定 ladder (e.g. 1080p needs 5 Mbps for this title vs 8 Mbps for another)
- Encode N ladders × M codecs (H.264, H.265, AV1)
- QC + 自动 quality scoring
- 推 CDN

### 2. Adaptive Bitrate (ABR)

参考 YouTube。Client measure bandwidth → select bitrate variant per chunk。

Netflix 用 **Dynamic Optimizer** —— 不只看 bandwidth，还估 device screen size + quality preference (some user 偏 mobile data 省)。

### 3. CDN 多层

Netflix 自建 OpenConnect Appliance：装在 ISP 数据中心 → 内容从 ISP 内部 deliver，bypass internet backbone。

每 ISP 一台 appliance 装 popular titles cache。冷内容 fall back 中心 CDN。

### 4. 推荐系统

两阶段：
- **Candidate**：collaborative filtering (similar users watch what) + content-based (genre/cast/director similarity)
- **Ranking**：DNN scoring per user

Netflix 著名"row-based" UI：homepage 是 N rows，每 row 是一个 theme（"Continue Watching", "Action Thrillers"）。Row selection + within-row ordering 都 personalized。

### 5. A/B testing

Netflix everything is A/B tested:
- Thumbnail (per-show 不同 user 看不同 thumbnail)
- Row order
- Autoplay behavior
- New UI

Massive A/B framework underlying。

### 6. 离线下载

下载 = encode 一份特殊格式 (DRM wrap + offline-friendly)，client 缓存 SD card / local。播放时 license server verify。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Encoding | Per-title optimized | Fixed ladder：浪费 |
| CDN | OpenConnect (ISP-local) | Generic CDN：高 backbone cost |
| 推荐 | 重 personalization | Top trending：低 retention |
| DRM | Widevine / FairPlay | None：被盗 |

## 关键 metric

- Bits per pixel per second
- Stall rate (re-buffering occurrences)
- Time-to-first-frame
- Hours watched per user
- Subscription retention

> [!key]
> Netflix vs YouTube：**前者重 quality + personalization + CDN penetration，后者重 scale + speed**。Per-title encoding + OpenConnect 是 Netflix unique。

> [!followup]
> "Live streaming on Netflix（boxing match）？" → 单独 pipeline，sub-second latency CDN。"如何防止 password sharing？" → device fingerprint + sometimes-IP-checks；2023 enforcement。"4K HDR 增加 storage？" → 但 OpenConnect cache 大部分 popular 内容。
