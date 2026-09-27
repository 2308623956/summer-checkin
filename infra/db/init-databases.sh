#!/bin/bash
# 由 postgres 镜像在**数据卷为空时**执行一次（挂在 /docker-entrypoint-initdb.d/）。
# 作用：建两个库 + 在每个库里启用 pgvector。
#
# 注意：只在初始化时跑一次。库被删掉后要么手动重建，要么删卷重来（见 infra/README.md）。
set -euo pipefail

PROD_DB="${SUMMER_PROD_DB:-summer_checkin}"
TEST_DB="${SUMMER_TEST_DB:-summer_checkin_test}"

create_database() {
  local db="$1"
  echo "init-databases: creating database ${db}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE DATABASE \"${db}\""
}

enable_vector() {
  local db="$1"
  echo "init-databases: enabling pgvector in ${db}"
  # pgvector 不是 trusted extension：需要超级用户，所以由这里的初始化用户执行。
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" \
    -c "CREATE EXTENSION IF NOT EXISTS vector"
}

for db in "${PROD_DB}" "${TEST_DB}"; do
  if psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
      -tAc "SELECT 1 FROM pg_database WHERE datname = '${db}'" | grep -q 1; then
    echo "init-databases: ${db} already exists, skipping create"
  else
    create_database "${db}"
  fi
  enable_vector "${db}"
done

echo "init-databases: done (${PROD_DB}, ${TEST_DB})"
