# Mock Sender (type beats) -> <IP máy chạy shipper>:15046 (mock trong Docker: IP gateway, vd 172.22.0.1): 1 batch x 3 event, log mẫu Filebeat
curl -s -X POST 'http://localhost:8881/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "172.22.0.1", "port": 15046, "batch_size": 3, "count": 1, "rate": 1,
  "user": "e2e", "action": "BEATS_DEFAULT"
}'
