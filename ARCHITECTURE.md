# Tài liệu Thiết Kế Kỹ Thuật (Architecture Overview) - Cloud Mock Server

**Tác giả:** Antigravity AI  
**Trạng thái:** Active  
**Ngày phân tích:** 06/10/2026  

---

## 1. Bối cảnh & Vấn đề (Context & Problem Statement)
Trong quá trình phát triển các hệ thống tích hợp (Integration) và thu thập log (Log Shipper) từ các nền tảng Cloud lớn (AWS, Azure, Microsoft 365, v.v.), đội ngũ QA/Dev gặp khó khăn vì:
- API Cloud thực tế thường có chi phí gọi cao, bị giới hạn tốc độ (Rate Limit), hoặc khó tái hiện các kịch bản lỗi mạng, lỗi hết hạn Token.
- Không thể tạo ra hàng nghìn log giả lập trên môi trường thật để làm bài test chịu tải (Stress Test).

Vì vậy, dự án **Cloud Mock Server** ra đời như một máy chủ độc lập chuyên dụng, giả lập 100% các hành vi của 6 nguồn Cloud Log phổ biến.

## 2. Mục tiêu & Tính năng lõi (Goals)
- **Giả lập Đa Nguồn (6 Sources):** Hỗ trợ REST API truyền thống, Azure, MS Defender, MS 365, AWS CloudWatch, AWS S3-SQS.
- **HTTPS Proxy Tunneling:** Có khả năng đứng chặn giữa (Man-in-the-Middle) và tự sinh chứng chỉ SSL giả (Mock Root CA, SAN) cho các domain thật như `*.microsoftonline.com` hay `*.amazonaws.com`.
- **Luật động & Kịch bản (Rule & Scenario Engine):** Khai báo Input/Output hoàn toàn qua file JSON/YAML mà không cần sửa code Python. Có thể đổi qua lại giữa các tình huống như `rate_limit_429`, `auth_fail_401`, `server_error_500` chỉ bằng 1 click.
- **Template Engine:** Tự động sinh dữ liệu thực tế (Real-time placeholders) như `{{NOW_ISO}}`, `{{UUID}}`, `{{MD5:...}}` vào trong Response Body.
- **Web Dashboard & Admin API:** Cung cấp giao diện trực quan tại `http://localhost:8081/mock/admin/` để theo dõi request real-time và API để tích hợp CI/CD.

---

## 3. Kiến trúc Tổng thể (C4 Model)

### C4 Level 2: Container Diagram

```mermaid
flowchart TB
    User(("👨‍💻 Dev/QA\n(Trình duyệt / CI-CD)"))
    Shipper(("📦 Log Shipper\n(Agent cần test)"))
    
    subgraph MockSystem ["☁️ Cloud Mock Server (Python)"]
        Dashboard["🌐 Web Dashboard\n[Giao diện quản trị HTML/JS]"]
        API["⚙️ Admin REST API\n[Quản lý Rules/Scenarios]"]
        Proxy["🛡️ Proxy Handler\n[HTTPS CONNECT Tunnel]"]
        Engine["🧠 Rule & Template Engine\n[Khớp cấu hình JSON/YAML]"]
        LogBuffer["📝 In-Memory Logger\n[Lưu lịch sử Request]"]
    end

    User -- "Thao tác giao diện UI" --> Dashboard
    User -- "Gọi API đổi kịch bản" --> API
    Shipper -- "Gửi Data / Connect Proxy" --> Proxy
    
    Dashboard -- "Fetch Logs & Rules" --> API
    API -- "Load/Switch" --> Engine
    Proxy -- "Chuyển Request" --> Engine
    Engine -- "Ghi vết" --> LogBuffer
    API -- "Đọc lịch sử" --> LogBuffer

    classDef container fill:#23a2d9,stroke:#0b4884,color:#ffffff,rx:5px,ry:5px
    class Dashboard,API,Proxy,Engine,LogBuffer container
```

---

## 4. Luồng Tương tác Nghiệp vụ (Sequence Diagrams)

### Luồng 1: Xử lý Request thông qua HTTPS Proxy Tunnel (Ví dụ gọi AWS S3)
Luồng này thể hiện cơ chế mà Mock Server làm giả một domain thật (Ví dụ `s3.amazonaws.com`) và dùng Rule Engine để trả về Payload giả. Yêu cầu bắt buộc: **User -> Proxy -> API**.

```mermaid
sequenceDiagram
    autonumber
    actor Shipper as Agent (Log Shipper)
    participant Proxy as HTTPS Proxy Tunnel
    participant RuleEngine as Rule & Template Engine

    Shipper->>Proxy: CONNECT s3.amazonaws.com:443
    Proxy->>Proxy: Sinh chứng chỉ SSL ảo (Mock CA) cho s3.amazonaws.com
    Proxy-->>Shipper: 200 Connection Established

    Shipper->>Proxy: GET /my-bucket/audit-log.json.gz (Bọc trong TLS)
    Proxy->>RuleEngine: Chuyển Request HTTP nội bộ để xử lý
    
    RuleEngine->>RuleEngine: Quét mảng Rules trong `06_aws_s3sqs_proxy.json`
    
    alt Không tìm thấy Rule phù hợp
        RuleEngine-->>Proxy: 404 Not Found
        Proxy-->>Shipper: Trả về 404
    else Tìm thấy Rule (Thành công)
        RuleEngine->>RuleEngine: Nạp Fixture file (Payload giả)
        RuleEngine->>RuleEngine: Render Template (Thay thế {{NOW_ISO}}, {{UUID}})
        RuleEngine-->>Proxy: Trả về HTTP 200 OK (Kèm Payload động)
        Proxy-->>Shipper: Trả dữ liệu JSON/XML đã được Mock
    end
```

**Mô tả các bước thực hiện:**
1. **Bước 1:** Ký giả (`Agent / Shipper`) gửi lệnh `CONNECT` qua TCP tới cổng Proxy của máy chủ Mock để đòi nói chuyện với domain thật (AWS).
2. **Bước 2:** `Proxy` sinh chứng chỉ giả mạo (Fake SSL Cert) và trả về `200 Connection Established`. Kể từ đây, kết nối TLS giữa Agent và Mock Server chính thức thành lập.
3. **Bước 3:** `Agent` gửi request lấy file thực sự (đã được mã hóa). `Proxy` giải mã và chuyển cho `Rule Engine`.
4. **Trường hợp Lỗi:** Nếu không có Rule JSON nào khai báo khớp với URL/Header/Body này, hệ thống ngắt luồng và trả về `404 Not Found` (Agent sẽ nhận cảnh báo).
5. **Trường hợp Thành công:** Engine nạp file mẫu từ thư mục `fixtures/`, biến đổi các biến động (ngày giờ hiện tại), và phản hồi `200 OK` ra ngoài cho Agent hoàn tất quy trình lấy log giả lập.

---

## 5. Mô hình Dữ liệu (Mock Rule Schema)

Vì dự án thuần túy dựa trên các cấu hình JSON (Data-driven), dưới đây là cấu trúc lõi của một Rule Object được dùng trong Engine:

```mermaid
erDiagram
    MOCK_RULE ||--|{ MATCH_CONDITION : "dùng để lọc Request"
    MOCK_RULE ||--|| RESPONSE_ACTION : "định nghĩa kết quả"

    MOCK_RULE {
        string id PK
        string name "Mô tả tính năng của Rule"
        boolean enabled "Bật/Tắt"
    }
    
    MATCH_CONDITION {
        string method "GET, POST, PUT..."
        string path "Đường dẫn URL"
        string path_match "exact | prefix | regex | contains"
        json headers "Key-value regex match"
        string body_contains "Chuỗi tồn tại trong Body"
    }

    RESPONSE_ACTION {
        int status "Mã HTTP (200, 403, 500)"
        int delay_ms "Độ trễ mạng giả lập"
        json headers "Custom Headers trả về"
        json body "Payload hoặc Fixture File"
    }
```

---

## 6. Tổng kết Vận hành & Bảo mật
Dự án được thiết kế 100% bằng **Python thuần** (`server.py`) không sử dụng các dependencies nặng nhằm tối ưu tốc độ và đơn giản hóa khâu cài đặt.
- **Start Daemon:** `./run.sh start -d`
- **Dashboard:** Truy cập cổng mặc định `8081` để theo dõi log.

Tài liệu này được biên soạn dựa trên cấu trúc cây thư mục, `README.md` và tuân thủ các quy tắc TDD/C4 của hệ thống Antigravity Loogix.
