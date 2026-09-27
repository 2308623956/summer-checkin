# infra

部署编排：PostgreSQL（pgvector）、两个应用容器与 nginx 路径分流。

## 目录

| 路径 | 作用 |
|---|---|
| `db/init-databases.sh` | postgres 容器首次初始化时建两个库并启用 pgvector |
| `docker-compose.yml` | 日常开发：四个容器（db / service / web / nginx） |
| `nginx/` | 路径分流：`/` 与 `/api/auth/*` → web，`/api/v1/*` → service |

## 两个数据库

| 库 | 用途 | 谁能连 |
|---|---|---|
| `summer_checkin` | 生产 | 只有服务器本机的应用容器 |
| `summer_checkin_test` | 测试 | 本地开发用这个库；服务器上不对外开放端口 |

`init-databases.sh` 由 postgres 镜像挂在 `/docker-entrypoint-initdb.d/`，**只在数据卷为空时执行一次**。
所以：

- 库被误删 → 手动重建，或 `docker compose down -v` 删卷重来（**会丢全部数据**）；
- 想改库名 → 改 `SUMMER_PROD_DB` / `SUMMER_TEST_DB` 之前先确认卷的状态。

`CREATE EXTENSION vector` 需要超级用户，因此放在这个初始化脚本里执行，而不是放进迁移。

## 本地开发

```bash
docker compose -f docker-compose.dev.yml up -d    # 只起 db（带 pgvector）
```

库名一律以 `_test` 结尾——`alembic downgrade` 有护栏，非测试库会被拒绝执行。
