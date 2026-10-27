# Mock Sender: 5 request x 10 log -> POST http://127.0.0.1:18086/log
curl -s -X POST 'http://localhost:18081/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "http", "host": "127.0.0.1", "port": 18086, "path": "/log", "batch_size": 10,
  "count": 5, "rate": 2, "user": "e2e", "action": "HTTP_PUSH"
}'
