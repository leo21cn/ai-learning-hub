#!/usr/bin/env bash
# nginx-vhost-apply.sh - 为 learning-hub (或其他新服务) 配置 nginx-gateway vhost + 申请 LE 证书
#
# 与 nginx-gateway stack 的本机文件系统约定:
#   - 配置单文件: /root/nginx-smartmoves/nginx.conf(已 bind-mount 到 nginx 容器 /etc/nginx/nginx.conf:ro)
#   - 证书路径:   /etc/letsencrypt/live/<domain>/{fullchain,privkey}.pem
#   - 在容器内被 bind-mount 成 /etc/nginx/certs/<domain>.{crt,key}(由 docker-compose.yml 控制)
#
# 此脚本分两阶段,确保在 LE 证书签出前 nginx.conf 已经能用、签出后 443 server 块才生效:
#   PHASE=1 - 加 80 server block + reload nginx + 用 certbot webroot 申请证书 (host 上跑)
#   PHASE=2 - 加 443 server block (container 内的 cert 已挂上) + reload nginx
#
# 可重复执行(幂等)。所有变更点前后都有 backup。
# 调用方式(由 publish.ps1 ssh 触发):
#   ssh ... "LH_DOMAIN=... NGINX_STACK_DIR=... bash /root/learning-hub/nginx-vhost-apply.sh phase1"
#   ssh ... "LH_DOMAIN=... NGINX_STACK_DIR=... STACK_NAME=... bash /root/learning-hub/nginx-vhost-apply.sh phase2"

set -euo pipefail

PHASE="${1:-${PHASE:-all}}"
: "${LH_DOMAIN:?missing LH_DOMAIN, 例如 learning-hub.smartmoves.com.cn}"
: "${NGINX_STACK_DIR:?missing NGINX_STACK_DIR, 例如 /root/nginx-smartmoves}"
: "${STACK_NAME:=nginx-gateway}"
: "${ACME_EMAIL:=admin@smartmoves.com.cn}"
: "${CERTBOT_WEBROOT:=/root/nginx-static/html}"

NGINX_CONF="${NGINX_STACK_DIR}/nginx.conf"
HTTP_SNIPPET="${REMOTE_DIR:-/root/learning-hub}/nginx-vhost-http.snippet"
FULL_SNIPPET="${REMOTE_DIR:-/root/learning-hub}/nginx-vhost-https.snippet"
LE_DIR="/etc/letsencrypt/live/${LH_DOMAIN}"
NGINX_CID="$(docker ps -q -f name=${STACK_NAME}_nginx | head -1)"

if [ -z "${NGINX_CID}" ]; then
  echo "[nginx-vhost-apply] ERROR: 找不到 ${STACK_NAME}_nginx 容器" >&2
  exit 1
fi
echo "[nginx-vhost-apply] nginx container id: ${NGINX_CID}"
echo "[nginx-vhost-apply] domain: ${LH_DOMAIN}"
echo "[nginx-vhost-apply] phase: ${PHASE}"

# 通用工具:把 snippet 幂等地插入到 nginx.conf 最后那个 '}' (http{} 闭合) 之前
insert_snippet() {
  local snippet="$1" marker="$2"
  if grep -q "${marker}" "${NGINX_CONF}"; then
    echo "[nginx-vhost-apply] nginx.conf 已包含 marker '${marker}', 跳过"
    return 0
  fi
  cp -a "${NGINX_CONF}" "${NGINX_CONF}.bak.$(date +%Y%m%d%H%M%S)"
  # 找最后一行内容为 '}' 的位置,在它前面插入 snippet + 空行
  python3 - "${NGINX_CONF}" "${snippet}" <<'PYEOF'
import sys, pathlib
conf = pathlib.Path(sys.argv[1])
snippet = pathlib.Path(sys.argv[2])
lines = conf.read_text().splitlines(keepends=True)
# 找最后一个位于行首且只有 '}' 的索引
idx = None
for i in range(len(lines) - 1, -1, -1):
    if lines[i].rstrip('\r\n') == '}':
        idx = i
        break
if idx is None:
    sys.exit("FAIL: 无法在 nginx.conf 末尾找到 '}'")
snippet_text = snippet.read_text()
if not snippet_text.endswith('\n'):
    snippet_text += '\n'
snippet_text += '\n'
new = lines[:idx] + [snippet_text] + lines[idx:]
conf.write_text(''.join(new))
PYEOF
  echo "[nginx-vhost-apply] snippet inserted to ${NGINX_CONF}"
}

# 通用工具:reload nginx 容器
reload_nginx() {
  echo "[nginx-vhost-apply] nginx -t:"
  docker exec "${NGINX_CID}" nginx -t
  echo "[nginx-vhost-apply] nginx -s reload:"
  docker exec "${NGINX_CID}" nginx -s reload
}

# =========================================================
# PHASE 1: 加 80 server block + 申请证书
# =========================================================
phase1() {
  insert_snippet "${HTTP_SNIPPET}" "server_name ${LH_DOMAIN};"
  reload_nginx

  if [ -d "${LE_DIR}" ] && [ -s "${LE_DIR}/fullchain.pem" ]; then
    echo "[nginx-vhost-apply] 证书已存在 (${LE_DIR}), 跳过 certbot"
  else
    echo "[nginx-vhost-apply] 用 certbot webroot 申请证书(${CERTBOT_WEBROOT})..."
    certbot certonly --webroot -w "${CERTBOT_WEBROOT}" \
      -d "${LH_DOMAIN}" --non-interactive --agree-tos \
      -m "${ACME_EMAIL}" --cert-name "${LH_DOMAIN}" \
      || { echo "[nginx-vhost-apply] certbot 失败,检查 ACME 日志" >&2; exit 1; }
  fi
  ls -la "${LE_DIR}"
}

# =========================================================
# PHASE 2: 加 443 server block(假设容器内 cert 已挂上)
# =========================================================
phase2() {
  # 验证容器内能读到证书
  if ! docker exec "${NGINX_CID}" test -f "/etc/nginx/certs/${LH_DOMAIN}.crt"; then
    echo "[nginx-vhost-apply] WARN: 容器内 /etc/nginx/certs/${LH_DOMAIN}.crt 不存在。"
    echo "[nginx-vhost-apply]      请先在 ${NGINX_STACK_DIR}/docker-compose.yml"
    echo "[nginx-vhost-apply]      加 fullchain.pem/privkey.pem 的 bind-mount 后,再 stack deploy。"
    exit 1
  fi
  insert_snippet "${FULL_SNIPPET}" "upstream learning_hub_frontend"
  reload_nginx
}

case "${PHASE}" in
  phase1) phase1 ;;
  phase2) phase2 ;;
  all) phase1; phase2 ;;
  *) echo "[nginx-vhost-apply] unknown phase: ${PHASE}"; exit 1 ;;
esac

echo "[nginx-vhost-apply] 完成。"
