## 题目本质

**LC 2408 Design SQL**：实现一个简化版关系数据库的 SQL 操作 —— `insertRow`、`deleteRow`、`selectCell`。**这道 LC 题相对简单**（只考增、删、单元格查询，没有 SELECT/WHERE/JOIN），但 OpenAI 报告这题 4 次提到，可能问的是**它的扩展版**：写 SQL 查询产生指定结果集，含 JOIN / GROUP BY / 窗口函数 / 子查询。

我把两个角度都覆盖。

## Part A：LC 2408 标准题

```
SQL 类:
  __init__(names: list[str], columns: list[int])
    names[i] 是表名，columns[i] 是该表的列数
  insertRow(name, row): 向表追加一行，自动分配 rowId（1-based）
  deleteRow(name, rowId): 标记删除该 row（rowId 不复用）
  selectCell(name, rowId, columnId): 返回单元格值
```

## Python 实现

```python
class SQL:
    def __init__(self, names: list[str], columns: list[int]):
        # name -> dict of rowId -> list (values)
        self._tables: dict[str, dict[int, list[str]]] = {n: {} for n in names}
        # name -> next rowId
        self._next_id: dict[str, int] = {n: 1 for n in names}

    def insertRow(self, name: str, row: list[str]) -> None:
        rid = self._next_id[name]
        self._tables[name][rid] = row
        self._next_id[name] += 1

    def deleteRow(self, name: str, rowId: int) -> None:
        self._tables[name].pop(rowId, None)

    def selectCell(self, name: str, rowId: int, columnId: int) -> str:
        row = self._tables[name].get(rowId)
        if row is None:
            return ""  # 或抛错
        return row[columnId - 1]   # 1-based
```

**复杂度**：所有操作 O(1)（dict get/set）。

**关键点**：
- rowId 自增不复用 —— 不能用 list（删除后 idx 错位）；用 dict by rowId
- 删了的 rowId 之后查会返回 None / ""
- columnId 1-based

## Part B：扩展 - 真 SQL Query 设计

OpenAI 报告里描述：

> "Given one or more relational tables and a target result set, write a SQL query... typically requiring joins, grouping/aggregation, conditional logic, and often window functions for per-group ordering or selection."

这变成了一道 **SQL 写题**，类似 LeetCode SQL 50。考的是你能不能 deconstruct 需求并写正确 SQL。

### 写 SQL 的通用框架

1. **理解目标 schema**：先把 expected output 的列名 + 几行 sample 看清
2. **确定主表**：从哪张表"开始"join
3. **逐列倒推**：每个 output 列来自哪张表，哪个聚合
4. **加 WHERE / GROUP BY / ORDER BY**

### 典型范型 1：Top-N per group（窗口函数必用）

> "为每个部门找薪水最高的 3 个人"

```sql
SELECT department, name, salary
FROM (
    SELECT
        department,
        name,
        salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rn
    FROM employees
) t
WHERE rn <= 3;
```

关键：`ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` 在每组内按规则排序打号；外层 WHERE 取前 N。

### 典型范型 2：连续/累计

> "每个用户的最长连续登录天数"

```sql
WITH date_rn AS (
    SELECT
        user_id,
        login_date,
        DATE_SUB(login_date, INTERVAL ROW_NUMBER() OVER (
            PARTITION BY user_id ORDER BY login_date
        ) DAY) AS grp
    FROM logins
)
SELECT user_id, MAX(consec) AS longest_streak
FROM (
    SELECT user_id, grp, COUNT(*) AS consec
    FROM date_rn
    GROUP BY user_id, grp
) g
GROUP BY user_id;
```

**Trick**：连续日期减去其在用户内的 row_number 得到的 group key 对**同一连续段**相同。

### 典型范型 3：自 JOIN（找前一行 / 同事关系）

> "找出每个员工的 manager 名字"

```sql
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;
```

### 典型范型 4：聚合 + HAVING 过滤组

> "找出有超过 5 个员工的部门"

```sql
SELECT department, COUNT(*) AS cnt
FROM employees
GROUP BY department
HAVING COUNT(*) > 5;
```

### 典型范型 5：Pivot

> "把行式数据 (year, metric, value) 透视成列"

```sql
SELECT year,
       SUM(CASE WHEN metric = 'revenue' THEN value END) AS revenue,
       SUM(CASE WHEN metric = 'cost' THEN value END) AS cost
FROM data
GROUP BY year;
```

## 写 SQL 题的检查清单

| 检查点 | 错过的常见后果 |
|---|---|
| NULL 处理 | `WHERE col != 'X'` 会过滤 NULL；用 `IS NOT NULL` 显式 |
| Distinct vs not | `COUNT(*)` vs `COUNT(DISTINCT x)` 完全不同 |
| Group by 列匹配 | SELECT 非聚合列必须在 GROUP BY 里 |
| 窗口函数 vs 聚合 | `MAX(x) OVER ()` 跟 `MAX(x) GROUP BY ...` 行为不同 |
| 自 JOIN 别名 | `FROM emp e1 JOIN emp e2` 必须用 e1/e2 区分 |
| INNER vs LEFT | 期待 outer 时用了 inner 会漏行 |
| ORDER BY 在 UNION | ORDER BY 只能在最外层 |

## 易错点

> [!pitfall]
> ❌ LC 2408 用 list 存 rows —— 删除后 rowId 失效；
> ❌ SQL 查询直接 SELECT TOP 3 期待 per-group —— 实际是 global top 3；必须窗口函数；
> ❌ NULL 比较用 `=` —— NULL 不等于任何值，包括 NULL 自己；
> ❌ JOIN 没有 ON 条件 —— 笛卡尔积，几行变几亿；
> ❌ GROUP BY 写漏列 —— MySQL 早期会随便返回某行值，严格模式直接报错。

> [!key]
> SQL 题不是考你"记不记得语法"，是考**你能不能把需求拆解成 SQL 算子序列**。窗口函数（ROW_NUMBER / RANK / LAG / LEAD / SUM OVER）是中级 SQL 必杀技 —— 80% 的"per-group X" 都靠它。

> [!followup]
> "如何 explain query plan？" → 加 EXPLAIN 看 join 顺序、用了哪个索引；"如何防止 N+1 query？" → 用 JOIN 而非循环单查；"如何处理 1B 行表？" → 索引设计 + 分区 + materialized view 提前聚合。
