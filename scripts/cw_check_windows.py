#!/usr/bin/env python3
"""
Đọc request log của mock (Admin API) và in các lần shipper gọi CloudWatch FilterLogEvents:
thời điểm, startTime/endTime, nextToken, status, rule khớp.
Đồng thời kiểm tra mốc checkpoint giữa các chu kỳ:
  - Chu kỳ trước thành công  -> startTime mới phải = endTime cũ + 1 (Time-Window Advance)
  - Chu kỳ trước lỗi         -> startTime mới phải = startTime cũ (giữ nguyên mốc)

Dùng: python3 scripts/cw_check_windows.py [--port 8081] [--limit 500]
"""
import argparse
import json
import urllib.request
from datetime import datetime, timezone


def fmt(ms):
    if ms is None:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    url = f"http://localhost:{args.port}/mock/admin/api/logs?limit={args.limit}"
    logs = json.load(urllib.request.urlopen(url))["logs"]

    calls = []
    for l in reversed(logs):  # cũ -> mới
        target = next((v for k, v in l.get("request_headers", {}).items() if k.lower() == "x-amz-target"), "")
        if not target.endswith("FilterLogEvents"):
            continue
        try:
            body = json.loads(l.get("request_body") or "{}")
        except json.JSONDecodeError:
            body = {}
        calls.append({
            "at": l["timestamp"], "status": l["status"], "rule": l["matched_rule"],
            "start": body.get("startTime"), "end": body.get("endTime"),
            "token": body.get("nextToken"), "group": body.get("logGroupName"),
        })

    if not calls:
        print("Chưa có request FilterLogEvents nào trong log của mock.")
        return

    print(f"{'Thời điểm':19} {'St':>4} {'startTime (UTC)':>15} {'endTime (UTC)':>15} {'nextToken':14} Rule")
    for c in calls:
        print(f"{c['at']:19} {c['status']:>4} {fmt(c['start']):>15} {fmt(c['end']):>15} {str(c['token'] or '-'):14} {c['rule']}")

    # Gom theo chu kỳ: 1 chu kỳ = các request cùng (startTime, endTime)
    cycles = []
    for c in calls:
        key = (c["start"], c["end"])
        if cycles and (cycles[-1]["key"] == key or c["start"] is None):
            cycles[-1]["calls"].append(c)
        else:
            cycles.append({"key": key, "calls": [c]})

    print("\nKiểm tra checkpoint giữa các chu kỳ:")
    for prev, cur in zip(cycles, cycles[1:]):
        p_start, p_end = prev["key"]
        c_start, _ = cur["key"]
        prev_ok = prev["calls"][-1]["status"] == 200
        if p_start is None or c_start is None:
            continue
        if p_end is not None and c_start == p_end + 1:
            verdict = "OK  tiến mốc = endTime cũ + 1"
        elif c_start == p_start:
            verdict = "OK  giữ nguyên mốc (chu kỳ trước lỗi)" if not prev_ok else "LỆCH chu kỳ trước thành công nhưng mốc không tiến"
        elif p_end is not None and c_start <= p_end:
            verdict = f"TRÙNG cửa sổ chồng lấn {p_end - c_start + 1} ms"
        else:
            verdict = f"HỔNG bỏ sót {c_start - p_end - 1} ms" if p_end is not None else "?"
        print(f"  {fmt(p_start)}..{fmt(p_end)}  ->  start {fmt(c_start)}  : {verdict}")


if __name__ == "__main__":
    main()
