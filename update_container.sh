#!/bin/bash
# Script cập nhật nhanh code Python vào container đang chạy
# Chạy từ thư mục gốc của project mock_server
# Usage: bash update_container.sh [container_name]

CONTAINER=${1:-cloud-mock-server-8881}

echo "=== Cập nhật container: $CONTAINER ==="

# Kiểm tra container đang chạy
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: Container $CONTAINER không tìm thấy hoặc không đang chạy"
    docker ps --format 'table {{.Names}}\t{{.Status}}'
    exit 1
fi

# Copy các file đã sửa vào container
echo ">> Copy src/event_hubs_broker.py ..."
docker cp src/event_hubs_broker.py ${CONTAINER}:/app/src/event_hubs_broker.py

echo ">> Copy src/amqp_codec.py ..."
docker cp src/amqp_codec.py ${CONTAINER}:/app/src/amqp_codec.py

echo ">> Copy src/proxy_handler.py ..."
docker cp src/proxy_handler.py ${CONTAINER}:/app/src/proxy_handler.py

echo ">> Copy streams/azure_event_hubs.json ..."
docker cp streams/azure_event_hubs.json ${CONTAINER}:/app/streams/azure_event_hubs.json

# Fix line endings (nếu cần)
echo ">> Fix line endings trong container ..."
docker exec ${CONTAINER} bash -c "sed -i 's/\r$//' /app/src/event_hubs_broker.py /app/src/amqp_codec.py /app/src/proxy_handler.py"

echo ">> Restart container ..."
docker restart ${CONTAINER}

echo "=== Done! Chờ container khởi động lại... ==="
sleep 3
docker logs ${CONTAINER} --tail 30
