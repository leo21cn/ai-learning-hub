#!/bin/bash
echo "=== service ls ==="
docker service ls
echo
echo "=== stack ps ==="
docker stack ps learning-hub
echo
echo "=== backend tail log ==="
docker service logs --tail 20 learning-hub_backend
