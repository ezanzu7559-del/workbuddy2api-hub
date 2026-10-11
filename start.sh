#!/bin/sh
set -e

# 公网部署必须设置 API Key，否则任何人可白嫖你的额度
if [ -z "$API_KEY" ]; then
  echo "[ERROR] API_KEY 环境变量未设置。公网部署必须设置。" >&2
  exit 1
fi

PORT="${PORT:-10000}"

PANEL_ARGS=""
if [ -n "$PANEL_PASSWORD" ]; then
  PANEL_ARGS="--panel-password $PANEL_PASSWORD"
fi

echo "[start] 启动网关 (内部 127.0.0.1:8788) ..."
python wb_proxy.py --host 0.0.0.0 --port 8788 --api-key "$API_KEY" $PANEL_ARGS &
GW_PID=$!

# 等网关就绪
sleep 3

echo "[start] 启动 DeepSeek 反代 (对外 0.0.0.0:$PORT) ..."
exec python deepseek-gateway.py --host 0.0.0.0 --port "$PORT" --gateway http://127.0.0.1:8788
