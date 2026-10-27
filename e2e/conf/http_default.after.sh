# Mock Sender (type http) -> <IP shipper>:18080/log, 2 request x 3 log
curl -s -X POST '__MOCK_URL__/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "http", "host": "__SHIPPER_HOST__", "port": 18080, "path": "/log", "batch_size": 3,
  "count": 2, "rate": 1, "user": "e2e", "action": "HTTP_DEFAULT"
}'
