#!/usr/bin/env bash
# Đổi nhanh kịch bản CloudWatch trên mock server.
#   ./scripts/cw_scenario.sh list            # liệt kê các kịch bản cw_*
#   ./scripts/cw_scenario.sh <tên kịch bản>  # bật kịch bản (vd: cw_06_throttling) và xóa request log cũ
#   ./scripts/cw_scenario.sh reset           # quay về kịch bản default
#   ./scripts/cw_scenario.sh check           # in cửa sổ startTime/endTime shipper đã gửi và kiểm tra checkpoint
PORT="${PORT:-8081}"
API="http://localhost:$PORT/mock/admin/api"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$1" in
    ""|list)
        curl -s "$API/scenarios" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for s in d["scenarios"]:
    if s["name"].startswith("cw_"):
        print(("* " if s["is_active"] else "  ")+s["name"].ljust(34)+s["description"])'
        ;;
    reset)
        curl -s -X POST "$API/scenarios/switch" -d '{"scenario":"default"}' | python3 -m json.tool
        ;;
    check)
        python3 "$DIR/cw_check_windows.py" --port "$PORT"
        ;;
    *)
        curl -s -X POST "$API/scenarios/reload" > /dev/null
        curl -s -X POST "$API/scenarios/switch" -d "{\"scenario\":\"$1\"}" | python3 -m json.tool
        curl -s -X POST "$API/logs/clear" > /dev/null
        echo "Đã xóa request log cũ của mock."
        ;;
esac
