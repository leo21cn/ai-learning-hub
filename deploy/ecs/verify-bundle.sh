#!/bin/bash
JS=$(curl -s https://learning-hub.smartmoves.com.cn/ | grep -oE "assets/index-[A-Za-z0-9_-]+\.js" | head -1)
echo "JS file: $JS"
echo "=== cw-material-sorter tokens in bundle ==="
curl -s https://learning-hub.smartmoves.com.cn/$JS | grep -oE "cw-material-sorter[a-z-]*" | sort -u
echo "=== SortableMaterialRow handler ==="
curl -s https://learning-hub.smartmoves.com.cn/$JS | grep -oE "cw-material-sorter-(row|handle|up|down|remove|available|add)-[0-9]+" | sort -u | head -10
echo "=== detail-materials-order-hint (P-DETAIL) ==="
curl -s https://learning-hub.smartmoves.com.cn/$JS | grep -oE "detail-materials-order-hint" | head -1
