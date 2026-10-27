#!/usr/bin/env bash
# Chạy CyM-Log-Shipper thật với 1 nguồn log, đọc dữ liệu từ Cloud Mock Server, in event ra stdout.
#
#   e2e/run_e2e.sh <nguồn> [số_giây]          # vd: e2e/run_e2e.sh gcp_pubsub 40
#   e2e/run_e2e.sh list                        # liệt kê các nguồn có sẵn
#
# Biến môi trường:
#   SHIPPER_BIN  binary shipper (mặc định ../test-cym-log-shipper/cym-log-shipper, cạnh librure.so)
#   MOCK_URL     URL mock server (mặc định http://localhost:8081)
#   SIEM_PORT    cổng SIEM-API stub (mặc định 18090), MONGO_PORT cổng mock Mongo (mặc định 27027)
#   LOG_LEVEL    INFO | DEBUG (mặc định INFO)
set -u

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$E2E_DIR")"
SHIPPER_BIN="${SHIPPER_BIN:-$ROOT_DIR/../test-cym-log-shipper/cym-log-shipper}"
MOCK_URL="${MOCK_URL:-http://localhost:8081}"
SIEM_PORT="${SIEM_PORT:-18090}"
MONGO_PORT="${MONGO_PORT:-27027}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

SOURCE="${1:-}"
DURATION="${2:-40}"

if [ -z "$SOURCE" ] || [ "$SOURCE" = "list" ]; then
    echo "Các nguồn có sẵn:"
    for f in "$E2E_DIR"/conf/*.yml; do
        n="$(basename "$f" .yml)"; [ "$n" = "config" ] || echo "  - $n"
    done
    exit 0
fi

CONF_TPL="$E2E_DIR/conf/$SOURCE.yml"
[ -f "$CONF_TPL" ] || { echo "Không có cấu hình $CONF_TPL"; exit 1; }
[ -x "$SHIPPER_BIN" ] || { echo "Không tìm thấy binary shipper: $SHIPPER_BIN (đặt SHIPPER_BIN=...)"; exit 1; }

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

STARTED_PIDS=()
cleanup() {
    for p in "${STARTED_PIDS[@]}"; do kill "$p" 2>/dev/null; done
}
trap cleanup EXIT

if ! port_open "$SIEM_PORT"; then
    python3 "$E2E_DIR/siem_api_stub.py" "$SIEM_PORT" >/dev/null 2>&1 &
    STARTED_PIDS+=($!)
fi
if ! port_open "$MONGO_PORT"; then
    python3 "$E2E_DIR/mock_mongo.py" "$MONGO_PORT" >/dev/null 2>&1 &
    STARTED_PIDS+=($!)
fi
sleep 0.5

MOCK_HOSTPORT="${MOCK_URL#*://}"
MOCK_HOSTPORT="${MOCK_HOSTPORT%%/*}"
MOCK_HOST="${MOCK_HOSTPORT%%:*}"
MOCK_PORT="${MOCK_HOSTPORT##*:}"

RUN_DIR="$E2E_DIR/.run/$SOURCE"
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR/conf.d" "$RUN_DIR/data"
render() {
    sed -e "s#__MOCK_URL__#$MOCK_URL#g" -e "s#__MOCK_HOSTPORT__#$MOCK_HOSTPORT#g" \
        -e "s#__MOCK_HOST__#$MOCK_HOST#g" -e "s#__MOCK_PORT__#$MOCK_PORT#g" \
        -e "s#__SIEM_PORT__#$SIEM_PORT#g" -e "s#__ROOT_DIR__#$ROOT_DIR#g" -e "s#__SHIPPER_HOST__#${SHIPPER_HOST:-127.0.0.1}#g" -e "s#__LOG_LEVEL__#$LOG_LEVEL#g" "$1"
}
render "$E2E_DIR/conf/config.yml" > "$RUN_DIR/conf.d/config.yml"
render "$CONF_TPL" > "$RUN_DIR/conf.d/cym.yml"

export LD_LIBRARY_PATH="$(dirname "$SHIPPER_BIN"):${LD_LIBRARY_PATH:-}"
export SIEM_MONGO_URI="mongodb://127.0.0.1:$MONGO_PORT"
export SSL_CERT_FILE="$ROOT_DIR/certs/ca-bundle.crt"
export INTERVAL="${INTERVAL:-1}"
# Biến môi trường riêng từng nguồn (vd: PUBSUB_EMULATOR_HOST, PUB_KEY...)
if [ -f "$E2E_DIR/conf/$SOURCE.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(render "$E2E_DIR/conf/$SOURCE.env")
    set +a
fi

LOG_FILE="$RUN_DIR/shipper.log"
echo "▶ $SOURCE: chạy shipper ${DURATION}s (mock: $MOCK_URL) — log: $LOG_FILE"
# Nguồn kiểu push (http...): conf/<nguồn>.after.sh ra lệnh cho mock bắn log sau khi shipper đã khởi động
if [ -f "$E2E_DIR/conf/$SOURCE.after.sh" ]; then
    render "$E2E_DIR/conf/$SOURCE.after.sh" > "$RUN_DIR/after.sh"
    (sleep "${AFTER_DELAY:-5}"; bash "$RUN_DIR/after.sh" > "$RUN_DIR/after.log" 2>&1) &
fi
(cd "$RUN_DIR" && timeout "$DURATION" "$SHIPPER_BIN" run --config-dir conf.d > "$LOG_FILE" 2>&1)

EVENTS=$(grep -v "^time=" "$LOG_FILE" | grep -c "e2e $SOURCE" || true)
ERRORS=$(grep -ciE "level=error|level=fatal|panic" "$LOG_FILE" || true)
echo "  event nhận được: $EVENTS | dòng lỗi: $ERRORS"
if [ "$EVENTS" -gt 0 ]; then
    echo "  ví dụ event:"
    grep -v "^time=" "$LOG_FILE" | grep -m 2 "e2e $SOURCE" | cut -c1-400 | sed 's/^/    /'
    exit 0
fi
echo "  ❌ không nhận được event nào. 20 dòng log cuối:"
tail -n 20 "$LOG_FILE" | cut -c1-300 | sed 's/^/    /'
exit 1
