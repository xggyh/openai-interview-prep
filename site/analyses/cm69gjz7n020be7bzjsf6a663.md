## 题目本质

设计 **Google Docs**：实时多人协作文档编辑。N 用户同时改同 doc，所有 change 自动 sync + 不冲突。

参考 [[cmhi1hhbh05wt08ad2knqdyh2]] (CoderPad) 的协作 framework。Google Docs 是 OT (Operational Transformation) 经典。

## 与 CoderPad 区别

- **Doc 更复杂**：富文本（bold, italic, list, image, table），不只是 char
- **更大规模**：几千 user 同 doc 同 edit (Google Docs comment 上百人)
- **Offline + sync**：网络断后回来要 reconcile

## 核心算法

### OT (Operational Transformation)

经典：Google Wave / Docs。每 op 由 server transform against concurrent ops，保证最终所有 client 看到同结果。

```
op_a (insert "X" at 5)
op_b (insert "Y" at 3, concurrent)
After server transform:
  op_a' = insert "X" at 6 (shifted because b inserted before)
  op_b' = unchanged
```

复杂：转换函数对 each op type pair 需 prove correctness。

### CRDT (Conflict-free Replicated Data Type)

每 char 有 global unique ID (vector clock / lamport)。Operations commutative + idempotent，无需 transform。

CRDT 优势：implementation 简单，offline-friendly。
劣势：metadata overhead，doc 增长 (deleted chars 留 tombstone)。

**Google Docs 用 OT**（历史决定）。**Yjs / Automerge 是现代 CRDT**。

## 整体架构

```ascii
   Client (browser)
       │ WebSocket / long-poll
       ▼
  ┌──────────────┐
  │ Doc Server   │  per-doc session state
  │ (sticky by   │  applies & broadcasts ops
  │ doc_id)      │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Storage      │  doc state + op log
  │ (Spanner)    │
  └──────────────┘
```

## 核心组件

### 1. Doc state

```
Document = sequence of styled segments + comments + revisions
op = insert/delete/style/comment
op log = persisted ordered sequence
```

每 doc 内存里维护 current state + op log。

### 2. Sync protocol

```
Client →[op]→ Server  (with revision number)
Server  → transform op against ops since client's revision
        → apply
        → append to op log
        → return ack with new revision
        → broadcast to other clients
```

### 3. Operational Transformation rules

每种 (op_type, op_type) 组合定义 transform function。例：

```python
def transform(local_op, remote_op):
    # remote_op already applied; local must adjust
    if both insert and local.pos > remote.pos:
        local.pos += len(remote.text)
    if local.delete and remote.delete overlap:
        ...
```

Combinatorial 复杂度高 (rich text 操作多)。

### 4. Cursor / Selection sync

Cursor 不是 op，是 ephemeral state。Server 周期 broadcast 每 user cursor 位置。

### 5. Comments

Comment 关联 anchor (char range)。Range shift as document edits。

### 6. Versioning + revision history

每 op 写 op log → 完整历史。User 可 view "1 hour ago" state by replaying log to that point。

### 7. Offline editing

Client 离线时 edit 本地 op queue → reconnect 时 transform against server intermediate ops → apply。

### 8. 大 doc 优化

10k-page doc 不全 load。Lazy load sections + virtual scroll。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Algorithm | OT (历史) / CRDT (现代) | Locking：blocks user |
| Sync | WebSocket + sticky session | REST polling：高延迟 |
| Storage | Spanner（strong consistency for ops） | Eventual：op 顺序乱 |
| Offline | Op queue + sync on reconnect | Disable offline：UX 差 |

## 易错点

> [!pitfall]
> ❌ Naïve last-write-wins → lost edits；
> ❌ OT transform function bug → divergence；
> ❌ 没 sticky routing → 跨 server op log 乱；
> ❌ Cursor 走 op log → 太多 noise；分开 ephemeral；
> ❌ Comment anchor 不跟随编辑 → comment 偏。

> [!key]
> 三大要点：(1) **OT 或 CRDT** 实时协作；(2) **WebSocket + sticky session**；(3) **Op log 持久 + replay enable versioning + offline**。

> [!followup]
> "如何 prevent 恶意 client 假 ops？" → server authoritative + auth check；"How handle 1000+ concurrent editor？" → ops 减频 (batched + LWW for low-priority changes)；"AI suggestions in doc？" → 单独 layer，suggestion = special op type pending user accept。
