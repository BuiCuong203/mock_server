# Mock Sender: 2 batch x 10 event qua TLS -> input beats 127.0.0.1:15045
curl -s -X POST 'http://localhost:18081/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "127.0.0.1", "port": 15045, "tls": true, "batch_size": 10,
  "count": 2, "rate": 1, "user": "e2e", "action": "BEATS_TLS"
}'
