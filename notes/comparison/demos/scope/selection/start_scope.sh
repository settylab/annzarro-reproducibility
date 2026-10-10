#!/bin/bash
# Starts the local SCope 1.8.2 (9ae5207) server for the selection test. Idempotent. Stop: docker rm -f scope-selection
D=$DEMO_ROOT/scope/selection/serve
docker rm -f scope-selection >/dev/null 2>&1
docker run -d --name scope-selection --platform linux/amd64 -p 55850-55853:55850-55853 -p 8000:8000 \
  -v $D:/root/.local/share/SCope -v $D/config.json:/app/scope_config.json \
  -e SCOPE_CONFIG=/app/scope_config.json -e DATABASE_URL=sqlite:////root/.local/share/SCope/scope.sqlite \
  scope:1.8.2-9ae5207-final bash -c "cd /app && (/opt/conda/envs/scope/bin/python -m http.server 55850 --bind 0.0.0.0 >/tmp/http.log 2>&1 &) ; cd /app/opt && poetry run hypercorn --bind 0.0.0.0 main:scope_api" >/dev/null || exit 1
for i in $(seq 1 60); do
  curl -sf -m 2 http://127.0.0.1:8000/echo/up >/dev/null && curl -sf -m 2 http://127.0.0.1:55850/ >/dev/null && break
  sleep 3
done
sleep 25
echo "frontend: $(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:55850/)  api: $(curl -s -m 3 http://127.0.0.1:8000/echo/up)"
