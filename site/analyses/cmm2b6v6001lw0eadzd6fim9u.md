## 题目本质

设计 **MapReduce Shuffler**：MapReduce 框架中 map output → reducer input 的 shuffle 阶段。把 N mappers 的 keyed output 按 key partition + sort + transport 给 M reducers。

经典 distributed systems 题。

## 整体流程

```
Map output: list of (key, value)
   │
   │ partition by hash(key) % R
   ▼
Per-mapper R buckets (one per reducer)
   │
   │ sort each bucket by key
   ▼
Local disk spill (intermediate file)
   │
   │ reducer pulls relevant bucket from each mapper
   ▼
Reducer input: merged sorted (key, value list)
   │
   │ reduce function
   ▼
Final output
```

## 核心组件

### 1. Partitioner

`partition(key) = hash(key) % R`。同 key 永远去同 reducer。

可自定义（如 by date range）实现 locality。

### 2. Per-mapper local sort + spill

Map output 累积到内存 buffer。达 spill threshold → sort + write disk。Sorting 用 in-place quicksort（per partition）。

最后 mapper 完成时多个 spill file 需要 merge。

### 3. Sort vs hash shuffle

**Sort shuffle (Hadoop)**：mapper output 排序 + reducer 接 merge sorted streams。优势：sorted input 让 reducer 同 key 自然 group。劣势：sort 开销大。

**Hash shuffle**：不 sort，按 partition 切分写文件。Reducer 自己 group by key。简单但 reducer 端工作多。

Spark 早期用 hash，后改 sort（更可扩展）。

### 4. Shuffle service / pull

Reducer 主动 pull from mappers。问题：mapper finish 后 reducer 没拉就挂会丢数据。

解决：
- Mapper output 写本地 disk + commit 到 external shuffle service（Spark 用此）
- Mapper 进程退出后数据还在
- Reducer 任意时刻 pull

External shuffle service = 中心 daemon per worker box，专门处理 shuffle data 请求。

### 5. Bandwidth optimization

- **Compression**：spill file 用 Snappy / LZ4 压缩 ~2-3x
- **Combiner**：在 mapper 本地先做 partial reduce（如 word count 在 map 端就 sum 同 word），减少 shuffle data
- **Map-side aggregation**：tree reduce

### 6. Failure handling

- Mapper task 重试：原 output 失效，重新 spill
- Reducer fetch fail：retry from same mapper or fallback to another replica
- Reducer crash：重启 + re-fetch all mapper output（expensive，所以 mapper 数据要 persist long）

### 7. Skew handling

Some key 极不均衡（如 90% data 在 key="" 上）→ 一个 reducer overload。

Mitigation:
- **Salting key**：append random suffix → split to N reducers → final aggregate
- **Sampling**：先 sample 找 heavy keys → 给它们专 reducer

### 8. Memory management

Reducer pulling 多 mapper data 不能全装内存。**External sort + merge**：buffer 一定量 → spill → merge K-way 流式。

## 取舍

| 决策 | 选择 | 替代 |
|---|---|---|
| Shuffle type | Sort shuffle | Hash：可扩展性差 |
| Storage | Local disk + external service | Memory：OOM |
| Compression | Snappy/LZ4 | None：网络爆 |
| Combiner | Yes when associative | No：浪费 |
| Skew | Salting + sampling | None：straggler |

## 易错点

> [!pitfall]
> ❌ 不 partition by hash → reducer 收到非聚合 key；
> ❌ 不 sort → reducer 同 key 不连续；
> ❌ Mapper 进程退出 data 没 persist → reducer fetch 失败；
> ❌ 不处理 skew → 1 个 reducer 跑几小时；
> ❌ Reducer 全装内存 → OOM。

> [!key]
> 三大要点：(1) **Partition (hash) + sort** by key；(2) **External shuffle service** decoupling mapper / reducer lifecycle；(3) **Skew + memory management** 工程难点。

> [!followup]
> "Spark vs Hadoop shuffle 区别？" → Spark 早期 hash → sort (Tungsten)；in-memory vs disk priority；"如何 streaming shuffle？" → 类似 Flink 的 pipelined exchange，无 spill；"GPU shuffle？" → RAPIDS / GPU MR，shuffle 仍是 disk bottleneck。
