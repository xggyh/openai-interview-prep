## 题目本质

设计 **Smart Alarm System**：用户 set alarm（time + 设备 + repeat），到点触发：声音 / 通知 / 设备动作（智能家居）。支持 voice ("Alexa set alarm for 7AM")。

## 需求

- 100M users，每用户多个 alarm
- 准确性：< 5 秒精度
- 跨时区 / DST
- 多设备 sync（同 alarm 跨手机 + 智能音箱）

## 整体架构

```ascii
   User device
       │ create / update alarm
       ▼
  ┌──────────────┐
  │ Alarm API    │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Alarm DB     │  Postgres / Spanner
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Scheduler    │  computes next fire times
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Time Wheel   │  min-heap of (fire_at, alarm_id)
  └──────┬───────┘
         │ when due
         ▼
  ┌──────────────────┐
  │ Trigger Worker   │  → device push (FCM / APN)
  └──────┬───────────┘  → smart home (IFTTT / Matter)
         │
         ▼
   Devices ring
```

## 核心组件

### 1. Time wheel / 调度

100M alarms，每秒可能千个 fire。**Min-heap of (next_fire_ts, alarm_id)** 由 worker poll。

或更高效：**hash wheel** —— 把时间分成 buckets (e.g. per-second slot)，alarm 放到 slot。Worker tick 当前 second 取出该 bucket。O(1) per alarm。

### 2. Timezone + DST

Alarm 存 `(time_of_day_local, timezone, recurrence_rule)`。Scheduler 每天 0:00 (UTC) 重算每 user 当天的 alarm UTC fire times，写入 time wheel。

DST transition：scheduler 处理（"7AM local" 在 DST 前后 UTC 差 1 小时）。

### 3. Recurrence

Recurrence rule（RFC 5545 iCalendar 标准）：
- "Daily 7AM"
- "Weekdays 8AM"
- "Every Mon/Wed/Fri 9AM"

Library：python-dateutil rrule。

### 4. Multi-device sync

Alarm 属于 user，不属于 device。User 所有 device 都 subscribe alarm events via push notification。

第一个响应的 device 标记 "dismissed"，其他 device 收到 dismiss event 停 ring。

### 5. Snooze

`dismiss` vs `snooze`：snooze 创建临时 alarm 5 / 10 分钟后。临时 alarm 不写主 DB（in-memory 状态足够）。

### 6. Voice integration

"Alexa set alarm 7AM" → NLU 提取 (time, recurrence, label) → POST /alarms。同样 API path。

### 7. Edge case：离线 device

Device 离线时 push 失败。三种策略：
- Device 端本地 cached alarms：online 时 sync，offline 时本地触发
- Re-push when device online
- Multiple device fallback：手机离线但音箱在线 → 音箱响

### 8. 智能家居动作

Alarm 触发不只是 ring。可配联动：
- "Wake up alarm": ring + lights on (智能灯泡 API) + curtain open
- Matter / Home Assistant 协议

每 alarm 关联 action list。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Scheduler | Hash time wheel | Pure heap：log N |
| Recurrence | RRule (RFC 5545) | Ad-hoc：怪规则难处理 |
| TZ | Re-compute daily | Live compute：fire 时算复杂 |
| Sync | Server-driven event | Device-only：sync 难 |
| Offline | Device cache + sync | 服务器 only：离线失败 |

## 易错点

> [!pitfall]
> ❌ Alarm time 存 UTC 不考虑 TZ → DST 引起 1h 偏；
> ❌ Snooze 写主 DB → 每分钟很多写；
> ❌ Device 离线没本地 cache → alarm 不响；
> ❌ Recurrence 自己实现 → 复杂 case 出 bug，用 rrule；
> ❌ Multi-device 不同步 dismiss → 一个 dismiss 其他还响。

> [!key]
> 三大要点：(1) **Hash time wheel** 处理百万 alarm；(2) **Local TZ + recurrence 拆解到 UTC** 处理 DST；(3) **Device 本地 cache + server sync** 处理离线。

> [!followup]
> "Alarm 触发 voice 助手 reply？" → 加 voice prompt 元数据；"如何处理 dst non-existent time (2:30 AM not occurring)？" → fall back to next valid time；"如何防止系统 outage 时漏 fire？" → ack-based delivery + retry；"实时 share alarm 给家人？" → group alarm + multi-user notifications。
