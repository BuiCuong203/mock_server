#!/usr/bin/env bash
# Script tiện ích quản trị Cloud Mock Server

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BASE_DIR/.server.pid"
LOG_FILE="$BASE_DIR/server.log"
PORT="${PORT:-8081}"

start_foreground() {
    echo "⚡ Khởi động Cloud Mock Server ở chế độ foreground (Port $PORT)..."
    python3 "$BASE_DIR/server.py" --port "$PORT" "$@"
}

start_background() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "⚠️  Cloud Mock Server đã đang chạy với PID $(cat "$PID_FILE")"
        exit 0
    fi

    echo "⚡ Khởi động Cloud Mock Server ở chế độ background daemon (Port $PORT)..."
    python3 "$BASE_DIR/server.py" --port "$PORT" --daemon "$@"
    sleep 1

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "✅ Server đã khởi động thành công (PID: $(cat "$PID_FILE"))"
        echo "📊 Web Dashboard : http://localhost:$PORT/mock/admin/"
        echo "📝 File log      : $LOG_FILE"
    else
        echo "❌ Lỗi: Server không thể khởi động! Kiểm tra log tại $LOG_FILE"
        cat "$LOG_FILE" 2>/dev/null || true
        exit 1
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID="$(cat "$PID_FILE")"
        if kill -0 "$PID" 2>/dev/null; then
            echo "🛑 Đang tắt Cloud Mock Server (PID: $PID)..."
            kill "$PID" 2>/dev/null
            sleep 1
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
            echo "✅ Đã tắt server thành công."
        fi
        rm -f "$PID_FILE"
    fi

    # Đảm bảo giải phóng port nếu còn tiến trình nào chiếm giữ
    fuser -k "$PORT/tcp" 2>/dev/null || true
    echo "✅ Port $PORT đã sẵn sàng."
}

status_server() {
    API_STATUS=$(curl -s "http://localhost:$PORT/mock/admin/api/status" 2>/dev/null || true)
    if [ -n "$API_STATUS" ] && [[ "$API_STATUS" == *"online"* ]]; then
        echo "🟢 Cloud Mock Server ĐANG CHẠY TRÊN PORT $PORT"
        echo "$API_STATUS" | python3 -m json.tool
    else
        echo "🔴 Cloud Mock Server ĐANG TẮT (Không kết nối được tới http://localhost:$PORT)"
    fi
}

test_endpoints() {
    echo "🧪 Đang kiểm thử các endpoints của Mock Cloud Server..."
    echo "--------------------------------------------------------"
    echo "1. Kiểm tra Web Dashboard:"
    curl -s -I "http://localhost:$PORT/mock/admin/" | head -n 1

    echo "2. Kiểm tra Admin Status API:"
    curl -s "http://localhost:$PORT/mock/admin/api/status" | python3 -m json.tool

    echo "3. Kiểm tra REST API Logs:"
    curl -s "http://localhost:$PORT/mock/rest_api/logs" | head -n 12

    echo "4. Kiểm tra Azure Poller Logs:"
    curl -s "http://localhost:$PORT/mock/azure/auditLogs/signIns" | head -n 12

    echo "5. Kiểm tra Defender Alerts:"
    curl -s "http://localhost:$PORT/mock/defender/alerts" | head -n 12

    echo "--------------------------------------------------------"
    echo "✅ Hoàn tất kiểm thử cơ bản!"
}

case "$1" in
    start)
        shift
        if [ "$1" == "-d" ]; then
            shift
            start_background "$@"
        else
            start_foreground "$@"
        fi
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        shift
        start_background "$@"
        ;;
    status)
        status_server
        ;;
    test)
        test_endpoints
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        start_foreground "$@"
        ;;
esac
