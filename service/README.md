# service（FastAPI 领域服务）

Summer Checkin 的领域服务：**业务数据与业务接口的唯一所有者**。web 只做页面与登录，
所有业务数据都经 `/api/v1/*` 从这里出去。

## 本地怎么跑

```bash
python -m venv .venv                       # Python 3.12；Windows: py -3.12 -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -i https://mirrors.aliyun.com/pypi/simple/
cp ../.env.example .env                    # 填入 SUMMER_DATABASE_URL 等
alembic upgrade head                       # 建表（31 张）
uvicorn app.main:app --reload              # 起服务
```

依赖只声明在 `requirements.txt`（运行时）/ `requirements-dev.txt`（含 ruff、pytest），
用普通 venv + pip 安装，所以 `-i` 可以直接指定镜像源；`pyproject.toml` 只留工具配置。
容器里同样是 venv（`/app/.venv`），见 `infra/service.Dockerfile`。

校验命令：

```bash
ruff check . && ruff format --check .
pytest                                     # 93 passed
alembic check                              # 模型与库无漂移
```

## 目录

| 路径 | 职责 |
|---|---|
| `app/core/` | 配置、鉴权、统一响应与错误码、日志、id、分页 |
| `app/db/` | 声明基类与命名约定、async 会话与事务边界 |
| `app/models/` | 31 张表的 SQLAlchemy 模型（按域分文件）——**schema 的唯一声明处** |
| `app/api/v1/` | 薄路由：解析 → 校验 → 鉴权 → 调服务层 → 包装响应 |
| `app/services/` | 业务规则、事务、幂等、审计 |
| `app/llm/` | 模型池（档位链、失败降级、限流冷却、记账） |
| `alembic/` | 唯一的迁移链——DDL 只允许出现在这里 |
| `tests/` | 单测 |

## 迁移纪律

1. 改模型必须同时提交一条迁移；两者不一致会被 `alembic check` 拦下。
2. 迁移**不在容器启动时隐式执行**；开发期可开 `SUMMER_AUTO_MIGRATE=true`，生产由部署脚本显式跑。
3. **表改名与列改名自动检测不出来**（会被渲染成 drop + add，照执行即丢数据）；必须手写
   `op.alter_column(..., new_column_name=...)`。
4. pgvector 的 `CREATE EXTENSION`、`vector(1024)` 列与 HNSW 索引在迁移里是**手写**的，
   自动生成认不出来。
5. 破坏性命令（`downgrade base` 等）设有护栏：目标库名必须以 `_test` 结尾才能执行。
