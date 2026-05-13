## 题目本质

实现一个 **in-memory database**，支持 SQL-like 操作：`INSERT`、`SELECT WHERE`、`ORDER BY`。需要数据结构 + 解析 WHERE 条件 + **inverted index** 加速 lookup。

OpenAI 真实报告 Mid-Staff 级，11 人。考点：**class 设计 + 简单 query 解析器 + 索引**。

## 题目语义

```python
db = MiniDB()
db.create_table("users", schema=["id", "name", "age", "city"])
db.insert("users", {"id": 1, "name": "Alice", "age": 30, "city": "SF"})
db.insert("users", {"id": 2, "name": "Bob",   "age": 25, "city": "NYC"})
db.insert("users", {"id": 3, "name": "Carol", "age": 30, "city": "SF"})

db.select("users",
    where={"city": "SF", "age": {"$gte": 30}},
    order_by=("age", "DESC"))
# → [{"id":1,"name":"Alice",...}, {"id":3,"name":"Carol",...}]
```

## 解题思路

1. 表：`dict[table_name] -> Table`
2. 每个 Table：行用 list，自增 row_id；每列可选建索引
3. 索引：`column -> value -> set[row_id]`（倒排）
4. SELECT：从索引交集出候选 row_id → 过滤剩余条件 → 排序
5. 简化版只支持等值 WHERE 用索引；范围 WHERE 退化为扫描

## Python 实现

```python
from collections import defaultdict
from typing import Any
import operator

class Table:
    def __init__(self, schema: list[str]):
        self.schema = schema
        self.rows: list[dict] = []           # row_id = idx
        # column -> value -> set of row_ids
        self.index: dict[str, dict[Any, set[int]]] = {col: defaultdict(set) for col in schema}

    def insert(self, row: dict):
        # 校验 schema
        for col in self.schema:
            if col not in row:
                raise ValueError(f"missing col {col}")
        rid = len(self.rows)
        self.rows.append(row.copy())
        for col, val in row.items():
            if col in self.index:
                self.index[col][val].add(rid)
        return rid

    def _match_predicate(self, row: dict, col: str, pred) -> bool:
        if not isinstance(pred, dict):
            return row.get(col) == pred
        for op_name, target in pred.items():
            op = {
                '$eq':  operator.eq,
                '$ne':  operator.ne,
                '$gt':  operator.gt,
                '$gte': operator.ge,
                '$lt':  operator.lt,
                '$lte': operator.le,
                '$in':  lambda a, b: a in b,
            }[op_name]
            if not op(row.get(col), target):
                return False
        return True

    def select(self, where: dict = None, order_by: tuple = None,
               limit: int | None = None) -> list[dict]:
        where = where or {}
        # 1. 找到所有等值条件 → 走索引
        eq_filters = {c: v for c, v in where.items()
                      if not isinstance(v, dict)}
        other_filters = {c: v for c, v in where.items()
                         if isinstance(v, dict)}

        # 2. 用索引交集出候选
        if eq_filters:
            candidate_sets = [self.index[c].get(v, set()) for c, v in eq_filters.items()]
            candidates = set.intersection(*candidate_sets) if candidate_sets else set(range(len(self.rows)))
        else:
            candidates = set(range(len(self.rows)))

        # 3. 应用范围 / 不等条件
        rows = []
        for rid in candidates:
            row = self.rows[rid]
            ok = all(self._match_predicate(row, c, p) for c, p in other_filters.items())
            if ok:
                rows.append(row)

        # 4. ORDER BY
        if order_by:
            col, direction = order_by
            rows.sort(key=lambda r: r.get(col), reverse=(direction == "DESC"))

        # 5. LIMIT
        if limit is not None:
            rows = rows[:limit]
        return rows

class MiniDB:
    def __init__(self):
        self.tables: dict[str, Table] = {}

    def create_table(self, name: str, schema: list[str]):
        if name in self.tables:
            raise ValueError("table exists")
        self.tables[name] = Table(schema)

    def insert(self, table: str, row: dict):
        return self.tables[table].insert(row)

    def select(self, table: str, **kwargs):
        return self.tables[table].select(**kwargs)
```

## 复杂度

| 操作 | 有索引 | 无索引 |
|---|---|---|
| INSERT | O(C)，C = 列数 | O(C) |
| SELECT 等值 | O(K)，K = 命中行数 | O(N) |
| SELECT 范围 | O(M)，M = 候选行（先索引粗筛） | O(N) |
| ORDER BY | O(K log K) | O(N log N) |

## 关键设计点

### 1. 倒排索引（Inverted Index）

每列一个 dict：`value -> set[row_id]`。等值查询直接命中；多列 AND 等值用 `set.intersection`。

```python
# city='SF' AND age=30 的查询
ids_sf = self.index['city']['SF']      # {0, 2}
ids_30 = self.index['age'][30]         # {0, 2}
ids_sf & ids_30                        # {0, 2}
```

### 2. 范围查询

简单实现：先用等值索引粗筛，再扫描结果。生产级：用 **B-tree / skip list** 为列建有序索引（`SortedList` from sortedcontainers），支持 `range query` 在 O(log N + K)。

### 3. UPDATE / DELETE

要维护索引：删除时从 `index[col][old_val]` 移除 row_id；插入时加入新值。row 用 dict 自增 id 而非物理位置，删除不需要重排（标记 tombstone）。

### 4. 多个条件的成本估算（query planner 雏形）

如果 `city='SF'` 命中 100 行，`age=30` 命中 1 行，先用 age 索引开始，能避免扫 100 行的 SF。生产 DB 用 column statistics 决定 plan。

## 取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| 存储 | 行式 list[dict] | 简单。列式（dict[col][rid]）查询友好但插入复杂 |
| 索引 | 每列默认建索引 | 简化；生产应允许 user 选择 |
| 并发 | 单线程 | 加 Lock 简单但题面没要求 |
| WHERE 解析 | dict 风格（$gt $lt） | 比解析 SQL string 简单且清晰 |

## 扩展（如果面试官追问）

- **多表 JOIN**：先实现 nested loop join，O(N×M)；优化用 hash join（小表建 hash）
- **GROUP BY + 聚合**：分组用 dict，对每组算 sum/avg
- **持久化**：把 rows + index 序列化到文件（pickle / JSON）
- **事务**：BEGIN / COMMIT / ROLLBACK，写一份 WAL（write-ahead log）

> [!key]
> 这题是**OOP 设计 + 数据结构选择**的展示。先把 INSERT / SELECT 主路径写干净，倒排索引是核心亮点。WHERE 用 dict 风格比解析 SQL string 节省时间。

> [!pitfall]
> ❌ 用嵌套循环扫每个 row 检查 WHERE —— O(N×C) 慢但勉强对；面试官会问"如何加速"，必须答上索引；
> ❌ 索引存储用 `list[(value, rid)]` 而不是 dict —— 等值查询变 O(N)；
> ❌ INSERT 不更新索引 —— 写入后查不到；
> ❌ ORDER BY 完不 LIMIT，写了 LIMIT 但没在 sort 之后 —— 先 sort 再 limit。

> [!followup]
> "如何支持 SELECT DISTINCT？" 用 set 去重。"如何支持 OR 查询？" `set.union`。"如果数据太大放不下内存？" → 引入 mmap 或简单 LSM tree。"并发写入？" 每表 RWLock 或乐观锁（CAS on rid）。
