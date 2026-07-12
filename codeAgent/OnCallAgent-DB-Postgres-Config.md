# OnCallAgent PostgreSQL DB 配置说明

## 1. 当前 DB 设计

DB 查询现在通过 Driver Adapter 层执行：

```text
DBInvestigationAgent
  -> DBQueryTool
      -> DB Driver Adapter
          -> SQLiteDriver / PostgresDriver
```

业务层只关心 SQL 模板和参数，不直接关心底层数据库驱动。

当前支持：

- `sqlite`
- `postgres`

Postgres driver 默认优先使用：

```text
psycopg
```

如果没有安装 `psycopg`，会尝试：

```text
psycopg2
```

## 2. 安装 PostgreSQL 驱动

推荐安装 psycopg v3：

```bash
pip install "psycopg[binary]"
```

如果你们环境已经使用 psycopg2：

```bash
pip install psycopg2-binary
```

生产环境如果公司有自己的封装驱动，可以后续在 `app/db/drivers/postgres_driver.py` 里做适配，或者通过 `driver_module` 指定模块名。

## 3. 配置文件

配置文件：

```text
configs/db.json
```

当前默认还是：

```json
"active_profile": "local-demo"
```

所以本地不会直接连 Postgres。

如果要切换到 pirun Postgres：

```json
"active_profile": "pirun-postgres"
```

或者用环境变量：

```powershell
$env:DB_PROFILE="pirun-postgres"
python -m app.main
```

## 4. Postgres Profile 示例

```json
{
  "driver": "postgres",
  "host": "${MES_PIRUN_DB_HOST}",
  "port": 5432,
  "database": "${MES_PIRUN_DB_NAME}",
  "username": "${MES_PIRUN_DB_USER}",
  "password": "${MES_PIRUN_DB_PASSWORD}",
  "connect_timeout": 10,
  "sslmode": "prefer",
  "application_name": "OnCallAgent-pirun",
  "autocommit": true
}
```

注意：`${...}` 会从环境变量读取。

例如：

```powershell
$env:MES_PIRUN_DB_HOST="10.1.2.3"
$env:MES_PIRUN_DB_NAME="mes_pirun"
$env:MES_PIRUN_DB_USER="readonly_user"
$env:MES_PIRUN_DB_PASSWORD="your-password"
$env:DB_PROFILE="pirun-postgres"
python -m app.main
```

## 5. SQL 参数格式

OnCallAgent 的 SQL 模板统一使用 named 参数：

```sql
select *
from lot_history
where lot_id = :lot_id
```

Postgres 驱动会自动转换成 psycopg 使用的格式：

```sql
where lot_id = %(lot_id)s
```

所以 `configs/db.json` 里的 SQL 模板不用因为 Postgres 改写参数占位符。

## 6. 只读账号建议

建议给 OnCallAgent 使用只读账号。

最小权限：

- 可以查询 LotHistory
- 可以查询 lot 当前 module
- 可以查询 rule execution
- 不允许 update/delete/insert

当前 DBQueryTool 主要用于查询，但账号权限最好也从数据库侧限制住。

## 7. 公司自研驱动怎么接

如果你们公司驱动只是基于 psycopg 封装了一层，有两种接法。

### 方式一：保持当前 PostgresDriver

如果公司驱动仍兼容：

```python
connect(**kwargs)
cursor()
cursor.execute(sql, params)
cursor.description
cursor.fetchall()
close()
```

那只需要在 profile 中加：

```json
"driver_module": "your_company_postgres_driver"
```

PostgresDriver 会 import 这个模块，并调用它的 `connect(**kwargs)`。

### 方式二：新增 Company Driver

如果公司驱动连接方式完全不同，建议新增：

```text
app/db/drivers/company_postgres_driver.py
```

然后在：

```text
app/db/drivers/factory.py
```

里增加：

```python
if driver == "company_postgres":
    return CompanyPostgresDriver(profile)
```

这样不会污染官方 PostgresDriver。

## 8. 明天到公司需要确认的信息

需要确认：

- DB host / port
- database name
- username / password
- 是否需要 SSL，`sslmode` 是 `prefer`、`require` 还是关闭
- 是否需要额外连接参数，比如 schema、search_path
- 公司驱动模块名
- 公司驱动是否兼容 `connect(**kwargs)`
- SQL 表名和字段名是否和 `configs/db.json` 示例一致

如果默认 schema 不是目标 schema，可以在 profile 里增加：

```json
"options": "-c search_path=mes_schema"
```

## 9. 常见错误

### 没装驱动

错误：

```text
Postgres driver is not installed. Run: pip install psycopg[binary]
```

处理：

```bash
pip install "psycopg[binary]"
```

### 环境变量没配

如果 `${MES_PIRUN_DB_HOST}` 为空，连接会失败。

检查：

```powershell
echo $env:MES_PIRUN_DB_HOST
echo $env:MES_PIRUN_DB_NAME
echo $env:MES_PIRUN_DB_USER
```

### SQL 字段不一致

如果真实表字段和示例不一致，修改：

```text
configs/db.json -> queries
```

不要改 Python 代码。
