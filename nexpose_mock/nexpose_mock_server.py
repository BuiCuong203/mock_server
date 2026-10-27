"""Mock Rapid7 Nexpose (InsightVM on-prem) API v3 cho siem-va-integrate.

Giả lập 2 endpoint mà job sync_rapid7_nexpose gọi:
  GET  /api/3/assets?page=&size=          -> lần sync đầu (sync_all_assets)
  POST /api/3/assets/search?page=&size=   -> các lần sync sau (sync_assets), lọc theo last-scan-date

Mỗi lần job gọi POST /assets/search ở page=0 (tức mỗi lần R7_JOB_CRON chạy), mock giả lập
một đợt scan mới: rescan ngẫu nhiên một số asset cũ (thêm history mới, đổi số lỗ hổng) và
sinh thêm asset mới, tất cả có last scan = bây giờ. Nhờ vậy mỗi lần cron chạy đều có dữ liệu
để job upsert vào MongoDB (collection r7_assets).

Chạy (mặc định HTTPS port 3780, khớp NEXPOSE_API: https://localhost:3780/api/3):
  python3 nexpose_mock_server.py
  python3 nexpose_mock_server.py --initial 200 --rescan 5 --new 3
  python3 nexpose_mock_server.py --no-tls          # chạy HTTP, đổi NEXPOSE_API sang http://
"""
import argparse
import base64
import json
import logging
import math
import os
import random
import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_DIR = os.path.join(BASE_DIR, "..", "certs")

OS_LIST = [
    # (os, family, product, systemName, vendor, version, type)
    ("Ubuntu Linux 22.04", "Linux", "Linux", "Ubuntu Linux", "Ubuntu", "22.04", "General"),
    ("Red Hat Enterprise Linux 8.6", "Linux", "Enterprise Linux", "Red Hat Enterprise Linux", "Red Hat", "8.6", "General"),
    ("CentOS Linux 7.9", "Linux", "Linux", "CentOS Linux", "CentOS", "7.9", "General"),
    ("Microsoft Windows Server 2019 Standard Edition", "Windows", "Windows Server 2019 Standard Edition",
     "Microsoft Windows", "Microsoft", "1809", "General"),
    ("Microsoft Windows 10 Enterprise Edition 22H2", "Windows", "Windows 10 Enterprise Edition",
     "Microsoft Windows", "Microsoft", "22H2", "Workstation"),
    ("Cisco IOS 15.2", "IOS", "IOS", "Cisco IOS", "Cisco", "15.2", "Router"),
]
ASSET_TYPES = ["guest", "physical", "hypervisor", "unknown"]
SERVICES = [(22, "tcp", "SSH"), (80, "tcp", "HTTP"), (443, "tcp", "HTTPS"), (445, "tcp", "CIFS"),
            (3389, "tcp", "RDP"), (9443, "tcp", "HTTPS"), (27017, "tcp", "MongoDB"), (161, "udp", "SNMP")]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class AssetStore:
    def __init__(self, initial, rescan, new, seed, base_url, tz):
        self.tz = tz
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.rescan = rescan
        self.new = new
        self.base_url = base_url
        self.next_id = 1
        self.next_scan_id = 1
        self.assets = {}
        now = datetime.now(timezone.utc)
        for _ in range(initial):
            # Asset ban đầu có lần scan cuối rải trong 30 ngày qua
            self._create(now - timedelta(seconds=self.rng.randint(0, 30 * 24 * 3600)))

    # ------------------------------------------------------------- sinh data
    def _vulns(self):
        r = self.rng
        critical, severe, moderate = r.choice([0, 0, 1, 2, 5, 12]), r.randint(0, 40), r.randint(0, 15)
        return {
            "critical": critical,
            "severe": severe,
            "moderate": moderate,
            "exploits": r.randint(0, critical),
            "malwareKits": r.choice([0, 0, 0, 1]),
            "total": critical + severe + moderate,
        }

    def _create(self, scan_time):
        r = self.rng
        aid = self.next_id
        self.next_id += 1
        os_name, family, product, system_name, vendor, version, os_type = r.choice(OS_LIST)
        ip = f"10.{r.randint(10, 30)}.{r.randint(0, 255)}.{r.randint(1, 254)}"
        mac = ":".join(f"{r.randint(0, 255):02X}" for _ in range(6))
        prefix = {"Windows": "WIN", "IOS": "rt"}.get(family, "srv")
        host = f"{prefix}-{r.choice(['app', 'db', 'web', 'ad', 'core'])}-{aid:04d}.corp.local"
        services = r.sample(SERVICES, k=r.randint(1, 4))
        cpe_ver = version.lower()
        asset = {
            "addresses": [{"ip": ip, "mac": mac}],
            "assessedForPolicies": False,
            "assessedForVulnerabilities": True,
            "history": [],
            "hostName": host,
            "hostNames": [{"name": host, "source": "dns"}],
            "id": aid,
            "ids": [{"id": f"{r.getrandbits(128):032x}", "source": "WQL"}] if family == "Windows" else [],
            "ip": ip,
            "mac": mac,
            "os": os_name,
            "osFingerprint": {
                "architecture": "x86_64",
                # Key có dấu "." như API thật -> bị sanitize_mongo_keys loại bỏ khi upsert
                "cpe": {
                    "part": "o",
                    "product": product.lower().replace(" ", "_"),
                    "v2.2": f"cpe:/o:{vendor.lower()}:{product.lower().replace(' ', '_')}:{cpe_ver}",
                    "v2.3": f"cpe:2.3:o:{vendor.lower()}:{product.lower().replace(' ', '_')}:{cpe_ver}:*:*:*:*:*:*:*",
                    "vendor": vendor.lower(),
                    "version": cpe_ver,
                },
                "description": os_name,
                "family": family,
                "id": r.randint(1, 500),
                "product": product,
                "systemName": system_name,
                "type": os_type,
                "vendor": vendor,
                "version": version,
            },
            "services": [{"port": p, "protocol": proto, "name": name,
                          "links": [{"href": f"{self.base_url}/assets/{aid}/services/{proto}/{p}", "rel": "self"}]}
                         for p, proto, name in services],
            "type": r.choice(ASSET_TYPES),
            "links": [{"href": f"{self.base_url}/assets/{aid}", "rel": "self"}],
        }
        self.assets[aid] = asset
        self._scan(asset, scan_time)
        return asset

    def _scan(self, asset, scan_time):
        r = self.rng
        asset["history"].append({
            "date": iso(scan_time),
            "description": "",
            "scanId": self.next_scan_id,
            "type": "SCAN",
            "user": "",
            "version": len(asset["history"]) + 1,
            "vulnerabilityExceptionId": 0,
        })
        self.next_scan_id += 1
        vulns = self._vulns()
        asset["vulnerabilities"] = vulns
        raw = vulns["critical"] * 900 + vulns["severe"] * 400 + vulns["moderate"] * 120 + r.uniform(0, 500)
        asset["rawRiskScore"] = round(raw, 5)
        asset["riskScore"] = round(raw * r.uniform(1.0, 1.3), 5)

    def simulate_new_scan(self):
        """Mỗi lần cron gọi search: rescan một số asset cũ + phát hiện asset mới."""
        now = datetime.now(timezone.utc)
        existing = list(self.assets.values())
        rescanned = self.rng.sample(existing, k=min(self.rescan, len(existing)))
        for a in rescanned:
            self._scan(a, now)
        created = [self._create(now) for _ in range(self.new)]
        logging.info("Simulated scan: rescanned ids=%s, new ids=%s",
                     [a["id"] for a in rescanned], [a["id"] for a in created])

    # ------------------------------------------------------------- truy vấn
    def _last_scan_date(self, asset):
        # Nexpose so sánh ngày theo timezone của console, job gửi ngày theo JOB_TZ
        if not asset["history"]:
            return None
        dt = datetime.strptime(asset["history"][-1]["date"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(self.tz).strftime("%Y-%m-%d")

    def search(self, body):
        filters = (body or {}).get("filters", [])
        match_all = (body or {}).get("match", "all") == "all"

        def check(asset, f):
            if f.get("field") != "last-scan-date":
                return True  # field khác: mock bỏ qua (coi như khớp)
            d, value, op = self._last_scan_date(asset), str(f.get("value", ""))[:10], f.get("operator")
            if d is None:
                return False
            if op == "is-on-or-after":
                return d >= value
            if op == "is-on-or-before":
                return d <= value
            if op == "is":
                return d == value
            if op == "is-within-the-last":
                return d >= (datetime.now(self.tz) - timedelta(days=int(value or 0))).strftime("%Y-%m-%d")
            return True

        result = []
        for a in self.assets.values():
            checks = [check(a, f) for f in filters]
            if not filters or (all(checks) if match_all else any(checks)):
                result.append(a)
        return result


def page_response(items, page, size, path, base_url):
    total = len(items)
    total_pages = math.ceil(total / size) if size else 0
    resources = items[page * size:(page + 1) * size]
    links = [{"href": f"{base_url}{path}?page={page}&size={size}", "rel": "self"},
             {"href": f"{base_url}{path}?page=0&size={size}", "rel": "first"}]
    if page + 1 < total_pages:
        links.append({"href": f"{base_url}{path}?page={page + 1}&size={size}", "rel": "next"})
    if total_pages:
        links.append({"href": f"{base_url}{path}?page={total_pages - 1}&size={size}", "rel": "last"})
    return {
        "links": links,
        "page": {"number": page, "size": size, "totalPages": total_pages, "totalResources": total},
        "resources": resources,
    }


def make_handler(store, username, password, base_url):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.info("%s - %s", self.address_string(), fmt % args)

        def _send(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json;charset=UTF-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            header = self.headers.get("Authorization", "")
            if not header.startswith("Basic "):
                return False
            if username is None:
                return True
            try:
                user, _, pwd = base64.b64decode(header[6:]).decode().partition(":")
            except Exception:
                return False
            return user == username and pwd == password

        def _paging(self, query):
            try:
                page = int(query.get("page", ["0"])[0])
                size = int(query.get("size", ["10"])[0])
            except ValueError:
                return None
            if page < 0 or size < 1 or size > 500:
                return None
            return page, size

        def _handle(self, method):
            url = urlparse(self.path)
            if not self._authorized():
                return self._send(401, {"status": 401, "message": "Unauthorized",
                                        "links": [{"href": base_url, "rel": "self"}]})
            paging = self._paging(parse_qs(url.query))
            if paging is None:
                return self._send(400, {"status": 400, "message": "Invalid page or size parameter"})
            page, size = paging

            if method == "GET" and url.path == "/api/3/assets":
                with store.lock:
                    items = sorted(store.assets.values(), key=lambda a: a["id"])
                    return self._send(200, page_response(items, page, size, "/assets", base_url))

            if method == "POST" and url.path == "/api/3/assets/search":
                length = int(self.headers.get("Content-Length", 0) or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, {"status": 400, "message": "Malformed JSON body"})
                logging.info("Search body: %s", json.dumps(body))
                with store.lock:
                    if page == 0:
                        store.simulate_new_scan()
                    items = sorted(store.search(body), key=lambda a: a["id"])
                    return self._send(200, page_response(items, page, size, "/assets/search", base_url))

            return self._send(404, {"status": 404, "message": f"No resource found for {method} {url.path}"})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


def main():
    p = argparse.ArgumentParser(description="Mock Rapid7 Nexpose API v3")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=3780)
    p.add_argument("--initial", type=int, default=120, help="số asset có sẵn lúc khởi động")
    p.add_argument("--rescan", type=int, default=5, help="số asset cũ được rescan mỗi lần cron gọi search")
    p.add_argument("--new", type=int, default=2, help="số asset mới phát hiện mỗi lần cron gọi search")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--tz", default="Asia/Ho_Chi_Minh", help="timezone dùng để so sánh last-scan-date (khớp JOB_TZ)")
    p.add_argument("--user", default=None, help="chỉ chấp nhận đúng user này (mặc định: mọi Basic Auth)")
    p.add_argument("--password", default=None)
    p.add_argument("--no-tls", action="store_true")
    p.add_argument("--cert", default=os.path.join(CERT_DIR, "server.crt"))
    p.add_argument("--key", default=os.path.join(CERT_DIR, "server.key"))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    scheme = "http" if args.no_tls else "https"
    base_url = f"{scheme}://localhost:{args.port}/api/3"
    store = AssetStore(args.initial, args.rescan, args.new, args.seed, base_url, ZoneInfo(args.tz))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store, args.user, args.password, base_url))
    if not args.no_tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(args.cert, args.key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    logging.info("Nexpose mock listening on %s (%d assets)", base_url, len(store.assets))
    server.serve_forever()


if __name__ == "__main__":
    main()
