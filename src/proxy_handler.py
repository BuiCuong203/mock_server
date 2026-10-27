import os
import ssl
import time
import socket
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from .config import (
    SERVER_CERT, SERVER_KEY, GREEN, YELLOW, BLUE, CYAN, MAGENTA, RED, BOLD, RESET
)
from .request_logger import request_logger
from .scenario_manager import scenario_manager
from .admin_api import AdminApi
from .web_dashboard import WebDashboard


def process_http_request(
    handler_obj,
    method: str,
    raw_path: str,
    client_ip: str,
    headers: dict,
    body_bytes: bytes,
    is_proxy: bool = False
):
    start_time = time.time()
    parsed = urlparse(raw_path)
    path = parsed.path
    params = parse_qs(parsed.query)
    host = headers.get("Host", "") or headers.get("host", "")
    body_str = body_bytes.decode("utf-8", errors="ignore")
    now_str = time.strftime('%H:%M:%S')

    # 1. WEB DASHBOARD (/ hoặc /mock/admin/ hoặc /mock/admin)
    if method == "GET" and not is_proxy and (path in ("/", "/mock/admin", "/mock/admin/")):
        html_content = WebDashboard.get_html().encode("utf-8")
        handler_obj.send_response(200)
        handler_obj.send_header("Content-Type", "text/html; charset=utf-8")
        handler_obj.send_header("Content-Length", str(len(html_content)))
        handler_obj.end_headers()
        handler_obj.wfile.write(html_content)
        handler_obj.wfile.flush()
        return

    # 2. ADMIN REST API (/mock/admin/api/...)
    if not is_proxy and path.startswith("/mock/admin/api"):
        status, resp_hdrs, resp_bytes = AdminApi.handle_request(method, path, params, headers, body_str)
        handler_obj.send_response(status)
        for hk, hv in resp_hdrs.items():
            handler_obj.send_header(hk, hv)
        handler_obj.end_headers()
        handler_obj.wfile.write(resp_bytes)
        handler_obj.wfile.flush()
        return

    # 3. GENERIC DYNAMIC RULE MATCHING (Direct API & HTTPS Proxy)
    match_result = scenario_manager.find_matching_rule(method, path, host, headers, body_str, is_proxy=is_proxy)
    if match_result:
        rule, rule_source = match_result
        status, resp_hdrs, resp_bytes = rule.build_response(method, path, host, params, headers, body_str)
        matched_name = f"rule:{rule.name} ({rule_source})"

        # Rule yêu cầu cắt kết nối (giả lập lỗi mạng / connection reset)
        if status == -1:
            try:
                handler_obj.connection.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            handler_obj.close_connection = True
            duration_ms = (time.time() - start_time) * 1000
            request_logger.log(
                method=method, path=path, host=host, client_ip=client_ip, params=params,
                req_headers=headers, req_body=body_str, status=0, resp_headers={},
                resp_body="[CONNECTION DROPPED]", matched_rule=matched_name, duration_ms=duration_ms
            )
            tag = f"[{'PROXY' if is_proxy else 'DIRECT'}]"
            print(f"[{now_str}] {RED}{tag} [DROP {method}]{RESET} {BOLD}{path}{RESET} (Host: {host}) -> {CYAN}{matched_name}{RESET}")
            return
    else:
        # Fallback 404 nếu không có rule nào khớp
        matched_name = "no_rule_matched_404"
        status = 404
        err_data = {
            "error": "No matching mock rule found",
            "mode": "proxy" if is_proxy else "direct",
            "method": method,
            "host": host,
            "path": path,
            "hint": "You can add a dynamic rule for this endpoint via Dashboard or rules/*.json"
        }
        resp_bytes = json.dumps(err_data, indent=2).encode("utf-8")
        resp_hdrs = {
            "Content-Type": "application/json",
            "Content-Length": str(len(resp_bytes))
        }

    duration_ms = (time.time() - start_time) * 1000

    # 4. SEND RESPONSE
    handler_obj.send_response(status)
    for hk, hv in resp_hdrs.items():
        handler_obj.send_header(hk, hv)
    handler_obj.end_headers()
    handler_obj.wfile.write(resp_bytes)
    handler_obj.wfile.flush()

    # 5. AUDIT LOG & CONSOLE OUTPUT
    resp_preview = resp_bytes.decode("utf-8", errors="ignore")
    request_logger.log(
        method=method,
        path=path,
        host=host,
        client_ip=client_ip,
        params=params,
        req_headers=headers,
        req_body=body_str,
        status=status,
        resp_headers=resp_hdrs,
        resp_body=resp_preview,
        matched_rule=matched_name,
        duration_ms=duration_ms
    )

    tag = f"[{'PROXY' if is_proxy else 'DIRECT'}]"
    color = GREEN if status < 400 else (YELLOW if status < 500 else RED)
    print(f"[{now_str}] {color}{tag} [{status} {method}]{RESET} {BOLD}{path}{RESET} (Host: {host}) -> {CYAN}{matched_name}{RESET} [{round(duration_ms, 1)}ms]")


class MockCloudHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_CONNECT(self):
        """Xử lý HTTPS Proxy Tunneling cho mọi domain bên ngoài qua lệnh CONNECT"""
        now_str = time.strftime('%H:%M:%S')
        host_port = self.path
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        print(f"[{now_str}] {MAGENTA}[HTTPS PROXY CONNECT]{RESET} Mở đường hầm TLS tới: {BOLD}{host_port}{RESET}")

        # Gửi 200 Connection Established
        self.send_response(200, "Connection Established")
        self.end_headers()

        # Bọc TLS socket và xử lý các requests bên trong tunnel
        try:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
            tls_socket = ssl_ctx.wrap_socket(self.connection, server_side=True)
            tls_socket.settimeout(15.0)

            # Handler chuyên trách cho kênh TLS Proxy này
            TLSProxyConnectionHandler(tls_socket, self.client_address, self.server)
        except Exception:
            pass
        finally:
            self.close_connection = True

    def _read_body(self) -> bytes:
        content_len = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(content_len) if content_len > 0 else b""

    def do_HEAD(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "GET", self.path, client_ip, dict(self.headers), b"", is_proxy=False)

    def do_GET(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "GET", self.path, client_ip, dict(self.headers), b"", is_proxy=False)

    def do_POST(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "POST", self.path, client_ip, dict(self.headers), body, is_proxy=False)

    def do_PUT(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "PUT", self.path, client_ip, dict(self.headers), body, is_proxy=False)

    def do_DELETE(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "DELETE", self.path, client_ip, dict(self.headers), body, is_proxy=False)

    def do_OPTIONS(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "OPTIONS", self.path, client_ip, dict(self.headers), b"", is_proxy=False)


class TLSProxyConnectionHandler(MockCloudHandler):
    """Xử lý stream các HTTP requests trên socket đã bọc mã hóa TLS qua proxy"""
    def __init__(self, tls_socket, client_address, server):
        self.connection = tls_socket
        self.rfile = tls_socket.makefile("rb", -1)
        self.wfile = tls_socket.makefile("wb", -1)
        self.client_address = client_address
        self.server = server
        self.close_connection = False

        try:
            while not self.close_connection:
                self.handle_one_request()
        except (socket.timeout, ssl.SSLError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            try:
                self.wfile.flush()
            except Exception:
                pass
            try:
                self.connection.close()
            except Exception:
                pass

    def do_HEAD(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "GET", self.path, client_ip, dict(self.headers), b"", is_proxy=True)

    def do_GET(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "GET", self.path, client_ip, dict(self.headers), b"", is_proxy=True)

    def do_POST(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "POST", self.path, client_ip, dict(self.headers), body, is_proxy=True)

    def do_PUT(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "PUT", self.path, client_ip, dict(self.headers), body, is_proxy=True)

    def do_DELETE(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        body = self._read_body()
        process_http_request(self, "DELETE", self.path, client_ip, dict(self.headers), body, is_proxy=True)

    def do_OPTIONS(self):
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        process_http_request(self, "OPTIONS", self.path, client_ip, dict(self.headers), b"", is_proxy=True)
