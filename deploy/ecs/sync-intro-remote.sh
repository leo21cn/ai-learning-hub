#!/usr/bin/env bash
# Rebuild the frontend image with only /intro/index.html replaced, then roll the
# learning-hub_frontend service. Runs on the ECS host; the build context
# (/root/learning-hub/intro-deploy) is prepared by scripts/sync-intro.ps1.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

SERVICE="learning-hub_frontend"
BASE="$(docker service inspect "$SERVICE" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}')"
BASE="${BASE%%@*}"
TAG="lh-frontend:intro-$(date +%Y%m%d-%H%M%S)"

printf 'FROM %s\nCOPY index.html og-cover.png qr.png /usr/share/nginx/html/intro/\n' "$BASE" >Dockerfile

echo "[*] base image : $BASE"
echo "[*] new image  : $TAG"
docker build -q -t "$TAG" . >/dev/null
echo "[*] built"

docker service update -q --image "$TAG" "$SERVICE" >/dev/null

CID="$(docker ps -q -f "name=${SERVICE}.1" | head -1)"
echo "[*] container  : $CID"
docker exec "$CID" sha256sum \
  /usr/share/nginx/html/intro/index.html \
  /usr/share/nginx/html/intro/og-cover.png \
  /usr/share/nginx/html/intro/qr.png
echo "[*] service now: $(docker service inspect "$SERVICE" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}')"

# Keep the 5 newest intro images; older ones are only rollback candidates.
docker images --format '{{.Repository}}:{{.Tag}}' lh-frontend \
  | grep '^lh-frontend:intro-' | sort -r | tail -n +6 \
  | xargs -r docker rmi >/dev/null 2>&1 || true
