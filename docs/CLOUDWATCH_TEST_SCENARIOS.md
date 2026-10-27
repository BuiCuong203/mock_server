# Kịch bản mock AWS CloudWatch Logs

Bộ kịch bản `scenarios/cw_*.json` dùng để kiểm thử input `cloudwatch` của CyM-Log-Shipper theo sơ đồ `Luong_day_log_CloudWatch.xmind`. Kết quả mong đợi trong tài liệu này được đối chiếu với code thật ở `input/aws_cloud/aws_cloudwatch`.

## 1. Chuẩn bị

### 1.1. Chạy mock

```bash
./run.sh start -d                       # mặc định port 8081
./scripts/cw_scenario.sh list           # liệt kê kịch bản cw_*
./scripts/cw_scenario.sh cw_01_success_single_page
```

Shipper gọi đúng endpoint thật `logs.<region>.amazonaws.com`, vì vậy **bắt buộc đi qua proxy của mock**. Mock nhận lệnh CONNECT và trả lời bằng cert của CA riêng.

Cert hiện có chỉ hợp lệ cho region `us-east-1`. Muốn dùng region khác (ap-southeast-1, ap-southeast-2, ap-northeast-1, us-west-2, eu-west-1) thì xóa thư mục `certs/` rồi khởi động lại mock để sinh cert mới. Sau đó phải cấp lại `ca-bundle.crt` mới cho shipper.

### 1.2. Cấu hình shipper (`cym.yml`)

```yaml
input:
  - type: cloudwatch
    log_type: cloudtrail
    log_group_arn: "arn:aws:logs:us-east-1:123456789012:log-group:mock-cw-group:*"
    access_key_id: "AKIAMOCKACCESSKEY01"
    secret_access_key: "mock-secret-key"
    proxy_url: "http://<IP máy chạy mock>:8081"
    add_field:
      input_plugin: cloudwatch
```

- **Không cấu hình `role_arn`.** Request STS AssumeRole được tạo trước khi gắn proxy (`credentails.go`: `getRoleArn` chạy trước `HTTPClient = proxy`), nên đi thẳng ra Internet và mock không chặn được.
- `eps_limit` để trống. Nếu đặt giá trị này, shipper sẽ ngủ `len(events)/eps_limit` giây sau mỗi trang.

### 1.3. Biến môi trường của shipper

```bash
export SSL_CERT_FILE=/path/cloud-mock-server/certs/ca-bundle.crt   # Go trust CA của mock
export SIEM_MONGO_URI="mongodb://<host>:27017"
```

### 1.4. Seed checkpoint MongoDB (BẮT BUỘC)

Code đọc mốc bằng `FindOne`:
- **Không có document**: lỗi `fail FindOne mongo`. Shipper thử lại mỗi 10 giây và **không bao giờ gọi AWS**.
- **Có document nhưng thiếu `last_query`**: `startTime = 0`, tức kéo log từ năm 1970.

Mốc nằm ở field **`last_query` ở cấp root, đơn vị mili-giây** (không nằm trong `value`). Nếu không cấu hình `log_streams` thì **không được** ghi field `log_streams` trong document, vì filter so sánh với `null`.

```js
use siem
db.log_source.insertOne({
  protocol_properties: { log_group_arn: "arn:aws:logs:us-east-1:123456789012:log-group:mock-cw-group:*" },
  last_query: NumberLong(Date.now() - 5 * 60 * 1000)
})
// Theo dõi mốc:
db.log_source.find({ "protocol_properties.log_group_arn": /mock-cw-group/ }, { last_query: 1 })
```

### 1.5. Cách kiểm tra kết quả

| Kiểm tra | Cách làm |
|---|---|
| Request shipper gửi, cửa sổ thời gian, mốc tiến/giữ/trùng/hổng | `./scripts/cw_scenario.sh check` |
| Request/response chi tiết | Dashboard `http://localhost:8081/mock/admin/` |
| Log shipper | `Query group ... from <start> to <end>`, `Processing N events`, `Push success N event`, `fail get log event`, `update time_query` |
| Số bản ghi trên Kafka | Đếm theo `event_id` trong `log_raw` (mock gắn `event_id` vào message của từng event) |
| Mốc MongoDB | Query ở mục 1.4 |

Đặc điểm thời gian của code cần nhớ khi đọc kết quả:
- **Chu kỳ:** chu kỳ đầu chạy ngay, các chu kỳ sau nghỉ cố định 10 giây.
- **endTime** = Now − 30 giây.
- **Mốc mới** = endTime + 1.
- **Giữa các trang:** nghỉ 200 ms, chỉ khi trang có event.

Đổi kịch bản ngay khi shipper đang chạy thì có hiệu lực từ request tiếp theo, không cần restart shipper.

## 2. Danh sách kịch bản

### Giai đoạn 3: API thành công

| Kịch bản | Mock trả về | Kết quả mong đợi (theo code) |
|---|---|---|
| `cw_01_success_single_page` | 3 event, không có `nextToken` | Kafka +3 mỗi chu kỳ. `last_query = endTime + 1`. `check` báo **tiến mốc** |
| `cw_02_empty_window` | `events: []` | Không có gì vào Kafka. **Mốc vẫn tiến** (Time-Window Advance). Log `update time_query` vẫn xuất hiện |
| `cw_03_pagination` | Trang 1: 2 event, token `cw-page-2`. Trang 2: 0 event, token `cw-page-3`. Trang 3: 2 event, hết token | Mỗi chu kỳ có 3 request (request sau mang `nextToken`). Kafka +4 (`cw-p1-1/2`, `cw-p3-1/2`). Trang rỗng ở giữa bị bỏ qua nhưng vẫn kéo tiếp. Mốc tiến sau trang cuối |
| `cw_04_large_batch` | Trang 1: 2000 event (bằng `Limit`). Trang 2: 500 event | Kafka +2500, mỗi `event_id` (`cw-big-p1-0001..2000`, `cw-big-p2-0001..0500`) xuất hiện đúng một lần |
| `cw_05_special_payload` | Tiếng Việt và emoji, JSON lồng, stack trace nhiều dòng, plain text, message ~210 KB | 5 event giữ nguyên nội dung. Event `cw-sp-big` **bị bộ lọc `limit_size 200000` trong `cym.yml` loại bỏ** (nếu dùng cấu hình mẫu). Các event còn lại vào Kafka |

### Giai đoạn 3: API thất bại

| Kịch bản | Mock trả về | Kết quả mong đợi (theo code) |
|---|---|---|
| `cw_06_throttling` | 400 `ThrottlingException` | SDK tự retry nên mock thấy **nhiều request cùng cửa sổ trong một chu kỳ**. Sau đó log `fail get log event`, **mốc giữ nguyên**, sau 10 giây thử lại cùng startTime |
| `cw_07_throttling_then_recover` | Xen kẽ: Throttling, rồi 200 kèm 1 event | Lần gọi đầu bị throttle, SDK retry thành công **ngay trong cùng chu kỳ**. Shipper không log lỗi. Kafka +1, mốc tiến |
| `cw_08_server_error_5xx` | Xen kẽ 500 `InternalFailure` và 503 `ServiceUnavailableException` | SDK retry, sau đó lỗi. Mốc giữ nguyên |
| `cw_09_pagination_fail_mid` | Trang 1 OK (2 event, token `cw-dup-page-2`), trang 2 bị Throttling | **Trang 1 đã vào Kafka nhưng mốc không tiến.** Chu kỳ sau kéo lại trang 1, nên `cw-dup-p1-1/2` **bị trùng** trên Kafka sau mỗi chu kỳ. Đây là lỗi thiết kế của code, sơ đồ cần ghi nhận |
| `cw_10_network_timeout` | Treo 70 giây | `ResponseHeaderTimeout` = 60 giây (khi có proxy) nên request lỗi timeout. SDK có thể retry nên một chu kỳ kéo dài vài phút. Mốc giữ nguyên |
| `cw_11_connection_drop` | Mock đóng kết nối, không trả response | Lỗi mạng (EOF / connection reset). SDK retry, sau đó lỗi. Mốc giữ nguyên. Request log của mock ghi `status 0` |
| `cw_12_malformed_response` | 200 nhưng JSON bị cắt dở | SDK lỗi deserialize. Mốc giữ nguyên, không có gì vào Kafka |
| `cw_13_missing_event_fields` | Event thiếu `message` và `ingestionTime` | **Phát hiện lỗi:** `receive.go:41-43` dereference con trỏ nil, shipper **panic và process dừng**. Kiểm tra process có restart không và có mất mốc không |

### Giai đoạn 2: Xác thực / tài nguyên

Tất cả trả HTTP 400 với `__type` tương ứng. Lỗi xác thực không được SDK retry. Shipper log `fail get log event: ... <Mã lỗi>`, **giữ nguyên mốc**, thử lại sau mỗi 10 giây (không dừng hẳn input).

| Kịch bản | Mã lỗi AWS | Tình huống |
|---|---|---|
| `cw_14_auth_access_denied` | `AccessDeniedException` | Key đúng nhưng thiếu quyền `logs:FilterLogEvents` |
| `cw_15_auth_invalid_key` | `UnrecognizedClientException` | Sai Access Key ID |
| `cw_16_auth_signature_mismatch` | `InvalidSignatureException` | Sai Secret Access Key |
| `cw_17_auth_expired_token` | `ExpiredTokenException` | `session_token` hết hạn |
| `cw_18_log_group_not_found` | `ResourceNotFoundException` | Sai tên log group hoặc log group đã bị xóa |

> Mock **không xác minh chữ ký SigV4**. Để kiểm tra lỗi xác thực, hãy bật kịch bản tương ứng thay vì nhập sai key thật.

## 3. Các nhánh trong xmind không mock bằng API được

Các nhánh dưới đây liên quan đến hạ tầng, không phải phản hồi API, nên phải thao tác trực tiếp lên hạ tầng (nên chạy song song với `cw_01_success_single_page`):

| Nhánh xmind | Cách tạo tình huống | Hành vi thực tế theo code |
|---|---|---|
| GĐ1: kết nối MongoDB thất bại | Dừng container MongoDB hoặc đặt sai `SIEM_MONGO_URI` | `mongo.Connect` không lỗi ngay. Lỗi xuất hiện ở `FindOne`, log `fail FindOne mongo`, thử lại mỗi 10 giây (không dừng hẳn) |
| GĐ1: chưa có mốc | Xóa document trong `log_source` | **Khác xmind:** code không lấy Now mà lỗi `FindOne` và không gọi AWS. Nếu document có nhưng thiếu `last_query` thì kéo từ 1970 |
| GĐ3: lưu MongoDB thất bại | Dừng MongoDB **sau khi** shipper đã đọc mốc | `SaveToMongo` lỗi nhưng mốc **trong RAM vẫn tiến**, nên chu kỳ sau kéo tiếp bình thường. DB giữ mốc cũ, restart shipper sẽ kéo lại (trùng) |
| GĐ3: lưu MongoDB không khớp document | Đổi `log_group_arn` trong document | `UpdateOne` không upsert, không báo lỗi, mốc không được lưu |
| GĐ3: đẩy Kafka thất bại | Dừng Kafka | **Khác xmind:** `PushEvent` không trả lỗi mà **bị block** khi queue đầy, input đứng chờ, mốc không tiến |
| GĐ4: chu kỳ 10 giây | Xem cột thời điểm trong `check` | Hai chu kỳ thành công liên tiếp cách nhau khoảng 10 giây cộng thời gian xử lý |

## 4. Tính năng mock bổ sung cho bộ kịch bản này

- `response.drop_connection: true`: mock đóng socket, không trả response (dùng ở `cw_11`).
- Rule phân trang khớp bằng `match.body_regex` trên `"nextToken":"..."`. Rule trang sau phải đặt **trước** rule trang 1 trong file scenario.
- Fixture lớn: `fixtures/cloudwatch/large_page_1.json`, `large_page_2.json`, `special_payload.json`.
