# service 层规约（FastAPI 领域服务）

> **契约查 `docs/tech/`**：接口出入参 → `docs/tech/api/`；表字段 → `docs/tech/data-model/`；
> 模块划分与函数清单 → `docs/tech/backend.md`。本文只写"改 `service/` 代码时要注意什么"。

## 目录职责

```
service/
├── app/
│   ├── core/          config / errors / response / security / ids / pagination / logging / handlers
│   ├── db/            base（命名约定）/ session（引擎与连接池）/ guard（测试库护栏）
│   ├── models/        31 张表，按 6 册分文件，与 docs/tech/data-model/ 一一对应
│   ├── schemas/       对外 JSON 的 Pydantic 模型（camelCase）
│   ├── api/v1/        薄路由：解析 → 鉴权 → 调服务层 → 包装信封
│   ├── services/      业务规则、事务、幂等（R000 起逐步填充）
│   └── llm/           pool（档位链、降级、记账）
├── alembic/           迁移（DDL 的唯一来源）
└── tests/
```

**分层规则**：路由层不写业务判断，服务层不碰 `Request`/`Response`，模型层不写查询方法。
违反这条的典型症状是"同一段规则在两个路由里各写一遍，改一处漏一处"。

## Pre-Development Checklist

动手前逐条确认：

- [ ] **接口契约是否已在 `docs/tech/api/` 写明？** 没写就先写契约（见该文档 §9 的 5 步）。
- [ ] **`user_id` 从哪来？** 只能来自 `Depends(get_current_user)`。**永远不从查询参数或请求体取**。
- [ ] **改模型了吗？** 改了就必须配一条迁移，否则启动时 `alembic check` 会拒绝启动。
- [ ] **新增可空列还是必填列？** 表里已有数据时，必填列必须给 `server_default`，否则迁移直接失败。
- [ ] **这次改动要不要动 `docs/tech/`？** 成为跨需求契约就必须回写。
- [ ] **有没有可以直接复用的现成实现？** 先 `grep`，`app/core/` 里大概率已经有了。

## Quality Check

```
cd service
uv run ruff check .            # 必须 All checks passed
uv run ruff format --check .   # 必须 already formatted
uv run pytest                  # 必须全绿（不需要数据库）
```

离线渲染迁移（不需要数据库，CI 也跑这条）：

```
SUMMER_DATABASE_URL="postgresql+asyncpg://ci:ci@localhost:5432/summer_checkin_test" \
  uv run alembic upgrade head --sql > /tmp/schema.sql
grep -c "CREATE TABLE" /tmp/schema.sql   # 32（31 张业务表 + alembic_version）
grep -c "USING hnsw" /tmp/schema.sql     # 2
grep -c "CREATE EXTENSION" /tmp/schema.sql  # 1
```

## 三条硬规则

### 1. 路由薄、服务层厚

`app/api/v1/*.py` 只做四件事：解析入参、取当前用户、调服务层、`ok()` 包装。
参考 `app/api/v1/system.py` 的 `example()`——它就是"最少该写多少"的样例。

**反例**：在路由里直接 `select(...)` 拼业务条件。R000 的 `/cron/daily` 是**刻意的例外**：
它还没有服务层（R005 才有巡检运行时），且带注释说明了这一点。新增接口不要照抄这个例外。

### 2. `user_id` 只能来自 JWT

```python
@router.get("/checkins")
async def list_checkins(user: Annotated[CurrentUser, Depends(get_current_user)]) -> ...:
    ...where(Checkin.user_id == user.id)   # 而不是请求参数里的 user_id
```

跨用户访问返回 `NOT_FOUND` 而不是 `FORBIDDEN`——`FORBIDDEN` 会泄露"这条数据存在"。
`tests/test_isolation.py` 是这条规则的守卫。

### 3. 响应一律走 `app/core/response.py`

`ok(data)` / `list_ok(items, next_cursor)` / 异常交给 `app/core/handlers.py`。
**不要**在路由里 `JSONResponse({...})` 手写信封——错误码与 `X-Request-Id` 会漏掉。

## 配置

全部来自环境变量，前缀 `SUMMER_`（`app/core/config.py`）。缺必需项**拒绝启动**：

| 必需 | 说明 |
|---|---|
| `SUMMER_DATABASE_URL` | 必须是 `postgresql+asyncpg://`（同步驱动会堵死事件循环，已验证并报错） |
| `SUMMER_JWT_PUBLIC_KEY` | PEM 文本；支持字面量 `\n`（环境变量里换行常被转义） |
| `SUMMER_CRON_SECRET` | `/cron/daily` 的 Bearer |

**为什么不给默认值**：`SUMMER_JWT_PUBLIC_KEY` 一旦有默认值，忘配就会静默变成"无鉴权放行"，
这比启动失败危险得多。

## 迁移纪律

- DDL **只**出现在 `alembic/versions/`。手改数据库会让 `alembic check` 报漂移。
- `CREATE EXTENSION vector`、`vector(1024)` 列、`USING hnsw` 索引三处必须手写——autogenerate 认不出来。
- **改名检测不出来**：autogenerate 会把改名渲染成 `drop_table` + `create_table`，照执行等于删数据。
  改名必须手写 `op.alter_column(..., new_column_name=...)`。
- `compare_server_default` 默认关闭，改默认值不会被发现。
- `downgrade` 前有护栏：库名必须以 `_test` 结尾（`app/db/guard.py`）。
- `alembic.ini` **必须保持纯 ASCII**：alembic 用系统 locale 读它，中文注释在 GBK 环境会
  `UnicodeDecodeError`。注释写进 `env.py` 或迁移文件里。

## 测试约定

- `tests/conftest.py` 在**导入时**用 `os.environ.setdefault` 设好环境变量——
  `Settings` 在模块导入时就会校验，晚了就报 `ValidationError`。
- 共享常量与 token 工具放 `tests/helpers.py`（绝对导入 `from tests.helpers import ...`）。
- `client` fixture 是 **session 级**的：每次新建 app 都会重新验一次公钥，且连不通的端口要等
  系统超时（本机实测每端口约 2 秒）。
- 测试**不需要数据库**：R000 的接口不查库。真库验收见任务 `prd.md` §10 第 8 行。

## 常见错误

| 症状 | 原因 | 怎么做 |
|---|---|---|
| 启动报 `ValidationError`，指向缺失字段 | 环境变量没设，或设在了 `Settings` 实例化之后 | 在导入 app 之前设好（测试里看 `conftest.py`） |
| 线上 404，本地直连端口正常 | 路径漏了 `/api/v1` 前缀，被 nginx 交给 web | 前缀在 `app/api/v1/__init__.py` 统一加 |
| `alembic check` 报漂移，但代码没改 | 表达式索引（如 `desc("created_at")`）反射不回来 | 用普通 btree，Postgres 反向扫描同样快 |
| 中文注释导致 alembic 崩 | `alembic.ini` 被按系统 locale 解码 | `alembic.ini` 只写 ASCII |
| 越权读到别人的数据 | `user_id` 取自请求参数 | 只从 `get_current_user` 取 |
