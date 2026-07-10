#!/usr/bin/env bash
# db-init.sh — 在 postgres stack 现有服务上幂等创建 learning_hub 数据库。
# 复用 postgres stack 已有的 user(无需新建账号,避免跨 stack 授权改动)。
set -euo pipefail

# 这些环境变量由 publish.ps1 通过 ssh 注入(从 .env 读出来):
#   POSTGRES_SERVICE_NAME  e.g. postgres_postgres
#   DATABASE_USER           e.g. agent_mcp
#   DATABASE_NAME           e.g. learning_hub
: "${POSTGRES_SERVICE_NAME:?missing POSTGRES_SERVICE_NAME}"
: "${DATABASE_USER:?missing DATABASE_USER}"
: "${DATABASE_NAME:?missing DATABASE_NAME}"

echo "[db-init] 查找 postgres 容器: ${POSTGRES_SERVICE_NAME}"
PG_CID="$(docker ps --filter "name=${POSTGRES_SERVICE_NAME}" -q | head -1)"
if [ -z "${PG_CID}" ]; then
  echo "[db-init] ERROR: 找不到 ${POSTGRES_SERVICE_NAME} 容器;确认 postgres stack 已部署。" >&2
  exit 1
fi
echo "[db-init] postgres container id: ${PG_CID}"

echo "[db-init] 检查数据库 ${DATABASE_NAME} 是否已存在..."
EXISTS="$(docker exec -e PGPASSWORD="${DATABASE_PASSWORD:-}" "${PG_CID}" \
  psql -U "${DATABASE_USER}" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='${DATABASE_NAME}'")"

if [ "${EXISTS}" = "1" ]; then
  echo "[db-init] 数据库 ${DATABASE_NAME} 已存在,跳过 CREATE。"
  exit 0
fi

echo "[db-init] 创建数据库 ${DATABASE_NAME}..."
docker exec -e PGPASSWORD="${DATABASE_PASSWORD:-}" "${PG_CID}" \
  psql -U "${DATABASE_USER}" -d postgres -c "CREATE DATABASE ${DATABASE_NAME};"

echo "[db-init] 完成。"
