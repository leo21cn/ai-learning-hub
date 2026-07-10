#!/usr/bin/env bash
# remote-setup.sh — 在 ECS 上创建学习 hub stack 需要的本地资源。
# 由 publish.ps1 scp 上传后,通过 ssh 触发。可重复执行(idempotent)。
set -euo pipefail

REMOTE_DIR="${ECS_REMOTE_DIR:-/root/learning-hub}"

echo "[remote-setup] 创建持久卷 lh_storage (若已存在则跳过)..."
docker volume inspect lh_storage >/dev/null 2>&1 || docker volume create lh_storage

echo "[remote-setup] 创建工作目录 ${REMOTE_DIR}..."
mkdir -p "${REMOTE_DIR}"

# 注:不创建外部 overlay 网络,这些网络由 postgres / nginx-gateway stack 负责;
# learning-hub stack 在 compose.yml 里仅声明 external: true 复用。
# 若 ECS 端首次部署且这些网络尚未出现,本脚本会跳过 —— 需手动从对应 stack 拉起。

echo "[remote-setup] 已就绪。"
