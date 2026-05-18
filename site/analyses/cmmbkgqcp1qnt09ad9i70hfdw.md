## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **Smart alarm** | 跨设备的闹钟 —— 在手机/手表/智能音箱任一设备设置都生效 | 老板让全公司任一秘书都能改你的日程 |
| **Effective device** | 实际响铃的那台设备（不是全部都响） | 多个秘书，但只有"主秘书"打电话叫醒你 |
| **Push notification** | 服务器主动推到设备的消息（不用 client poll） | 邮局上门派件 |
| **APNs / FCM** | Apple / Google 的官方 push 通道 | 邮局 |
| **Wake lock / wakeup alarm** | OS 级"到时间叫醒"机制，省电关键 | 闹钟物理按键 |
| **Offline-first** | 设备没网也能用，网络恢复后同步 | 离线模式做笔记 |
| **CRDT** | 一种数据结构，多端各自改、自动 merge 到一致 | 多人协同编辑文档无冲突 |
| **Eventual consistency** | 最终一致，中间可能 lag 几秒 | 改完文件几秒后所有人看到 |
| **Idempotent operation** | 操作可重复执行，结果不变 | 按 N 次电梯按钮 = 按 1 次 |
| **Time zone** | 时区，user 7AM 本地 ≠ server UTC 7AM | 北京 8AM = 纽约前一天 8PM |
| **DST (Daylight Saving Time)** | 夏令时切换，时钟跳 1 小时 | 时钟突然往前/后跳 |
| **Heartbeat** | 设备定期上报"我活着"，server 用来判断 device 在线 | 哨兵每 30 秒报平安 |
| **Geofencing** | 基于位置触发（在某区域内/外 → 动作） | "进入公司大门就静音" |

---

## 1. 题目本质

**Smart Alarm System** = 跨设备闹钟服务，**任一设备 set/edit/delete，按规则只在指定设备响铃**。

**典型产品**：
- **Apple Clock** —— iPhone / Watch / HomePod / Mac 同步
- **Google Clock** —— Android / Nest / Pixel Watch
- **Alexa alarms** —— Echo / phone app 同步
- **Sleep cycle apps** —— 配合智能手环 / 手表

**为什么这是 STAFF 题**：

不是"做闹钟"那么简单。考的是：

1. **Multi-device sync**：1 个 user 5 个 device，全部要看到一致的 alarm 列表
2. **Selective trigger**：5 个 device 都收到 alarm，但只一个响（如何决定？）
3. **Offline-first**：手表没网时设了 alarm，还能响吗？
4. **时间精确性**：alarm 7:00 必须 ±1 秒内响，不能 5 分钟才响
5. **跨时区 + DST**：用户出差怎么办？

考 STAFF 关键：**multi-device consistency + push timing** 的组合 trade-off。

---

## 2. 需求拆解

### Functional

| API | 含义 |
|---|---|
| `CreateAlarm(user, time, label, repeat?, effective_device?) -> alarm_id` | 创建 alarm |
| `UpdateAlarm(alarm_id, ...)` | 改 alarm |
| `DeleteAlarm(alarm_id)` | 删 alarm |
| `ListAlarms(user) -> alarm[]` | 列所有 |
| `Snooze(alarm_id, duration)` | 推迟 |
| `Dismiss(alarm_id)` | 关掉响铃 |
| `RegisterDevice(user, device_id, type, capabilities)` | 设备注册 |

**澄清要点**：
- 一次性 vs 重复（每周一 7AM）？支持哪些 repeat pattern？
- 是 server-side 触发还是 client-side 触发？(关键决策)
- Effective device 怎么选？自动还是手动？
- 是否要 voice control / geofence triggers？

### Non-functional

| 维度 | 目标 | 为什么 |
|---|---|---|
| **触发精度** | ±1 秒 | 7:00 响在 7:00:05 用户能接受，7:05 不行 |
| **Sync 延迟** | < 5s 跨设备 | 用户改了应该马上同步 |
| **Offline 工作** | 必须支持 | 飞机模式也要响 |
| **Scale** | 100M users × 5 devices × 5 alarms = 2.5B alarms | 量不大但 trigger 频繁 |
| **Availability** | 99.95% | 闹钟不响是严重问题 |
| **Consistency** | eventual | 没必要 strong |

> [!key] 这道题没有海量数据，但**precise timing + multi-device sync** 是真核心。别被量级误导。

---

## 3. 容量估算

- **Users**: 100M active
- **Devices/user**: 平均 3 (phone + watch + speaker)
- **Alarms/user**: 平均 5
- **Total alarms**: 500M active alarms
- **Trigger rate**: 早 7-8 AM peak，假设 30% users 同时段 → 30M alarms in 1 hour → **10k triggers/sec peak**
- **Edit rate**: 100M edits/day → ~1200 QPS sustained

**存储**：500M alarms × 200 B = 100 GB → 单机能装，主要瓶颈是 trigger fan-out。

---

## 4. 关键设计决策：Server-side vs Client-side trigger

这道题的核心 trade-off。

### Option A: Server-side trigger

```
Server 维护 alarm 的"下次触发时间"队列
   → 到点 server 发 push notification 到 effective device
   → device 收到 push → 响
```

**优点**：
- 容易做 multi-device 选 effective device 逻辑（server 决策）
- alarm 改了立即生效（server 重算）

**缺点**：
- **离线设备收不到 push** → alarm 不响（飞机模式致命）
- Server 必须 100% 可用
- Push 延迟波动（APNs/FCM 99% < 5s, p99 偶尔 30s）

### Option B: Client-side trigger

```
Device 本地存 alarm，OS 级 wakeup alarm 到点响
Server 只做"sync alarm 数据"的角色
```

**优点**：
- **离线也响**（OS 闹钟物理 alarm）
- 触发精确（OS 级 ±10ms）
- Server 挂了不影响触发

**缺点**：
- 5 个 device 都本地存 alarm → **谁响**是难题
- Sync delay 期间设备数据不一致

### Option C: Hybrid（推荐）

**Client-side 是 source of truth for triggering，server-side 是 sync engine + tie-breaker。**

- Alarm 数据**全部本地存 + 设 OS wakeup alarm**
- Server 仅负责**sync 状态 across devices** + **决定 effective device**
- 离线设备照样响（OS 级）
- Effective device 选举走 server，离线时 fallback 到"hierarchy"（手表 > 手机 > 音箱）

> [!key] 这是 Apple Clock 的真实设计：alarm 全 sync 到所有 device，每个 device 本地 schedule OS alarm，effective device 通过 iCloud 协调。

---

## 5. 高层架构

```
┌───────────────────────────────────────────────────┐
│  Device (phone/watch/speaker)                      │
│   - Local alarm DB                                 │
│   - OS-level wakeup alarm scheduler                │
│   - WebSocket connection (sync)                    │
└───────────────────────────────────────────────────┘
                │ sync ops
                ↓
┌───────────────────────────────────────────────────┐
│  Sync Service (server)                             │
│   - WebSocket fan-out                              │
│   - Conflict resolution (LWW or CRDT)              │
└───────────────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────┐
│  Alarm DB (Spanner / DynamoDB)                     │
│  Schema: alarm_id, user_id, time, label, repeat,   │
│          effective_device, version, updated_at     │
└───────────────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────┐
│  Trigger Service (backup, server-side fallback)    │
│   - Timer queue (Redis ZSET by trigger_time)       │
│   - Send push at trigger time                      │
│   - Only fires if device hasn't ack'd local fire   │
└───────────────────────────────────────────────────┘
```

### Step 1: Device sync

- Device 启动 / alarm 改时 → WebSocket 推到 sync service
- Sync service 写 DB → fan-out 到 user 的其他 devices
- Devices 收到后本地写 + reschedule OS alarm

### Step 2: Trigger

- **Primary path**: 设备本地 OS alarm 到时间响
- **Backup path**: server timer 也到点，发 push（防止 device 本地 schedule 失败）
- Device 响后 ack server，server 取消 backup push

### Step 3: Effective device selection

- User 配置规则（"卧室 HomePod 优先，其次手表，其次手机"）
- Server-side：基于 device 在线状态 + 用户偏好 + recent activity
- 选中 device 拿到 `effective=true` flag，其他设为 `effective=false`（不响）
- **Offline fallback**：sync 中断时 device 按本地配置 fallback hierarchy

---

## 6. 组件深挖

### Deep Dive 1: 触发精度

**Server-side 用 timer queue**：

- Redis ZSET: `score = unix_timestamp_ms, member = alarm_id`
- 后台 worker 每 100ms 扫一次 `ZRANGEBYSCORE` 过期的 → 发 push
- 触发后 `ZREM`

**Client-side**：
- iOS `UNUserNotificationCenter.scheduleNotification(at: time)`
- Android `AlarmManager.setExactAndAllowWhileIdle(...)` (Doze mode 也响)
- Watch app 用 Watch OS API 设本地 alarm

**精度**：
- Client OS-level ±10 ms (excellent)
- Server push 端到端 p99 < 5s (不够，所以必须 client-side primary)

### Deep Dive 2: Multi-device Sync — CRDT vs LWW

**问题**：手机 set alarm 7:00, watch set alarm 7:30，**同时**操作同一 alarm → 用谁的？

**Option A: Last-Write-Wins (LWW)**
- 每次写带 timestamp，按 timestamp 选大的
- 简单，但**时钟漂移**会丢数据

**Option B: CRDT (LWW-Register or OR-Map)**
- LWW-Register: 同 LWW 但 timestamp 是 vector clock
- OR-Map: alarm 字段级 merge

**Option C: User-driven conflict resolution**
- 检测冲突 → 弹窗让用户选

**STAFF 答**：LWW with hybrid logical clock（Spanner-style，HLC = wall clock + counter），简单 + 防时钟回退。冲突极少（同一用户同 alarm 双端同时编辑），用户可接受。

### Deep Dive 3: Time Zone + DST

**问题**：alarm 设 7:00 (Beijing)，user 飞到 NYC：响 NYC 7:00 还是 Beijing 7:00？

**两种存储模型**：

| 模型 | 含义 | 何时用 |
|---|---|---|
| **Absolute time** | 存 UTC unix timestamp | "明天 早上的会议 6AM ET" → 用户飞了也是 ET 6AM |
| **Wall-clock time** | 存 "7:00 + TZ name" | "每天起床闹钟" → 用户飞了也是当地 7AM |

**Apple Clock 默认**：Wall-clock + device 当前 TZ → user 飞 NYC 自动 NYC 7AM 响。

**DST**：用 IANA TZ database（"America/New_York"），自动处理 DST 跳变。**不要用 offset (UTC-5)**，DST 时会错。

### Deep Dive 4: Offline Mode

**飞机模式下 set alarm**：

- Device 本地写 → 本地 schedule OS alarm
- 标记 "pending sync"
- 网络恢复 → push 到 server

**Server 挂了 device 也能响**：因为 OS-level alarm 本地驱动。

**反向**：飞机模式下其他 device 改了 alarm，本机收不到 → 醒来 sync 后看到。**eventual consistency 可接受**。

### Deep Dive 5: Effective Device Selection

**规则引擎**：

```python
def select_effective_device(user, alarm):
    devices = get_online_devices(user)
    if alarm.preferred_device in devices:
        return alarm.preferred_device
    # Fallback hierarchy from user prefs
    for kind in user.hierarchy:  # ["watch", "phone", "speaker"]
        match = next((d for d in devices if d.kind == kind), None)
        if match: return match
    return devices[0]  # any
```

**Offline scenario**：alarm 时所有 device 离线 → 不响（or 后续 device 上线 → late notification？取决于产品决策，闹钟通常不补发）。

### Deep Dive 6: Snooze / Dismiss Multi-device

**问题**：手机响了，user 在手机按 dismiss，**手表也在响**怎么办？

**解法**：dismiss/snooze 操作通过 WebSocket **立即广播**到所有 device → 其他 device 也停。

**Race condition**：手机 dismiss 同时手表 dismiss → 都 OK，操作 idempotent。

**Network 中断**：手机 dismiss 但 sync 失败 → 手表继续响 → user 在手表也 dismiss → 后续 sync 重发 dismiss → idempotent，安全。

### Deep Dive 7: Battery Optimization

**问题**：手表 / 手机一直 maintain WebSocket → 耗电。

**解法**：
- **APNs/FCM push** 唤醒：常规情况下连接 sleep，server 通过 push 唤醒
- **Heartbeat 间隔自适应**：插电时 30s，电池低时 5min
- **Wakeup alarm** 是 OS 级，不需要 app 后台运行（关键省电）

---

## 7. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清：server vs client trigger，how many devices, what alarm features |
| 5-10min | 容量估算（500M alarms, 10k trigger QPS peak） |
| 10-15min | API + schema |
| 15-25min | 高层架构：hybrid trigger (client primary + server backup) + sync service |
| 25-40min | Deep dives: timing precision / CRDT or LWW / time zones / offline / effective device |
| 40-45min | battery / DST edge cases |

---

## 8. 样板讲解稿

> Smart alarm 看似简单但有 4 个真正难点：multi-device sync, **selective trigger**, offline 友好, time zone/DST.
>
> 我的核心架构决策：**client-side primary + server-side backup**：
> - alarm 全 sync 到所有 device，每个 device 本地 schedule OS-level wakeup alarm（精度 ±10ms，OS 级，省电）
> - server 同时也存 alarm，timer queue 到点发 push 作为兜底
> - 这样离线设备照样响（OS 闹钟物理 alarm 驱动），server 挂了不影响
>
> **Multi-device sync**：WebSocket fan-out，LWW with HLC (hybrid logical clock) 解冲突。冲突极少（同一 user 双端同时编辑同 alarm），LWW 够用。
>
> **Effective device**：用户偏好 hierarchy + 在线状态。Server-side 计算后下发 effective flag 给指定 device。
>
> **Time zone**：默认 wall-clock + IANA TZ name（不是 UTC offset），自动处理 DST 跳变和跨时区。
>
> **Offline**：所有写本地优先 + 标 pending sync，网络恢复后 push。Server-side fallback 处理"5 device 都离线了 alarm 不响"的极端情况通过 OS-level reschedule。
>
> Scale：500M alarms 100GB 单机能装；trigger 高峰 10k QPS 普通 timer queue 能扛。

---

## 9. Follow-up Q&A

### Q1: "如果 server 挂了 30 分钟，会不会有 alarm 不响？"

**A**：**不会**。Client-side OS alarm 是 source of truth for triggering，server 只是 sync 通道。Server 挂了用户只是没法在 30 分钟内同步新 alarm，已设的本地照响。

### Q2: "用户在两台手机同时改同 alarm 不同 time，怎么解决？"

**A**：LWW with HLC timestamp。后写的赢。极少 case，用户可见两端最终一致后改最新值。如果业务要严格冲突检测，加 version field + conflict UI。

### Q3: "用户飞到 NYC，闹钟应该响北京 7AM 还是 NYC 7AM？"

**A**：取决于 alarm 类型：
- "Daily wake-up" → wall-clock + device current TZ → NYC 7AM
- "Meeting reminder, this Friday 9AM ET" → absolute UTC → 仍是 ET 9AM 不变

**默认 wall-clock**（最常见 use case）。

### Q4: "Watch 没网时设 alarm，会响吗？"

**A**：会。watchOS 本地有 AlarmKit，能本地 schedule OS alarm，不依赖 server。下次上网时 sync 到其他 device。

### Q5: "10M users 同时 7AM 响铃，server 端 push 怎么扛？"

**A**：
1. 主要 trigger 是 device 本地 OS alarm，**不需要 server push 来响**
2. Backup push 用 APNs/FCM batched API（一次推 100 个 token）
3. Push 通道本身是 hyperscale 设计的（APNs 每秒能扛 100k+ tokens）

### Q6: "DST 切换那个晚上 (2AM → 3AM)，set 在 2:30AM 的 alarm 怎么办？"

**A**：经典坑。两种行为：
1. 该 alarm **不响**（2:30 不存在）
2. 该 alarm **响在 3:30 等效位置**

iOS 选 #1。**面试时主动澄清这个 edge case** 体现深度。

### Q7: "怎么处理用户的 snooze（推迟 9 分钟）？"

**A**：响铃时 dismiss/snooze 按钮。Snooze → 服务端记录 snooze 操作 → 9 分钟后再触发同 alarm。Multi-device 用 WebSocket 立刻广播 snooze 状态，其他 device 同步推迟。

---

## 10. 易错点 & 加分项

### ❌ 易错点

1. **Server-side trigger 当唯一方案** → 离线设备完全 break
2. **用 UTC offset 存时区** → DST 不对
3. **忽略 effective device 选择逻辑** → 5 个 device 全响吵醒邻居
4. **WebSocket 是唯一 sync 通道** → 离线设备永远不同步
5. **没考虑 DST gap (2-3AM)** → 闹钟在切换日不响
6. **dismiss 不广播** → 多设备 alarm 不同步关

### ✅ 加分项

1. **Hybrid client-primary + server-backup** trigger
2. **HLC** for LWW 解决时钟漂移
3. **IANA TZ name** 而非 UTC offset
4. **Idempotent operations** for offline retry
5. **OS-level wakeup alarm** 省电的本质
6. **CRDT 提一嘴** 即便不用，体现你懂
7. **DST gap edge case** 主动澄清

---

## 11. Cheat Sheet

```
核心决策:
  - Hybrid: client-side OS alarm primary, server backup
  - Client 是 source of truth for triggering
  - Server 是 sync engine + tie-breaker

Sync:
  - WebSocket + Push 唤醒
  - LWW with HLC (or CRDT)
  - Offline-first, pending sync queue

Effective device:
  - User hierarchy + online status
  - Server-side compute, push flag to chosen device

Time zone:
  - Wall-clock + IANA TZ name
  - Auto-handle DST
  - Absolute time for meetings (UTC)

Trigger:
  - Client: OS AlarmManager / UNUserNotificationCenter (±10ms)
  - Server backup: Redis ZSET timer queue + APNs/FCM

数字:
  - 100M users × 3 devices × 5 alarms = 500M alarms
  - Peak trigger: 10k/sec
  - Sync latency: < 5s
  - Storage: 100 GB
```
