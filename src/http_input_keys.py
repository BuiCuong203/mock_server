"""
Khóa / token cho input `http` của CyM-Log-Shipper (shipper là HTTP server, mock là client đẩy log vào).

Shipper xác thực header X-API-KEY = base64(payload) + "." + base64(chữ ký RSA-SHA256 PKCS#1 v1.5 của payload),
kiểm tra bằng public key lấy từ certificate PEM trong biến môi trường PUB_KEY. Shipper còn bắt buộc
SSL_CERT / SSL_KEY (dùng khi bật tls: true) dù không bật TLS.

Mock tự sinh 1 cặp khóa ký (certs/http_input/signer.key + signer.crt) và dùng server cert sẵn có của mock
(ký bởi Mock CA, SAN localhost / 127.0.0.1) làm SSL_CERT / SSL_KEY cho shipper.
"""
import base64
import json
import os
import subprocess
import tempfile
import threading
import time
from typing import Dict, Optional

from .config import CERTS_DIR, SERVER_CERT, SERVER_KEY

HTTP_INPUT_DIR = os.path.join(CERTS_DIR, "http_input")
SIGNER_KEY = os.path.join(HTTP_INPUT_DIR, "signer.key")
SIGNER_CERT = os.path.join(HTTP_INPUT_DIR, "signer.crt")

_lock = threading.Lock()


def ensure_keys() -> None:
    with _lock:
        if os.path.exists(SIGNER_KEY) and os.path.exists(SIGNER_CERT):
            return
        os.makedirs(HTTP_INPUT_DIR, exist_ok=True)
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes", "-newkey", "rsa:2048",
            "-keyout", SIGNER_KEY, "-out", SIGNER_CERT, "-days", "3650",
            "-subj", "/C=VN/O=CyM/CN=CyM Mock HTTP Agent Signer",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[HTTP INPUT] Đã sinh khóa ký token tại {HTTP_INPUT_DIR}")


def make_token(payload: Optional[Dict] = None) -> str:
    """Token X-API-KEY hợp lệ với PUB_KEY = signer.crt."""
    ensure_keys()
    data = json.dumps(payload or {"agent_id": "cym-mock-agent", "iat": int(time.time())},
                      separators=(",", ":")).encode()
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", SIGNER_KEY],
                         input=data, capture_output=True, check=True).stdout
    return base64.b64encode(data).decode() + "." + base64.b64encode(sig).decode()


def sign_with_key(private_key_pem: str, payload: Optional[str] = None) -> Dict[str, str]:
    """Ký token X-API-KEY bằng private key do người dùng dán vào (vd agent.key).
    Khóa chỉ ghi ra file tạm 0600 trong lúc chạy openssl rồi xóa ngay; không lưu lại ở đâu."""
    key = (private_key_pem or "").strip()
    if "-----BEGIN" not in key or "PRIVATE KEY-----" not in key:
        raise ValueError("Không phải private key PEM (cần dòng -----BEGIN ... PRIVATE KEY-----)")
    if len(key) > 20000:
        raise ValueError("Private key quá lớn")
    data = (payload if payload not in (None, "") else json.dumps({"agent_id": "mock-sender"}, separators=(",", ":"))).encode()
    if len(data) > 4096:
        raise ValueError("Payload tối đa 4KB")
    fd, path = tempfile.mkstemp(prefix="cym_sign_", suffix=".pem")
    try:
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key + "\n")
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", path, "-passin", "pass:"], input=data, capture_output=True)
        if sig.returncode != 0:
            raise ValueError("openssl không ký được bằng khóa này (khóa hỏng hoặc có mật khẩu?)")
        pub = subprocess.run(["openssl", "pkey", "-in", path, "-pubout", "-passin", "pass:"], capture_output=True)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    token = base64.b64encode(data).decode() + "." + base64.b64encode(sig.stdout).decode()
    # dấu vân tay public key: so với  openssl x509 -in agent.crt -noout -pubkey | openssl md5
    import hashlib
    fp = hashlib.md5(pub.stdout).hexdigest() if pub.returncode == 0 else ""
    return {"token": token, "public_key_md5": fp, "payload": data.decode("utf-8", "replace")}


def shipper_env() -> Dict[str, str]:
    """Giá trị 3 biến môi trường shipper cần cho input http."""
    ensure_keys()

    def read(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    return {"PUB_KEY": read(SIGNER_CERT), "SSL_CERT": read(SERVER_CERT), "SSL_KEY": read(SERVER_KEY)}


def shipper_env_script() -> str:
    """Đoạn shell export 3 biến (dán vào terminal trước khi chạy shipper)."""
    lines = []
    for k, v in shipper_env().items():
        lines.append(f"export {k}='{v.strip()}'")
    return "\n".join(lines) + "\n"
