## 0. 在开始之前 — 你需要知道的概念

| 名词 | 一句话解释 | 类比 |
|---|---|---|
| **MapReduce** | Google 提的"map → shuffle → reduce"分布式计算模型 | 分发问题给工人，最后汇总 |
| **Mapper** | 第一阶段的 worker，把 input 切成 (key, value) 对 | 流水线第一步：拆零件 |
| **Reducer** | 第二阶段的 worker，对同 key 的所有 value 做汇总 | 流水线第二步：合并同类 |
| **Shuffle** | Map → Reduce 之间的"数据重新分组"过程 | 工厂里把零件按类别送到对应工人 |
| **Partition** | 一个 reducer 对应一个 partition；按 hash(key) 决定 | "姓 A 的零件给 1 号工人" |
| **Combiner** | Mapper 端的 mini-reducer，减少传输量 | 工人 1 自己先把同类零件合一遍再发 |
| **Spill** | mapper 内存满了把数据 dump 到本地磁盘 | 工人桌子塞满了暂时放到地上 |
| **Skew** | 某个 key 特别多 → 某个 reducer 过载 | 80% 的零件都是型号 A |
| **Push shuffle** | mapper 主动推数据到 reducer | 工厂工人主动送货 |
| **Pull shuffle** | reducer 来拉 | 下游工人去取 |
| **Hadoop / Spark / Tez** | 主流实现框架 | 不同工厂的运营方式 |
| **HDFS** | 分布式文件系统，input 数据在这 | 仓库 |
| **YARN / Mesos** | 资源调度器，分配机器给 mapper / reducer | 工厂调度员 |
| **External sort** | 内存装不下，借助磁盘排序 | 桌面排不下纸张，借助抽屉分组 |
| **Backpressure** | 下游处理不过来，让上游降速 | 流水线下游堵了，前段停一停 |

---

## 1. 题目本质

**MapReduce Shuffler** = 把 N 个 mapper 产生的 (key, value) 对，**按 key 重新分组 + 排序**，分发给 M 个 reducer。

**典型产品**：
- **Hadoop MapReduce** —— 原始实现，pull-based shuffle
- **Spark Shuffle** —— 后继者，shuffle 优化是 Spark 核心论文之一
- **Tez** —— DAG 优化的 MR
- **Google Borg / Flume Java** —— Google 内部 MR
- **Presto / Trino** —— SQL 引擎也用 shuffle

**为什么这是 STAFF 高频题**：

Shuffle 是 MR job 的**性能瓶颈**（典型占 50%+ 时间）。考的是：

1. **Network IO**：N×M 全连接传输，PB 级数据怎么传
2. **Sort**：reducer 拿到的数据要按 key 排序
3. **Memory management**：mapper 内存有限，要 spill 到磁盘
4. **Skew handling**：90% 数据集中在 10% key
5. **Fault tolerance**：worker 挂了怎么 retry
6. **Push vs Pull**：根本架构决策

考 STAFF 关键：**你知道 shuffle 是 MR 的关键瓶颈，而不只是"map → reduce 中间那一步"**。

---

## 2. 需求拆解

### Functional

- N 个 mapper 产生 (k, v) 对
- 按 `partition = hash(k) % M` 分发到 M 个 reducer
- 每个 reducer 收到的数据按 k 排序
- 支持 combiner（mapper 端预聚合）
- 支持 secondary sort（按 (k, v) 排序）

### Non-functional

| 维度 | 目标 |
|---|---|
| **Throughput** | TB/s aggregate shuffle bandwidth |
| **Latency** | shuffle 完成时间 < total job 的 30% |
| **Fault tolerance** | 任一 mapper/reducer 挂可 retry |
| **Scale** | 10k mappers × 10k reducers (Google 级) |
| **Memory** | 单 mapper 内存 ≤ 4GB |
| **Skew** | 单 partition 大小不超过 average 10× |

---

## 3. 容量估算

假设：
- Input: 100 TB
- 10k mappers (each processes 10 GB)
- 10k reducers
- Shuffle output 同 input = 100 TB

**Per-mapper output**: 10 GB → 跨 10k reducers = 1 MB / reducer / mapper

**Aggregate shuffle traffic**: 100 TB through N×M connections
- N×M = 10k × 10k = 100M connections (impossible in pull-based)
- **必须按 partition 聚合传输**

**Network**: 100 TB / 1 hour = 30 GB/s aggregate → 300 nodes × 100 Gbps = 可行

**Disk IO**: mapper 写 spill 文件，reducer 读 = 2× shuffle data = 200 TB local disk

---

## 4. 高层架构

### Step 1: Naive baseline — In-memory shuffle

```
Mapper M1 → keeps full output in memory → 直接 push to reducers
```

**问题**：100 TB / 10k mappers = 10 GB / mapper，**内存装不下** → 必须 spill。

### Step 2: Disk-based shuffle (Hadoop MR 经典)

```
Mapper produces output → 写本地 disk (按 partition 分文件)
Reducer pulls each mapper's partition file
```

**Mapper side**:
```
output_buf = [] (in memory, 内存 ≤ 100 MB)
on (k, v):
    output_buf.append((partition(k), k, v))
    if buf full:
        sort by (partition, k)
        write to spill file (one file per spill)
        clear buf

at mapper end:
    merge all spill files into one final file
    contains 10k partitions, each sorted by k
```

**Reducer side**:
```
for each mapper m:
    HTTP GET m's partition_R file
    append to local buffer
merge-sort all chunks by k
call reduce(k, [v1, v2, ...]) for each k
```

### Step 3: Combiner 减少 shuffle traffic

**Idea**：mapper 端做"局部 reduce"，减少传输。

```python
# Mapper output before combiner
("the", 1), ("the", 1), ("the", 1), ("cat", 1)

# After combiner
("the", 3), ("cat", 1)
```

**减少 traffic 5-100×**（看 reduce function 的可结合性）。

**条件**：reduce 操作必须 commutative + associative（sum、max、count OK；avg、median 不 OK 直接 combine）。

### Step 4: Push-based shuffle (Spark / Magnet)

```
Hadoop pull: reducer 主动 fetch from N mappers (慢)
Magnet push: mapper 主动 push to push-merger → reducer 一次拉一个 merged file
```

**push-merger 角色**：聚合多 mapper 的同 partition 数据，写一个 merged file → reducer 只 fetch 一次。

**优点**：
- N×M HTTP fetch → N + M
- random IO → sequential IO
- 减少 reducer 等待时间

**缺点**：
- 引入额外 service
- merger 自己会成瓶颈

### Step 5: Skew Handling

**问题**：某个 key 占 80% 数据 → 1 个 reducer 过载，其他闲。

**解法**：

1. **Salting**: 把 hot key 拆 `key_v1, key_v2, ..., key_v10`，分散到 10 个 reducer。reduce 完再 final merge。
2. **Sampling + custom partition**: 跑前先采样 detect skew，hot key 单独 partition
3. **Adaptive splitting** (Tez): 运行期 detect skew，动态拆 partition

### Step 6: Fault Tolerance

**Mapper 挂了**: 重跑那个 mapper。Input 是 HDFS immutable file，re-read OK。

**Reducer 挂了**: 重跑 reducer。重新从 N mappers fetch 自己的 partition。**前提**: mapper 的 output 还在 local disk。

**Mapper local disk 挂了**: 那个 mapper 的所有 output 丢，**所有依赖它的 reducer 必须重 trigger 那个 mapper**（Spark 的 lineage 机制）。

---

## 5. 组件深挖

### Deep Dive 1: Sort — External Merge Sort

Mapper 内存 100 MB，要 sort 10 GB 数据 → external sort。

**算法**：
1. 读 100 MB → in-memory quicksort → write spill file (sorted)
2. 重复，得 100 个 spill files
3. K-way merge：100 个 file 各开一个 reader，min-heap 选最小 → 写 final file
4. K-way merge 是 O(N log K)，N=数据量，K=spill 数

**优化**：merge 阶段先合并到 √N 个中间文件，再合并到 1 个（two-pass），减少 random IO。

### Deep Dive 2: Mapper Output Format

每个 mapper 产生一个 final file + index：

```
file: [partition_0_data] [partition_1_data] ... [partition_M-1_data]
index: [partition_0_offset, partition_0_size]
       [partition_1_offset, partition_1_size]
       ...
```

Reducer fetch partition_R → 用 index 找 offset → range read 该范围。

**好处**：N mappers × M reducers = N×M fetches, but each is a sequential read → 比 N×M files (Hadoop MR1) 好 100×。

### Deep Dive 3: Network Optimization

**问题**：10k mappers × 10k reducers = 100M HTTP connections in worst case。

**优化层次**：

1. **Connection pooling**：每对 (mapper-host, reducer-host) 维护一个 keep-alive HTTP/2 connection，复用
2. **Batched fetch**：reducer 一次从一个 host 拉所有 partition (合并多个 mapper)
3. **Push-based with merger** (Magnet)：跳过这个 N×M 问题
4. **Compression**：snappy / lz4 mapper output (4-10× 压缩)

### Deep Dive 4: Memory Management

Mapper 内存分配：

```
| input read buffer (10%) | output buffer (60%) | sort space (20%) | overhead (10%) |
                                                ↑ JVM heap or off-heap
```

**Off-heap 优化**：output buffer 用 `ByteBuffer.allocateDirect()` (Java) 或 `mmap`，避免 GC pause。

**Spill threshold**：output buffer 占用 80% 时 spill，避免 trigger full GC。

### Deep Dive 5: Skew Detection + Mitigation

**Detect**:
- Sample input keys (e.g., reservoir sampling 1% of records)
- Build histogram of partition sizes
- 任何 partition > avg × 10 → skew

**Mitigate**:

```python
def handle_skew(key, hot_keys):
    if key in hot_keys:
        salt = random.randint(0, 9)
        emit_key = f"{key}__{salt}"
    else:
        emit_key = key
    return partition(emit_key)
```

Reducer 处理 `key__0` ... `key__9` → 输出 10 个 partial results → second reduce stage 合 final。

**Spark adaptive**: runtime detect skew → split single partition into N → schedule multiple reducer tasks。

### Deep Dive 6: Push vs Pull

| Aspect | Pull (Hadoop) | Push (Magnet) |
|---|---|---|
| Connections | N×M | N + M |
| Random IO | many small reads | sequential reads |
| Reducer latency | wait for slowest mapper | mostly already merged |
| Implementation | simpler | needs push-merger service |
| Failure | re-fetch from mapper | merger has data, simpler |

**STAFF 答**：选 push-based。push-merger 跑在每个 cluster node，merge 同 partition data。Reducer 只 fetch merged。Spark 3.1+ 默认是 push shuffle。

### Deep Dive 7: Combiner Trade-off

**Combiner 提速 5-100×**，但有坑：

- **非 commutative**：count、sum OK；median 不行
- **CPU 开销**：mapper 自己 reduce 占 CPU，如果 reduce 廉价（如 count），net 加速
- **Memory**：combine 需要额外 hash map 存中间结果

**实战**：写 word count 必加 combiner；写复杂 aggregation 想清楚再加。

---

## 6. 45 分钟节奏

| 时间 | 阶段 |
|---|---|
| 0-5min | 澄清 + NFR（强调 shuffle 是 bottleneck） |
| 5-10min | 容量估算（10k×10k mappers/reducers, 100 TB data） |
| 10-20min | 高层架构 step 1→6（spill / combiner / push） |
| 20-35min | Deep dives: sort / network / memory / skew |
| 35-45min | fault tolerance / push vs pull |

---

## 7. 样板讲解稿

> MapReduce Shuffler 是 MR job 50%+ 时间花费的地方。我会讲 Hadoop pull-based shuffle，演进到 Spark/Magnet push-based。
>
> **演进**：
> 1. 单 mapper 内存写不下 10GB → **disk-based shuffle**：mapper 写 sorted spill file per partition
> 2. N×M 个 small file fetch 太慢 → mapper 写 **single file + index**：N×M connections each is sequential read
> 3. 数据量大 → **combiner** 减少 traffic 5-100×（前提：commutative + associative）
> 4. N×M 还是太多 connections → **push-based shuffle**（Magnet）：mapper push to push-merger，merger 合并同 partition，reducer 一次拉一个
> 5. Skew 单 reducer 过载 → **salt key**（拆 hot key into key_v1..v10）+ runtime adaptive split
>
> **Deep dives**：
> - External sort: in-memory quicksort + k-way merge
> - Network: connection pooling + HTTP/2 + compression + push-merger
> - Memory: off-heap + spill threshold
> - Skew: sampling + salt + adaptive split
> - Fault: mapper retry (input immutable) + lineage for cascade re-trigger
>
> Scale: 10k mappers × 10k reducers, 100 TB shuffle data, 30 GB/s aggregate network.

---

## 8. Follow-up Q&A

### Q1: "如果一个 mapper 慢（straggler），怎么办？"

**A**：**Speculative execution**。MR framework detect 慢 mapper (比 median 慢 1.5×) → 重跑同 task 在另一台机器，谁先完用谁。Hadoop / Spark 都有。

### Q2: "Reducer 等所有 mapper 都完成才能开始吗？"

**A**：**不一定**。Hadoop 默认 reducer 在 5% mappers 完成时就开始 fetch（partial shuffle），但 reduce phase 必须等所有 mapper done（因为按 key sort 需要完整数据）。Push-based: reducer 等 merger 完成 indicator。

### Q3: "Combine 一定能加速吗？"

**A**：不一定。如果数据 distribution 平均（每 key 只有 1 个 value），combine 是 no-op + 浪费 CPU。**只在 reduce 是 sum/count/max 这种 aggregation 时显著加速**。

### Q4: "Mapper local disk 挂了，10 个 reducer 都依赖它的数据，怎么办？"

**A**：触发 **cascade re-trigger**：重跑那个 mapper（Spark 的 lineage 机制），然后 10 个 reducer 重新 fetch。代价高，所以 mapper output 通常用 **replication** (Spark `spark.shuffle.replication=2`) 或 **shuffle service**（独立 storage layer, e.g., Apache Uniffle）。

### Q5: "10k reducers 都打到一个 mapper host fetch，host 网络爆了。"

**A**：**Throttling**：mapper host 限制并发 outgoing fetch (e.g., 64)。Reducer 实现 retry with backoff。Push-based: merger 提前打散 traffic（merger 跑在多 host）。

### Q6: "怎么测试 shuffle 性能？"

**A**：
1. **Sort benchmark**：跑 TeraSort，衡量 1TB 排序时间
2. **Skew test**：人工注入 hot key，看是否 detect + mitigate
3. **Failure injection**：kill mapper / reducer mid-job
4. **Network bisection bandwidth**：iperf3 全连接打满

### Q7: "Spark 比 Hadoop MR 快 10×，shuffle 上有什么改进？"

**A**：
1. **In-memory shuffle**：尽量在内存而非 disk
2. **Push-based shuffle (Magnet)**：减少 N×M connections
3. **DAG optimization**：避免不必要的 shuffle
4. **Predicate pushdown**：filter 提前到 mapper 减少 shuffle 量
5. **Adaptive query execution (AQE)**：runtime adjust partitions

---

## 9. 易错点 & 加分项

### ❌ 易错点

1. **忽略 skew** → 答案不完整，STAFF 必扣分
2. **以为 mapper output 全在内存** → 暴露你没真做过大数据
3. **N×M HTTP requests 当默认** → 没意识到 connection 爆炸
4. **Combiner 当作必选** → 没说前提条件
5. **不分 push vs pull** → 不知道 industry 演进
6. **Fault tolerance 只说 retry** → 没说 mapper output 丢的 cascade
7. **没考虑 sort 用 external merge** → 暴露算法基础

### ✅ 加分项

1. **Push-based shuffle (Magnet)**：体现你跟得上 industry
2. **Salt key for skew** 代码级写出来
3. **External k-way merge sort** 讲细节
4. **Off-heap memory** 避 GC pause
5. **Speculative execution** for stragglers
6. **Compression** (snappy/lz4) 量化压缩比
7. **Shuffle service** (Apache Uniffle / Magnet) 知道前沿

> [!key] STAFF vs SENIOR：SENIOR 说"shuffle 把 mapper output 传给 reducer"；STAFF 说"Hadoop pull 是 N×M，Spark Magnet push-based 减到 N+M，对吞吐 5-10× 提升"。

---

## 10. Cheat Sheet

```
架构 (Hadoop MR1 → Magnet):
  1. Mapper output 写本地 sorted file per partition
  2. Mapper 内存满了 spill → external k-way merge
  3. Combiner 减少 traffic 5-100×
  4. Push-based shuffle 减少 N×M connection 爆炸
  5. Salt key + adaptive split 应对 skew
  6. Speculative execution 处理 straggler

Sort:
  - In-memory quicksort + k-way merge
  - Two-pass: 100 spill → √N intermediate → 1 final

Network:
  - HTTP/2 keep-alive
  - Connection pool
  - snappy/lz4 compression (4-10×)
  - Push-merger 跑在每个 host

Memory:
  - 100MB output buffer
  - Off-heap ByteBuffer
  - 80% threshold for spill

Skew:
  - Sample 1% records → histogram
  - Salt hot key: key__0..9
  - Adaptive partition split

Fault Tolerance:
  - Mapper retry (input immutable)
  - Cascade re-trigger if local disk lost
  - Shuffle service (Uniffle / Magnet) for durability

数字:
  - 10k mappers × 10k reducers
  - 100 TB shuffle data
  - 30 GB/s aggregate network
  - 1 TB sort target time (TeraSort)
```
