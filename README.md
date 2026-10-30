# Cloud Mock Server: mock input cho CyM-Log-Shipper

Tài liệu bàn giao, ngày 16/10/2026. Ghi lại những gì đã làm được, những gì chưa làm, và cách chạy thử từng nguồn với binary shipper thật.

Binary dùng để test: `../test-cym-log-shipper/cym-log-shipper` (cần `librure.so` nằm cùng thư mục).

## 1. Tổng quan 11 nguồn

| # | Nguồn (`type` trong cym.yml) | Trạng thái | Kết quả e2e với shipper thật | Cách shipper tới mock |
|---|---|---|---|---|
| 1 | `rest_api` | Có sẵn. Đã sinh lại dataset | 627 event / 75s | Gọi thẳng `http://<mock>/mock/rest_api/logs` |
| 2 | `azure` (Azure Poller) | Có sẵn. Đã sinh lại dataset | 305 event / 75s | `proxy_url`, HTTPS MITM |
| 3 | `microsoft_defender` | Có sẵn | 13200 event / 75s | `alert_url` thẳng vào mock + `proxy_url` |
| 4 | `microsoft365` | Có sẵn. Đã sinh lại dataset | 6240 event / 75s | `proxy_url`, HTTPS MITM |
| 5 | `cloudwatch` | Có sẵn | 161 event / 20s | `proxy_url`, HTTPS MITM |
| 6 | `aws_s3sqs` | Có sẵn | 50 event / 75s | `proxy_url`, HTTPS MITM |
| 7 | `log_service_alibaba` | **Mới, xong** | 1296 event / 25s | `proxy_url`, HTTP thường |
| 8 | `http` | **Mới, xong** | 50 event (5 request × 10) | Mock Sender POST vào cổng shipper |
| 9 | `gcp_pubsub` | **Mới, xong** | 63/65 message (65 đã ack) | `PUBSUB_EMULATOR_HOST`, binary `pubsub_mock` |
| 10 | `azure_event_hubs` | **Mới, xong** (xem mục 4) | AMQP 1.0 qua WebSocket + Blob lease | `proxy_url`, HTTPS CONNECT |
| 11 | `wmi` (input `msrpc`) | **CHƯA LÀM** (xem mục 5) | – | – |
| + | `beats` (thêm ngày 17/10) | **Mới, xong** | 70/70 event (có nén + không nén); TLS 20/20 | Mock Sender giả làm Filebeat, Lumberjack v2 |

## 2. Những việc đã làm

### 2.1. Sửa lỗi dataset hết hạn: nguyên nhân rest_api, azure, m365 trả 0 event

Dataset của scenario `default` có mốc thời gian cố định, chỉ phủ đến 13/10. Ở chế độ realtime, mock lọc theo `since=now`, nên sau mốc đó không còn bản ghi nào để trả.

Đã sinh lại 4 dataset:

```bash
python3 generate_default_datasets.py --only rest_v1,azure,azure_audits,m365
```

> ⚠️ Dataset mới phủ đến **22/10/2026**. Sau ngày này phải chạy lại lệnh trên (bỏ `--only` để sinh lại tất cả), nếu không 3 nguồn này lại trả 0 event.

### 2.2. `log_service_alibaba` (Alibaba SLS)

- Mã nguồn: `src/sls_mock.py`; rule: `rules/07_log_service_alibaba.json` (rule base, áp dụng cho mọi scenario).
- Giả lập các API mà consumer group của `aliyun-log-go-sdk` gọi:
  - ListConsumerGroup, CreateConsumerGroup, UpdateConsumerGroup
  - HeartBeat (chia shard cho các consumer)
  - GetCheckpoint, UpdateCheckpoint
  - ListShards, GetCursor (`begin` / `end` / theo thời gian)
  - PullLogs: trả LogGroupList dạng protobuf, nén LZ4. Cả hai đều tự mã hoá bằng Python thuần, không cần thư viện.
- Log sinh đều theo thời gian. Rule có các tham số:
  - `shards`, `rate_per_shard` (log/giây)
  - `backlog_seconds`: lượng log có sẵn khi đọc từ `begin`
  - `log_group_size`, `topic`, `source`
  - `templates` / `template` / `dataset_file`: nội dung log
- Mỗi log có trường `seq`, dùng để kiểm tra mất hay trùng log khi đọc lại từ checkpoint.
- Lỗi 401/403/500 giả lập bằng cách đặt một rule thường lên trước, theo đúng cơ chế scenario sẵn có.
- Config shipper:

  ```yaml
  - type: log_service_alibaba
    endpoint: "cn-hangzhou.log.aliyuncs.com"   # giữ endpoint thật
    proxy_url: "http://<ip-mock>:8081"          # mọi request SLS đi qua mock
    access_id: "bất kỳ"
    access_key: "bất kỳ"
    project: "mock-project"
    logstore: "actiontrail-log"
    consumer_group: "cym-consumer-group"
    consumer_name: "cym-consumer-01"
    position: "begin"                           # hoặc "end"
    log_type: "alibaba_actiontrail"
  ```

  > Chế độ `endpoint: "127.0.0.1:8081"` (SDK tự dùng IP làm proxy) **không chạy** với binary hiện tại, vì shipper vẫn gọi DNS tới `mock-project.127.0.0.1`. Phải dùng `proxy_url` như trên.
- Admin API:
  - `GET /mock/admin/api/streams`: trạng thái logstore, consumer group, checkpoint.
  - `POST /mock/admin/api/streams/sls/inject` với body `{"project","logstore","count"}`: bơm thêm log.

### 2.3. `http` (shipper là HTTP server, mock đẩy log vào)

- Mã nguồn: `src/http_input_keys.py` (khoá + token) và loại `http` mới trong `src/mock_sender.py`.
- Shipper bắt buộc có 3 biến môi trường `PUB_KEY`, `SSL_CERT`, `SSL_KEY`, và header `X-API-KEY` là token ký RSA khớp với `PUB_KEY`.
  - Mock tự sinh cặp khoá ký tại `certs/http_input/`.
  - Lấy 3 biến cho shipper (export trước khi chạy shipper):

    ```bash
    eval "$(curl -s http://<ip-mock>:8081/mock/admin/api/http_input/env?format=shell)"
    ```

  - Lấy token để test bằng curl: `GET /mock/admin/api/http_input/token`.
- Gửi log bằng Mock Sender (Admin API). Mỗi request là một mảng JSON gồm `batch_size` log:

  ```bash
  curl -X POST http://<ip-mock>:8081/mock/admin/api/sender/jobs -H 'Content-Type: application/json' -d '{
    "type": "http", "host": "<ip-shipper>", "port": 8080, "path": "/log",
    "batch_size": 10, "count": 5, "rate": 2, "tls": false
  }'
  ```

- `path: /data` đẩy log sang NATS chứ không vào pipeline. Lỗi `Open file Nats Config fail` trong log shipper là bình thường khi không dùng NATS.
- Dashboard: tab Mock Sender có chế độ **HTTP**, nút "⚙ Điền cấu hình mẫu" và "🔑 Lấy biến môi trường cho shipper". Phần xem trước sinh sẵn đoạn `cym.yml` cho input http.

### 2.4. `gcp_pubsub` (tích hợp sẵn trong mock, từ 19/10)

- Mã nguồn: `pubsub_mock/main.go` (Go, dựng trên `pstest` của Google) + `src/pubsub_runner.py` (server.py tự chạy kèm / tắt theo).
- Image Docker tự build `pubsub_mock` (stage `golang:1.25`, binary tĩnh `/app/bin/pubsub_mock`). Chạy không Docker:
  `cd pubsub_mock && CGO_ENABLED=0 go build -o ../bin/pubsub_mock .`
- Cổng gRPC **8085** (mở ra ngoài, nghe mọi địa chỉ). Cổng quản trị nội bộ 18086 (chỉ 127.0.0.1).
  Biến môi trường mock: `PUBSUB_ENABLED` (0 để tắt), `PUBSUB_GRPC_PORT`, `PUBSUB_ADMIN_PORT`, `PUBSUB_CONFIG`.
- docker-compose: thêm `- "8085:8085"` vào `ports` của **một** container (container khác dùng cổng host khác, vd `"8086:8085"`).
- Cấu hình topic / subscription / tốc độ sinh / template: `streams/gcp_pubsub.json` (mount `./streams:/app/streams` để sửa không cần build lại).
- Dashboard: tab **☁️ GCP Pub/Sub** - trạng thái topic, publish message (sinh từ template hoặc tự nhập), tạm dừng / chạy bộ sinh, đoạn `cym.yml` + biến môi trường cho shipper để copy.
- Admin API: `GET /mock/admin/api/pubsub/status`, `POST /mock/admin/api/pubsub/publish` (`{topic, count}` hoặc `{topic, messages:[...]}`, `pause: true/false`), `GET /mock/admin/api/pubsub/config?host=<ip-mock>`.
- Shipper: biến môi trường `PUBSUB_EMULATOR_HOST=<ip-mock>:8085` (áp dụng cho cả tiến trình shipper) + input:

  ```yaml
  - type: gcp_pubsub
    log_type: "gcp_audit"
    project_id: "mock-gcp-project"
    subscription_name: "siem-audit-logs-sub"
    credentials_base64: "<service account giả, lấy ở tab Pub/Sub>"   # bắt buộc nhưng emulator không kiểm tra
  ```

### 2.5. `beats` (Filebeat → input beats)

- Mã nguồn: loại `beats` mới trong `src/mock_sender.py` (`BeatsSenderJob`). Đây là client Lumberjack v2 viết bằng Python thuần.
- Cách gửi: mỗi lượt gửi là 1 batch, gồm frame `2W` (số event) và các frame `2J` (seq 1..n, nội dung JSON). Nếu bật `compress` thì các frame được bọc trong frame `2C` nén zlib. Sau đó chờ ACK `2A` tới khi seq = n.
- Hỗ trợ TLS (`tls: true`, không kiểm tra chứng chỉ).
- Event mẫu giả dạng Filebeat 6.x:
  - `message`: dòng access log nginx
  - `beat.name`, `beat.hostname`
  - `source`, `type: nginx_access`, `offset`, `input_type`

  Bộ lọc genconfig đọc đúng các trường này (`beat.name` → `server_id`, `source` → `log_file`, `type` → `log_parser`).
- Gửi qua Admin API:

  ```bash
  curl -X POST http://<ip-mock>:8081/mock/admin/api/sender/jobs -H 'Content-Type: application/json' -d '{
    "type": "beats", "host": "<ip-shipper>", "port": 5044, "batch_size": 50,
    "compress": true, "tls": false, "count": 10, "rate": 1
  }'
  ```

- Trường `message` (tuỳ chọn) là template event: mỗi dòng là một object JSON. Dòng không phải JSON được bọc thành `{"message": ...}`. Event **thiếu `message` sẽ bị shipper bỏ.**
- `POST /mock/admin/api/sender/preview` với cùng body trả về event mẫu và đoạn Python tương đương.
- e2e:

  ```bash
  e2e/run_e2e.sh beats 15
  e2e/run_e2e.sh beats_tls 15
  ```

- Dashboard: tab Mock Sender có chế độ **Beats** (batch size, nén zlib, TLS) và nút "⚙ Điền cấu hình mẫu". Phần xem trước sinh sẵn đoạn `cym.yml` cho input beats, `filebeat.yml` tương đương và code Python mẫu.

### 2.6. Hạ tầng dùng chung

- `src/stream_common.py`: luồng bản ghi sinh đều theo thời gian. Mỗi bản ghi có biến riêng: `{{SEQ}}`, `{{EVENT_TIME_ISO}}`, `{{EVENT_TIME_MS}}`, `{{PARTITION}}`.
- `src/template_engine.py`: thêm placeholder `{{CHOICE:a|b|c}}`.
- `src/stateful_engine.py`: thêm `stateful.type = "sls"`.
- `src/cert_manager.py`:
  - Danh sách domain MITM chuyển thành `SAN_DNS` ở đầu file.
  - Đã thêm `*.servicebus.windows.net` và `*.blob.core.windows.net`.
  - Khi danh sách đổi, mock tự ký lại server cert bằng **CA cũ**, nên không phải tin lại CA.

### 2.7. Harness e2e (`e2e/`)

Chạy binary shipper thật với một nguồn, output ra stdout, rồi đếm số event nhận được.

```bash
e2e/run_e2e.sh list                                                # liệt kê nguồn
MOCK_URL=http://localhost:8081 e2e/run_e2e.sh log_service_alibaba 30
PUBSUB_GRPC_PORT=8085 e2e/run_e2e.sh gcp_pubsub 30                 # cần pubsub_mock đang chạy
```

- `e2e/siem_api_stub.py`: SIEM-API giả luôn trả "không có config mới", để shipper giữ đúng config đang test (mock_siem_api.py cũ sẽ đẩy config đè lên). Mặc định cổng 18090.
- `e2e/mock_mongo.py`: Mongo giả cho checkpoint của các nguồn cloud, mặc định cổng 27027. Copy từ `test-cym-log-shipper`.
- `e2e/conf/<nguồn>.yml`: config shipper. `<nguồn>.env`: biến môi trường riêng. `<nguồn>.after.sh`: lệnh cho mock bắn log, chạy sau khi shipper đã khởi động (dùng cho nguồn push).
- Biến điều khiển: `SHIPPER_BIN`, `MOCK_URL`, `SIEM_PORT`, `MONGO_PORT`, `LOG_LEVEL`.

## 3. Danh sách file thay đổi (chưa commit)

- Mới:
  - `src/sls_mock.py`, `src/stream_common.py`, `src/http_input_keys.py`
  - `src/amqp_codec.py`, `src/azure_blob_mock.py` (dành cho Event Hubs, chưa được dùng)
  - `rules/07_log_service_alibaba.json`
  - `streams/gcp_pubsub.json`, `streams/azure_event_hubs.json`
  - `pubsub_mock/`, `e2e/`, `certs/http_input/`
- Sửa: `src/admin_api.py`, `src/mock_sender.py`, `src/stateful_engine.py`, `src/template_engine.py`, `src/cert_manager.py`
- Sinh lại: 4 file trong `datasets/`, các file `certs/server.*` và `certs/san.ext`.
- Không đụng tới các thay đổi dở dang có sẵn trong `src/web_dashboard.py`, `.dockerignore`, `nexpose_mock/`, `snmpd-mock/`.

## 4. `azure_event_hubs` (Đã hoàn thiện)

### Shipper cần gì

Input này dùng Event Processor Host (SDK `azure-event-hubs-go` v3, bản đã patch trong vendor). Nó **cố định** hai điều:

1. **AMQP 1.0 qua WebSocket**: `wss://<namespace>.servicebus.windows.net/$servicebus/websocket`, subprotocol `amqp`, đi qua `proxy_url` (CONNECT). Không có tuỳ chọn kết nối AMQP TCP thường.
2. **Lease / checkpoint trên Blob Storage**: `https://<storage_account>.blob.core.windows.net/<container_name>/...`, cũng đi qua `proxy_url`.

### Kiến trúc Mock hoàn chỉnh

- `src/event_hubs_broker.py`:
  - Tiếp nhận WebSocket upgrade (HTTP 101 Switching Protocols, subprotocol `amqp`).
  - Xử lý SASL handshake (ANONYMOUS, MSSBCBS, PLAIN).
  - Khởi tạo session AMQP 1.0 (Open, Begin).
  - Phiên `$cbs`: tiếp nhận put-token, trả về `status-code: 200 OK`.
  - Phiên `$management`: trả về partition info (`com.microsoft:eventhub`, `com.microsoft:partition`).
  - Partition streaming: gắn luồng `RateStream` cho từng partition theo cấu hình `streams/azure_event_hubs.json`, tự sinh sự kiện với batch `records` bọc trong AMQP message annotations (`x-opt-offset`, `x-opt-sequence-number`, `x-opt-enqueued-time`, `x-opt-partition-key`).
- `src/azure_blob_mock.py`:
  - Xử lý các request tới `*.blob.core.windows.net` (container create/list, block blob upload, lease acquire/renew/release/break).
- `src/proxy_handler.py`:
  - Bắt request `Upgrade: websocket` cho `*.servicebus.windows.net` và chuyển sang `event_hubs_broker`.
  - Bắt request tới `*.blob.core.windows.net` và chuyển sang `azure_blob_mock`.
- Admin API:
  - `GET /mock/admin/api/streams`: xem trạng thái Event Hubs partitions & Blob containers.
  - `POST /mock/admin/api/streams/azure_event_hubs/inject`: `{ "hub": "insights-logs", "count": 10 }`.

## 5. CHƯA LÀM: `wmi` (input `msrpc`)

- Trên UI, log source `wmi` thuộc collector v1 (Logstash). Ở shipper v2, log Windows được lấy qua input `msrpc` (agentless).
- Input `msrpc`:
  - Kết nối DCE/RPC qua TCP, **cố định cổng 135** (endpoint mapper) cộng cổng động.
  - Xác thực NTLM có seal (mã hoá).
  - Giao thức MS-EVEN6 (RegisterLogQuery / QueryNext), event dạng BinXML.
- Thư viện `oiweiwei/go-msrpc`, kể cả bản mới nhất v1.6.4, **chỉ có phía client**, nên mock phải tự viết toàn bộ phía server.
- Binary shipper trong `test-cym-log-shipper` **không có** input `msrpc`. Source `CymLogShipper` thiếu `filter/`, `go.mod`, `Dockerfile` nên không build được. Cần lấy source hoặc binary đầy đủ trước.
- Phương án nhanh nhất: test bằng một máy hoặc VM Windows thật.

## 6. Việc nhỏ còn tồn

- Định kỳ sinh lại dataset (mục 2.1).
- `go.sum` của `pubsub_mock` lấy từ cache Go trên máy dev. Build ở máy khác cần mạng để tải module.
