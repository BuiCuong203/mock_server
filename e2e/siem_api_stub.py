#!/usr/bin/env python3
"""
SIEM-API stub tĩnh cho e2e: luôn trả "không có cấu hình mới" để shipper giữ nguyên conf.d/cym.yml
đang test (khác mock_siem_api.py của test-cym-log-shipper vốn chủ động đẩy cấu hình xuống).

    python3 siem_api_stub.py [port]      # mặc định 18090
"""
import json
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

GET_RESPONSES = {
    "/v1/node/update_v2": {"update": False, "config_hash": ""},
    "/v1/node/update": {"update": False, "config_hash": ""},
    "/v1/node/command_line": {"detail": "success", "status": 0, "command": ""},
    "/v1/node/log": {"detail": "success", "status": 0, "request": False},
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in GET_RESPONSES:
            self._send(GET_RESPONSES[path])
        else:
            self._send({"error": "not found", "path": path}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        self._send({"detail": "success", "status": 0})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18090
    print(f"[siem-api-stub] listening on :{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
