## 题目本质

设计 **Proximity Alert System for Apple Tags**（Apple AirTag / Tile）：物品丢失时 owner app 显示位置。利用 **anonymous nearby Apple devices 中继**报告 tag 位置。

## 需求

- 100M+ tags worldwide
- Privacy：owner 之外没人知道 tag 位置
- 离 owner 几公里仍能定位 (crowdsourced location)
- Battery：tag 1 年电池

## 整体架构 (Find My network)

```ascii
   AirTag (BLE beacon)
       │ broadcasts encrypted public key
       ▼
   Nearby Apple devices (iPhone / iPad)
       │ pick up BLE，relay encrypted (location, time, key)
       ▼
  ┌──────────────┐
  │ Apple cloud  │  end-to-end encrypted - server 看不懂内容
  │ (E2E         │
  │ encrypted)   │
  └──────┬───────┘
         │
         ▼
   Owner device
       │ query server with private key
       ▼
   Decrypt → location → display
```

## 核心技术：End-to-End Encryption

### 1. Key rotation

Tag generate (private, public) key pair。Periodic rotate public key (every ~15 min) to prevent tracking by 3rd parties。

Owner device shares private key（through iCloud key sync），可以 derive 任意时刻 public key + decrypt corresponding reports。

### 2. Anonymous relay

Nearby iPhone:
- 扫到 BLE beacon (public key advertised)
- 不知道是谁的 tag
- Encrypt (current GPS, time) with that public key → upload to Apple cloud

Apple 也不知道内容。Only owner with private key can decrypt。

### 3. Tag → server (NO direct path)

Tag itself 只 BLE broadcast，不连 internet。完全依赖 nearby Apple device crowd-sourced。

### 4. Owner queries

Owner app:
- Generate set of public keys（基于 private key + time range）
- Query server by public key hashes
- Server returns encrypted location reports matching
- Owner decrypts locally

### 5. Privacy guarantees

- Apple server: 只见加密 blob + opaque public key
- Relay device: 不知道是哪个 tag / 谁的
- Public key rotation: 防长期 tracking by adversary observing BLE
- Anti-stalking: tag away from owner for X hours → 主动 beep + iPhone 通知附近 user "an AirTag is following you"

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Network | Crowdsourced via Apple devices | Cellular tag：贵 + battery 短 |
| Crypto | E2E with key rotation | Server-known location：privacy fail |
| Range | BLE | Cellular：5x battery drain |
| Anti-stalk | Auto-beep + alert | None：abuse risk |

## 关键技术细节

- ECC P-224 + AES encryption
- Key derivation: T_i = HKDF(master_key, time_i)
- Per-tag periodic key rotation period ~15 min
- BLE advertisement: includes public key fragment

## 易错点

> [!pitfall]
> ❌ Apple sees plain location → privacy disaster；
> ❌ 不 rotate key → stalker can track by static key；
> ❌ 不 anti-stalking → 严重 abuse；
> ❌ Cellular instead of BLE → battery 几天 die；
> ❌ Owner key 不 backed up → 丢失永远定位不回 tag。

> [!key]
> 三大要点：(1) **E2E encryption with rotating public key** 让 server 看不见内容；(2) **Crowdsourced relay via Apple devices** 不依赖蜂窝；(3) **Anti-stalking measures** balance utility + safety。

> [!followup]
> "Battery life 1 year？" → BLE low duty cycle + small battery；"Anti-spoof (假装 AirTag 引人到陷阱)？" → 加 cert chain，only verified hardware can emit；"非 iOS 设备能查 AirTag？" → Apple 提供 Android app 检测 stalking AirTag。
