#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deepseek-gateway.py —— 把 workbuddy2api-hub 网关伪装成 DeepSeek 官方 API。

用途
    让只认 DeepSeek 协议 / 模型名（deepseek-chat / deepseek-reasoner）的客户端，
    实际使用你在 workbuddy2api-hub 网关里的 WorkBuddy 额度。

原理
    一个极薄的模型名改写反代：收到 DeepSeek 模型名 -> 改写成网关模型名 ->
    转发到网关的 OpenAI 兼容接口（/v1/chat/completions、/v1/models），
    响应（含 SSE 流式）原样透传。

依赖
    仅 Python 标准库，Python 3.9+。与网关一致，零第三方依赖。

用法
    python deepseek-gateway.py                                  # 监听 8787，转发 127.0.0.1:8788
    python deepseek-gateway.py --port 8787 --gateway http://127.0.0.1:8788

客户端配置（DeepSeek 预设 / 任意 OpenAI 兼容工具）
    Base URL : http://127.0.0.1:8787/v1     （也兼容不带 /v1）
    API Key  : 网关看板「设置」页生成的 Key；网关未开 key 校验时可随便填
    模型     : deepseek-chat / deepseek-reasoner

模型映射（按需修改 MODEL_MAP）
    默认把 deepseek-chat 指向网关的 deepseek-v4.1-flash（国际/国内均有），
    把 deepseek-reasoner 指向 deepseek-v4-pro（仅国内版 codebuddy.cn 有）。
    如果你的账号只有国际版，请把 deepseek-reasoner 也改成国际版可用的模型。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# 配置区
# ---------------------------------------------------------------------------
DEFAULT_GATEWAY = "http://127.0.0.1:8788"   # workbuddy2api-hub 网关地址
DEFAULT_PORT = 8787                          # 本反代监听端口

# DeepSeek 模型名 -> 网关模型名
MODEL_MAP = {
    "deepseek-chat": "deepseek-v4.1-flash",   # 通用对话模型
    "deepseek-reasoner": "deepseek-v4-pro",   # 推理模型（仅国内版）
}

# 上游网关是否要求 API Key（true 时，客户端必须带 Authorization，本反代透传）
UPSTREAM_REQUIRES_KEY = False
# ---------------------------------------------------------------------------


def rewrite_model(mid):
    """把 DeepSeek 模型名改写成网关模型名；未知模型原样透传。"""
    if mid in MODEL_MAP:
        return MODEL_MAP[mid]
    return mid


class DeepSeekFacade(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    gateway = DEFAULT_GATEWAY

    # ---- 工具 -------------------------------------------------------------
    def log_message(self, fmt, *args):
        sys.stderr.write("[ds-facade] %s\n" % (fmt % args))

    def _json_bytes(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- 路由 -------------------------------------------------------------
    def _route(self, method, path):
        # 归一化路径：去掉 /v1 前缀差异，DeepSeek 兼容 /models 与 /v1/models
        norm = path
        if norm.startswith("/v1"):
            norm = norm[3:] or "/"
        if method == "GET" and norm in ("/health", "/"):
            self._json_bytes({"ok": True, "service": "deepseek-facade"})
        elif method == "GET" and norm == "/models":
            self._handle_models()
        elif method == "POST" and norm == "/chat/completions":
            self._handle_chat()
        else:
            self._json_bytes(
                {"error": {"message": "not found", "type": "invalid_request_error",
                           "code": 404}}, 404)

    def do_GET(self):
        self._route("GET", self.path)

    def do_POST(self):
        self._route("POST", self.path)

    # ---- /models ----------------------------------------------------------
    def _handle_models(self):
        data = {
            "object": "list",
            "data": [
                {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek"},
                {"id": "deepseek-reasoner", "object": "model", "owned_by": "deepseek"},
            ],
        }
        self._json_bytes(data)

    # ---- /chat/completions ------------------------------------------------
    def _handle_chat(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._json_bytes(
                {"error": {"message": "missing request body",
                           "type": "invalid_request_error", "code": 400}}, 400)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json_bytes(
                {"error": {"message": "invalid JSON body",
                           "type": "invalid_request_error", "code": 400}}, 400)
        if not isinstance(body, dict):
            return self._json_bytes(
                {"error": {"message": "expected a JSON object",
                           "type": "invalid_request_error", "code": 400}}, 400)

        # 改写模型名
        if "model" in body:
            body["model"] = rewrite_model(str(body.get("model") or ""))

        # 转发到网关
        url = self.gateway.rstrip("/") + "/v1/chat/completions"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        # 透传鉴权头（DeepSeek 客户端会带 Authorization: Bearer <key>）
        for h in ("Authorization", "Content-Type"):
            if h in self.headers:
                req.add_header(h, self.headers[h])

        try:
            upstream = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            # 把网关的错误（503 无账号 / 400 模型不符 / 401 等）原样透传
            err_body = e.read()
            self.send_response(e.code)
            ct = e.headers.get("Content-Type", "application/json")
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return
        except urllib.error.URLError as e:
            return self._json_bytes(
                {"error": {"message": "gateway unreachable: %s" % e.reason,
                           "type": "server_error", "code": 502}}, 502)

        # 响应透传（含流式 SSE）
        content_type = upstream.headers.get("Content-Type", "")
        status = upstream.status
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        # 流式不写 Content-Length，逐块透传；非流式透传 Content-Length
        cl = upstream.headers.get("Content-Length")
        if cl and "text/event-stream" not in content_type:
            self.send_header("Content-Length", cl)
        self.end_headers()

        if "text/event-stream" in content_type:
            while True:
                chunk = upstream.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        else:
            self.wfile.write(upstream.read())


def main():
    ap = argparse.ArgumentParser(description="DeepSeek-compatible facade over workbuddy2api-hub")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--gateway", default=DEFAULT_GATEWAY)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    DeepSeekFacade.gateway = args.gateway.rstrip("/")
    srv = ThreadingHTTPServer((args.host, args.port), DeepSeekFacade)
    sys.stderr.write("[ds-facade] DeepSeek API facade listening on http://%s:%d/v1\n"
                     % (args.host, args.port))
    sys.stderr.write("[ds-facade] forwarding to gateway %s\n" % DeepSeekFacade.gateway)
    sys.stderr.write("[ds-facade] model map: %s\n" % json.dumps(MODEL_MAP, ensure_ascii=False))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
