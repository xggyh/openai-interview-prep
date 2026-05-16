## 题目本质

设计 **system to rollout new versions of a mobile OS to devices worldwide**：iOS / Android 这种 OTA (over-the-air) 系统级更新。10 亿+ devices，需 **rollout 阶梯 + 回滚 + bandwidth 控** + **device-specific**。

## 需求

- 10 亿 devices
- 多 device types (各 iPhone / Pixel 型号)
- 阶梯 rollout（先 1% → 10% → 100%）
- 异常自动 halt
- Resume on network interruption
- Battery / Wi-Fi 时机

## 整体架构

```ascii
   OS Build (publisher)
       │
       ▼
  ┌──────────────┐
  │ Update       │  meta: version, model compatibility,
  │ Manifest     │     size, delta-from previous
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Rollout      │  rollout state per device segment
  │ Controller   │  decide who can get update now
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ CDN          │  global edge cache of update files
  │ (regional)   │
  └──────┬───────┘
         │
         ▼
   Devices download
         │
         ▼
  ┌──────────────┐
  │ Telemetry    │  install success / fail rate
  └──────────────┘
```

## 核心组件

### 1. Rollout 阶梯 (canary)

```
Phase 0: Apple/Google internal (1k devices)
Phase 1: 1% public 24 hours
Phase 2: 10% 48 hours
Phase 3: 50% 1 week
Phase 4: 100%
```

每 phase 监控 metric:
- Crash rate
- Boot success rate
- Battery / temperature anomalies
- User-reported bugs

异常 → automated halt + alert + 决策 rollback。

### 2. Device segmentation

Rollout 不只是 random %。维度：
- Device type (iPhone 14 Pro vs 11)
- Region (US first，India 后)
- Network condition (Wi-Fi only initial; cellular later)
- Build / firmware compatibility

每 device 看 server："Am I eligible for update X?" Server replies based on segmentation rules。

### 3. Manifest & delta

Update 不是全 OS 重下。Delta = diff from previous version → 100 MB instead of 5 GB。Per device 之前版本的 delta 单独算。

设备发 "current version" → 服务器 reply 对应 delta URL。

### 4. CDN 分发

Update file 几 GB × 10 亿 devices = 数 EB total bandwidth。CDN edge cache hit critical。Per-region CDN 预热。

### 5. 下载 + install

Device pull manifest → check eligibility → download chunked from CDN → verify signature → install。

- Background download (Wi-Fi + 充电 + 屏幕关)
- Pause / resume
- Verify SHA256

### 6. Install timing

不要 user 用着手机时强制 reboot。等：
- 电量 > 50%
- Charging
- 凌晨 2-4AM 用户睡觉

User 可选 "install now" override。

### 7. Telemetry + halt

Device 安装完成后 phone home metrics:
- Pre-install / post-install boot time
- Crash logs first 24 h
- Battery drain
- Temperature

Aggregate → ML detect anomaly per device type → auto halt rollout。

### 8. Rollback

如果 phase 1 检测到 critical issue：
- Stop further rollout
- Push "roll-back firmware" to affected devices (rare, dangerous)
- Or push hotfix forward

True rollback rare（hard to revert installed OS）→ 优先 forward fix。

### 9. Multi-tenant variant

Carrier-specific builds（Verizon vs AT&T iPhone）。Per-carrier manifest + same infrastructure。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Rollout | Staged % | All at once：risk |
| File | Delta | Full：bandwidth waste |
| Halt | Auto + manual | Manual only：lag |
| Install timing | Idle + charging | Force：UX disaster |

## 容量估算

- 1B devices × 100 MB delta = 100 PB total
- CDN 99% hit → 1 PB origin egress
- Telemetry: 1B × 10KB = 10 TB/day inbound

## 易错点

> [!pitfall]
> ❌ 全部一次推 → bandwidth + brick devices；
> ❌ 不 verify signature → malicious update；
> ❌ Force install → user 愤怒；
> ❌ Halt criteria not automatic → ride disaster；
> ❌ 不区分 carrier variant → wrong build。

> [!key]
> 三大要点：(1) **Staged rollout + automated halt** by telemetry；(2) **Delta + per-device manifest** 节 bandwidth；(3) **Smart install timing** 不打扰 user。

> [!followup]
> "Security patch 紧急 (CVE)？" → expedited rollout 跳过 long canary，但仍 monitor；"Beta program 怎么 onboard？" → opt-in segment + early access channel；"如何 detect device brick？" → no telemetry phone-home → emergency recovery image。
