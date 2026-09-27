#!/bin/bash
# 部署脚本：**显式**跑迁移，再起服务。
#
# 为什么不放进容器启动：多实例同时启动会并发跑迁移，而迁移失败会让容器起不来、
# 排查时只看到"服务启动失败"（architecture.md §6）。
#
# 用法：在仓库根目录执行 `bash infra/deploy.sh`（需要在 .env 里有 SUMMER_DATABASE_URL）。
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> 1/3 构建镜像"
docker compose -f infra/docker-compose.yml build

echo "==> 2/3 起数据库并等待就绪"
docker compose -f infra/docker-compose.yml up -d db
until docker compose -f infra/docker-compose.yml exec -T db \
    pg_isready -U "${POSTGRES_USER:-summer}" -d "${SUMMER_PROD_DB:-summer_checkin}" >/dev/null 2>&1; do
  echo "    等待数据库就绪…"
  sleep 2
done

echo "==> 3/3 执行迁移（显式，不在容器启动时）"
# 生产库名不以 _test 结尾，所以这里**不能**用 alembic 的 downgrade 护栏；
# upgrade 本身不删数据，护栏只拦破坏性操作。
docker compose -f infra/docker-compose.yml run --rm service \
  /app/.venv/bin/alembic upgrade head

echo "==> 迁移完成，启动全部服务"
docker compose -f infra/docker-compose.yml up -d

echo "==> 健康检查"
sleep 3
docker compose -f infra/docker-compose.yml ps
