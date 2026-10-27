# 1 batch log mẫu MỚI (log_parser web_access) + 1 batch log kiểu CŨ (type nginx_access)
curl -s -X POST 'http://localhost:18081/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "127.0.0.1", "port": 15047, "batch_size": 2, "count": 1, "rate": 1, "user": "new_template"}'
curl -s -X POST 'http://localhost:18081/mock/admin/api/sender/jobs' -H 'Content-Type: application/json' -d '{
  "type": "beats", "host": "127.0.0.1", "port": 15047, "batch_size": 2, "count": 1, "rate": 1,
  "message": "{\"message\": \"old {{SEQ}}\", \"beat\": {\"name\": \"mock-filebeat-01\"}, \"source\": \"/var/log/nginx/access.log\", \"type\": \"nginx_access\", \"user\": \"old_template\"}"}'
