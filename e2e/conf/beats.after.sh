# Mock Sender: 3 batch x 20 event (nén zlib) + 2 batch x 5 event (không nén) -> input beats 127.0.0.1:15044
curl -s -X POST '__MOCK_URL__/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "127.0.0.1", "port": 15044, "batch_size": 20, "compress": true,
  "count": 3, "rate": 1, "user": "e2e", "action": "BEATS_ZLIB"
}'
curl -s -X POST '__MOCK_URL__/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "127.0.0.1", "port": 15044, "batch_size": 5, "compress": false,
  "count": 2, "rate": 1, "user": "e2e", "action": "BEATS_PLAIN"
}'
