#!/usr/bin/env python3
"""
Cloud Mock Server - Standalone Mock Server for Cloud Log Sources
Hỗ trợ 6 loại Cloud Log Source:
1. REST API
2. Azure Poller
3. Microsoft Defender (EDR)
4. Microsoft 365
5. AWS CloudWatch Logs
6. AWS S3-SQS
+ Alibaba SLS (log_service_alibaba) và GCP Pub/Sub (gcp_pubsub, gRPC cổng 8085, chạy kèm binary pubsub_mock)

Tích hợp:
- Web Dashboard & Request Inspector: http://localhost:8081/mock/admin/
- Admin REST API điều khiển kịch bản & rules linh hoạt
- HTTP Proxy CONNECT TLS Tunneling
- Dynamic Response Templating
"""

import sys
import argparse
import signal
from http.server import ThreadingHTTPServer

from src.config import (
    DEFAULT_PORT, DEFAULT_HOST, GREEN, CYAN, MAGENTA, YELLOW, BOLD, RESET
)
from src.cert_manager import ensure_certificates
from src.scenario_manager import scenario_manager
from src.proxy_handler import MockCloudHandler
from src import pubsub_runner


def main():
    parser = argparse.ArgumentParser(description="Cloud Mock Server for CyM-Log-Shipper")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"Port lắng nghe (mặc định: {DEFAULT_PORT})")
    parser.add_argument("-H", "--host", type=str, default=DEFAULT_HOST, help=f"Host bind (mặc định: {DEFAULT_HOST})")
    parser.add_argument("-s", "--scenario", type=str, default="default", help="Kịch bản khởi động mặc định (ví dụ: default, rate_limit_429, auth_fail_401)")
    parser.add_argument("-d", "--daemon", action="store_true", help="Chạy ở chế độ background daemon tách biệt terminal")
    args = parser.parse_args()

    # 1. Đảm bảo chứng chỉ SSL hợp lệ
    ensure_certificates()

    # 2. Đặt kịch bản ban đầu
    scenario_manager.set_active_scenario(args.scenario)

    if args.daemon:
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pid_file = os.path.join(base_dir, ".server.pid")
        log_file = os.path.join(base_dir, "server.log")

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.exit(1)

        os.setsid()

        try:
            pid = os.fork()
            if pid > 0:
                with open(pid_file, "w") as f:
                    f.write(str(pid))
                sys.exit(0)
        except OSError as e:
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()
        so = open(log_file, "a+", buffering=1)
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(so.fileno(), sys.stderr.fileno())

    # GCP Pub/Sub (binary Go chạy kèm) - khởi động sau khi đã tách daemon để tiến trình con thuộc daemon
    pubsub_ok = pubsub_runner.start()

    ThreadingHTTPServer.allow_reuse_address = True
    server_address = (args.host, args.port)
    httpd = ThreadingHTTPServer(server_address, MockCloudHandler)

    print("\n" + "=" * 76)
    print(f"{GREEN}{BOLD}⚡ CLOUD MOCK SERVER ĐÃ SẴN SÀNG TẠI PORT {args.port}{RESET}")
    print("=" * 76)
    print(f"📊 {BOLD}Web Dashboard & Inspector{RESET} : {CYAN}http://localhost:{args.port}/mock/admin/{RESET}")
    print(f"🎭 {BOLD}Kịch bản đang hoạt động{RESET}    : {MAGENTA}{scenario_manager.active_scenario_name}{RESET}")
    print("-" * 76)
    print(f"{BOLD}Direct Endpoints & Proxy Ports:{RESET}")
    print(f"  • {YELLOW}REST API Generic{RESET}     : GET  http://localhost:{args.port}/mock/rest_api/logs")
    print(f"  • {YELLOW}Azure Poller{RESET}         : GET  http://localhost:{args.port}/mock/azure/auditLogs/signIns")
    print(f"  • {YELLOW}Microsoft Defender{RESET}   : GET  http://localhost:{args.port}/mock/defender/alerts")
    print(f"  • {YELLOW}Microsoft 365 (Proxy){RESET} : CONNECT -> manage.office.com / login.microsoftonline.com")
    print(f"  • {YELLOW}AWS CloudWatch (Proxy){RESET}: CONNECT -> logs.us-east-1.amazonaws.com")
    print(f"  • {YELLOW}AWS S3-SQS (Proxy){RESET}    : CONNECT -> sqs.us-east-1.amazonaws.com & s3")
    print(f"  • {YELLOW}Alibaba SLS{RESET}           : HTTP proxy -> <project>.<region>.log.aliyuncs.com")
    if pubsub_ok:
        print(f"  • {YELLOW}GCP Pub/Sub (gRPC){RESET}    : cổng {pubsub_runner.GRPC_PORT} -> shipper đặt PUBSUB_EMULATOR_HOST=<ip-mock>:{pubsub_runner.GRPC_PORT}")
    else:
        print(f"  • {YELLOW}GCP Pub/Sub{RESET}           : KHÔNG chạy ({pubsub_runner.status().get('error')})")
    print("=" * 76)
    print("Đang lắng nghe requests từ CyM-Log-Shipper... (Nhấn Ctrl+C để dừng)\n")

    def signal_handler(sig, frame):
        print(f"\n{YELLOW}Đang dừng Cloud Mock Server...{RESET}")
        pubsub_runner.stop()
        httpd.server_close()
        print(f"{GREEN}Đã tắt server thành công.{RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
