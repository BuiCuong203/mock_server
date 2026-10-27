"""
Chạy kèm mock GCP Pub/Sub (binary Go pubsub_mock, dựng trên pstest) cùng Cloud Mock Server.

- Khởi động / tắt theo server.py; log của pubsub_mock in ra cùng log mock (tiền tố [PUBSUB]).
- Cổng gRPC (PUBSUB_GRPC_PORT, mặc định 8085) mở ra ngoài: shipper đặt PUBSUB_EMULATOR_HOST=<ip-mock>:8085.
- Cổng quản trị HTTP của pubsub_mock chỉ nghe 127.0.0.1 (PUBSUB_ADMIN_PORT, mặc định 18086);
  dashboard / Admin API của mock gọi qua /mock/admin/api/pubsub/...

Biến môi trường:
  PUBSUB_ENABLED     1 (mặc định) | 0 để tắt
  PUBSUB_GRPC_PORT   cổng gRPC (8085)
  PUBSUB_ADMIN_PORT  cổng quản trị nội bộ (18086)
  PUBSUB_CONFIG      file cấu hình topic / subscription (streams/gcp_pubsub.json)
  PUBSUB_MOCK_BIN    đường dẫn binary (mặc định bin/pubsub_mock, rồi pubsub_mock/pubsub_mock)
"""
import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .config import BASE_DIR

ENABLED = os.environ.get("PUBSUB_ENABLED", "1") not in ("0", "false", "no")
GRPC_PORT = int(os.environ.get("PUBSUB_GRPC_PORT", "8085"))
ADMIN_PORT = int(os.environ.get("PUBSUB_ADMIN_PORT", "18086"))
CONFIG_PATH = os.environ.get("PUBSUB_CONFIG", os.path.join(BASE_DIR, "streams", "gcp_pubsub.json"))

# Service account giả cho credentials_base64 của shipper (bắt buộc có nhưng emulator không kiểm tra)
FAKE_CREDENTIALS = {
    "type": "service_account", "project_id": "mock-gcp-project", "private_key_id": "mock",
    "client_email": "cym-shipper@mock-gcp-project.iam.gserviceaccount.com", "client_id": "1000000000",
    "token_uri": "https://oauth2.googleapis.com/token",
}

_proc: Optional[subprocess.Popen] = None
_lock = threading.Lock()
_last_error = ""


def _binary() -> Optional[str]:
    candidates = [os.environ.get("PUBSUB_MOCK_BIN", ""),
                  os.path.join(BASE_DIR, "bin", "pubsub_mock"),
                  os.path.join(BASE_DIR, "pubsub_mock", "pubsub_mock")]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _pipe_logs(proc: subprocess.Popen):
    for line in iter(proc.stdout.readline, b""):
        print("[PUBSUB] " + line.decode("utf-8", "replace").rstrip(), flush=True)


def start() -> bool:
    global _proc, _last_error
    if not ENABLED:
        _last_error = "Đã tắt bằng PUBSUB_ENABLED=0"
        return False
    binary = _binary()
    if not binary:
        _last_error = "Không tìm thấy binary pubsub_mock (build: cd pubsub_mock && CGO_ENABLED=0 go build -o ../bin/pubsub_mock .)"
        print(f"[PUBSUB] {_last_error}", flush=True)
        return False
    with _lock:
        if _proc and _proc.poll() is None:
            return True
        _proc = subprocess.Popen(
            [binary, "-grpc-port", str(GRPC_PORT), "-http-addr", f"127.0.0.1:{ADMIN_PORT}", "-config", CONFIG_PATH],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=BASE_DIR)
    threading.Thread(target=_pipe_logs, args=(_proc,), daemon=True, name="pubsub-logs").start()
    for _ in range(30):            # chờ cổng quản trị sẵn sàng (tối đa ~3s)
        if _proc.poll() is not None:
            _last_error = f"pubsub_mock thoát ngay với mã {_proc.returncode} (cổng {GRPC_PORT} đang bị chiếm?)"
            print(f"[PUBSUB] {_last_error}", flush=True)
            return False
        if _admin("GET", "/status", timeout=0.3)[0] == 200:
            _last_error = ""
            return True
        time.sleep(0.1)
    return _proc.poll() is None


def stop():
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _proc.kill()


def _admin(method: str, path: str, body: Optional[bytes] = None, timeout: float = 5.0):
    req = urllib.request.Request(f"http://127.0.0.1:{ADMIN_PORT}{path}", data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {"error": str(e)}
    except (OSError, ValueError) as e:
        return 0, {"error": str(e)}


def _first_subscription() -> Dict[str, str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        p = cfg["projects"][0]
        t = p["topics"][0]
        return {"project": p["project_id"], "topic": t["name"], "subscription": t["subscriptions"][0]}
    except (OSError, ValueError, KeyError, IndexError):
        return {"project": "mock-gcp-project", "topic": "siem-audit-logs", "subscription": "siem-audit-logs-sub"}


def status() -> Dict[str, Any]:
    running = bool(_proc and _proc.poll() is None)
    out = {"enabled": ENABLED, "running": running, "grpc_port": GRPC_PORT, "binary": _binary(),
           "config": CONFIG_PATH, "error": _last_error if not running else ""}
    if running:
        code, data = _admin("GET", "/status")
        out["pubsub"] = data if code == 200 else {"error": data.get("error", f"HTTP {code}")}
    return out


def publish(data: Dict[str, Any]):
    """Chuyển tiếp tới POST /publish của pubsub_mock: {project, topic, messages?, count?, attributes?, pause?}"""
    if not (_proc and _proc.poll() is None):
        return 503, {"error": "pubsub_mock không chạy: " + (_last_error or "chưa khởi động")}
    return _admin("POST", "/publish", json.dumps(data).encode())


def shipper_config(mock_host: str) -> Dict[str, str]:
    """Đoạn cym.yml + biến môi trường cho shipper (mock_host = IP / tên máy chạy mock, shipper tới được)."""
    s = _first_subscription()
    cred = base64.b64encode(json.dumps(FAKE_CREDENTIALS, separators=(",", ":")).encode()).decode()
    yml = "\n".join([
        "input:",
        "    -   type: gcp_pubsub",
        '        log_type: "gcp_audit"',
        f'        project_id: "{s["project"]}"',
        f'        subscription_name: "{s["subscription"]}"',
        f'        credentials_base64: "{cred}"',
        '        input_id: "gcp_pubsub_01"',
        "        add_field:",
        "            input_plugin: gcp_pubsub",
        "            input_id: gcp_pubsub_01",
    ])
    return {"cym_yml": yml, "env": f"PUBSUB_EMULATOR_HOST={mock_host}:{GRPC_PORT}", **s}
