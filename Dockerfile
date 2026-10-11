# 基于官方 workbuddy2api-hub 网关镜像，追加 DeepSeek 反代层
# 官方镜像已含全部 wb_*.py + dashboard.html，WORKDIR=/app
FROM ghcr.io/ardeyouxipianyi/workbuddy2api-hub:latest

COPY deepseek-gateway.py /app/deepseek-gateway.py
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 10000

CMD ["sh", "/app/start.sh"]
