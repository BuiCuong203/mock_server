import fcntl
import os
import ssl
import subprocess
from .config import (
    CERTS_DIR, CA_CERT, CA_KEY, SERVER_CERT, SERVER_KEY, CA_BUNDLE,
    GREEN, YELLOW, RESET
)

# Domain mà mock đóng vai qua HTTPS proxy (CONNECT). Thêm domain mới vào đây:
# lần khởi động sau server cert được ký lại bằng CA cũ (không cần tin lại CA).
SAN_DNS = [
    "*.microsoftonline.com",
    "login.microsoftonline.com",
    "*.office.com",
    "manage.office.com",
    "*.api.securitycenter.microsoft.com",
    "api.securitycenter.microsoft.com",
    "*.amazonaws.com",
    "*.us-east-1.amazonaws.com",
    "sqs.us-east-1.amazonaws.com",
    "logs.us-east-1.amazonaws.com",
    "s3.us-east-1.amazonaws.com",
    "*.s3.amazonaws.com",
    "*.s3.us-east-1.amazonaws.com",
    "localhost",
    "*.ap-southeast-1.amazonaws.com",
    "*.ap-southeast-2.amazonaws.com",
    "*.ap-northeast-1.amazonaws.com",
    "*.us-west-2.amazonaws.com",
    "*.eu-west-1.amazonaws.com",
    "graph.microsoft.com",
    "*.graph.microsoft.com",
    "api.securitycenter.windows.com",
    "*.securitycenter.windows.com",
    "*.s3-us-east-1.amazonaws.com",
    "*.us-east-2.amazonaws.com",
    "*.s3.us-east-2.amazonaws.com",
    "*.s3-us-east-2.amazonaws.com",
    "*.us-west-1.amazonaws.com",
    "*.s3.us-west-1.amazonaws.com",
    "*.s3-us-west-1.amazonaws.com",
    "*.s3.us-west-2.amazonaws.com",
    "*.s3-us-west-2.amazonaws.com",
    "*.s3.ap-southeast-1.amazonaws.com",
    "*.s3-ap-southeast-1.amazonaws.com",
    "*.s3.ap-southeast-2.amazonaws.com",
    "*.s3-ap-southeast-2.amazonaws.com",
    "*.s3.ap-northeast-1.amazonaws.com",
    "*.s3-ap-northeast-1.amazonaws.com",
    "*.ap-northeast-2.amazonaws.com",
    "*.s3.ap-northeast-2.amazonaws.com",
    "*.s3-ap-northeast-2.amazonaws.com",
    "*.ap-south-1.amazonaws.com",
    "*.s3.ap-south-1.amazonaws.com",
    "*.s3-ap-south-1.amazonaws.com",
    "*.s3.eu-west-1.amazonaws.com",
    "*.s3-eu-west-1.amazonaws.com",
    "*.eu-central-1.amazonaws.com",
    "*.s3.eu-central-1.amazonaws.com",
    "*.s3-eu-central-1.amazonaws.com",
    "*.servicebus.windows.net",
    "*.blob.core.windows.net",
]
SAN_IPS = ["127.0.0.1"]


def _san_ext_content() -> str:
    alt = "".join(f"DNS.{i} = {d}\n" for i, d in enumerate(SAN_DNS, 1))
    alt += "".join(f"IP.{i} = {ip}\n" for i, ip in enumerate(SAN_IPS, 1))
    return ("authorityKeyIdentifier=keyid,issuer\n"
            "basicConstraints=CA:FALSE\n"
            "keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment\n"
            "subjectAltName = @alt_names\n\n"
            "[alt_names]\n" + alt)


def _sign_server_cert(san_ext_path: str):
    """Sinh server key + CSR và ký bằng CA hiện có, SAN theo san.ext.
    Ghi ra file tạm rồi os.replace -> không bao giờ để lại cặp key/cert lệch nhau."""
    tmp_key, tmp_csr, tmp_crt = SERVER_KEY + ".tmp", os.path.join(CERTS_DIR, "server.csr.tmp"), SERVER_CERT + ".tmp"
    subprocess.run([
        "openssl", "req", "-new", "-nodes",
        "-newkey", "rsa:2048", "-keyout", tmp_key,
        "-out", tmp_csr,
        "-subj", "/C=VN/ST=HN/O=CyM/CN=mock-cloud-services"
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([
        "openssl", "x509", "-req", "-in", tmp_csr,
        "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
        "-out", tmp_crt, "-days", "3650", "-sha256",
        "-extfile", san_ext_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp_key, SERVER_KEY)
    os.replace(tmp_crt, SERVER_CERT)
    os.replace(tmp_csr, os.path.join(CERTS_DIR, "server.csr"))


def _server_pair_ok() -> bool:
    """server.crt và server.key có tồn tại và đi cặp với nhau không (nạp thử như lúc bắt tay TLS)."""
    if not (os.path.exists(SERVER_CERT) and os.path.exists(SERVER_KEY)):
        return False
    try:
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
        return True
    except (ssl.SSLError, OSError):
        return False


def ensure_certificates():
    """Đảm bảo bộ chứng chỉ Mock CA + server cert dùng được. Nhiều container có thể mount chung certs/
    -> làm dưới file lock. CA có sẵn thì luôn giữ (shipper đã tin CA đó); server cert thiếu, lệch cặp khóa
    hoặc danh sách SAN đổi thì chỉ ký lại server cert bằng CA cũ."""
    os.makedirs(CERTS_DIR, exist_ok=True)
    with open(os.path.join(CERTS_DIR, ".certs.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _ensure_certificates_locked()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _ensure_certificates_locked():
    san_ext_path = os.path.join(CERTS_DIR, "san.ext")
    expected_san = _san_ext_content()
    have_ca = os.path.exists(CA_CERT) and os.path.exists(CA_KEY)

    if have_ca:
        current_san = ""
        if os.path.exists(san_ext_path):
            with open(san_ext_path, "r", encoding="utf-8") as f:
                current_san = f.read()
        pair_ok = _server_pair_ok()
        if pair_ok and current_san == expected_san and os.path.exists(CA_BUNDLE):
            return True
        if not pair_ok:
            print(f"{YELLOW}[INIT CERTS] server.crt / server.key thiếu hoặc không khớp -> ký lại bằng Mock CA hiện có...{RESET}")
        elif current_san != expected_san:
            print(f"{YELLOW}[INIT CERTS] Danh sách SAN thay đổi -> ký lại server cert bằng Mock CA hiện có...{RESET}")
        if not pair_ok or current_san != expected_san:
            with open(san_ext_path, "w", encoding="utf-8") as f:
                f.write(expected_san)
            _sign_server_cert(san_ext_path)
            print(f"{GREEN}[INIT CERTS] Đã ký lại server cert ({len(SAN_DNS)} domain), CA giữ nguyên{RESET}")
        if not os.path.exists(CA_BUNDLE):
            _write_ca_bundle()
        return True

    print(f"{YELLOW}[INIT CERTS] Đang tự động sinh cặp chứng chỉ Mock SSL cho Proxy...{RESET}")

    # 1. Root CA
    subprocess.run([
        "openssl", "req", "-x509", "-new", "-nodes",
        "-newkey", "rsa:2048", "-keyout", CA_KEY,
        "-out", CA_CERT, "-days", "3650",
        "-subj", "/C=VN/ST=HN/O=CyM/CN=CyM Mock Root CA"
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. SAN Extension + 3. Server cert ký bởi CA
    with open(san_ext_path, "w", encoding="utf-8") as f:
        f.write(expected_san)
    _sign_server_cert(san_ext_path)

    # 4. CA bundle
    _write_ca_bundle()
    print(f"{GREEN}[INIT CERTS] Đã tạo xong chứng chỉ SSL và bundle tại {CERTS_DIR}{RESET}")
    return True


def _write_ca_bundle():
    """CA bundle = CA hệ thống + Mock CA (shipper đặt SSL_CERT_FILE trỏ vào file này)."""
    sys_ca = "/etc/ssl/certs/ca-certificates.crt"
    tmp = CA_BUNDLE + ".tmp"
    with open(tmp, "wb") as outfile:
        if os.path.exists(sys_ca):
            with open(sys_ca, "rb") as infile:
                outfile.write(infile.read())
        with open(CA_CERT, "rb") as infile:
            outfile.write(infile.read())
    os.replace(tmp, CA_BUNDLE)
