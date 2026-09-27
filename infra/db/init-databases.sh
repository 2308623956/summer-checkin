#!/bin/bash
# 由 postgres 镜像在**数据卷为空时**执行一次（挂在 /docker-entrypoint-initdb.d/）。
# 作用：在默认数据库里启用 pgvector。
#
# 注意：只在初始化时跑一次。要启用 pgvector 到已有数据库，手动执行：
#   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS vector"
set -euo pipefail

echo "init-databases: enabling pgvector in ${POSTGRES_DB}"
# pgvector 不是 trusted extension：需要超级用户，所以由这里的初始化用户执行。
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE EXTENSION IF NOT EXISTS vector"

echo "init-databases: done"
