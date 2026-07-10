#!/bin/bash
echo "=== Health ==="
curl -s https://learning-hub.smartmoves.com.cn/api/public/health
echo
echo "=== GET admin no auth - expect 401 ==="
curl -i -s https://learning-hub.smartmoves.com.cn/api/admin/coursewares/1 2>&1 | head -3
echo "=== GET admin order no auth - expect 401 ==="
curl -i -s -X PUT -H "Content-Type: application/json" --data-binary '{"materialIds":[1]}' https://learning-hub.smartmoves.com.cn/api/admin/coursewares/1/materials/order 2>&1 | head -3
echo "=== GET public courseware 1 - expect 200 ==="
curl -s https://learning-hub.smartmoves.com.cn/api/public/coursewares/1 | head -c 500
echo
echo "=== UI contains cw-material-sorter ==="
curl -s https://learning-hub.smartmoves.com.cn/ | grep -c cw-material-sorter
