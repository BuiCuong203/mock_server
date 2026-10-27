# TÀI LIỆU MÔ TẢ ĐẦU API CẦN MOCK CHO 6 LOẠI CLOUD LOG SOURCES

> **Dự án**: CyM-Log-Shipper & Cloud Mock Server  
> **Phiên bản tài liệu**: 1.0  
> **Mục đích**: Mô tả chi tiết toàn bộ các đầu API (đã có và cần bổ sung) của 6 loại Cloud Log Sources để thiết lập hệ thống Mock Server chuẩn hóa, phục vụ kiểm thử đơn vị, kiểm thử tích hợp và kiểm thử tải cho Log Shipper.

---

## 1. BẢNaG MA TRẬN TỔNG QUAN 6 NGUỒN LOG

| STT | Log Source | Module Shipper | Phương thức kết nối | Trạng thái Checkpoint Mongo | Tình trạng Mock hiện tại | Cần mock bổ sung |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Azure Poller** | `azurepoller` | HTTPS REST (Direct / Proxy) | `value.last_time` (ISO-8601) | Đã có OAuth2 Token, Sign-in Logs | Directory Audits, Phân trang `@odata.nextLink`, Lỗi Token 401 |
| **2** | **Microsoft Defender** | `microsoft_defender` | HTTPS REST (Direct / Proxy) | `last_query` (Epoch Giây) | Đã có Token Direct, EDR Alerts | Incidents API, Graph Security V2, Token Proxy, Phân trang URL-encode |
| **3** | **Microsoft 365** | `microsoft365` | Office 365 Management API | `value.last_time` (ISO-8601) | Đã có Token, Start, List, Content Blobs, Download AAD | Phân trang Header `NextPageUri`, Content types: Exchange, SharePoint, General, DLP, Stop Sub |
| **4** | **AWS CloudWatch** | `aws_cloudwatch` | AWS SDK / Signature V4 | `last_query` (Epoch Mili-giây) | Đã có 20 kịch bản FilterLogEvents, Groups, Streams | `GetLogEvents` theo stream, STS `AssumeRole` |
| **5** | **AWS S3-SQS** | `aws_s3sqs` | AWS SDK / Signature V4 | Không dùng Mongo (SQS Queue quản lý) | Đã có Receive, Delete, GetAttrs, GetObject text, Head | `ChangeMessageVisibility`, File nén Gzip (`.gz`), SQS SNS envelope |
| **6** | **Generic REST API** | `restapi` | HTTP REST (Custom Headers/Auth) | `value.last_time` (Format động) | Đã có Token, Pull log tĩnh 1 trang | 4 cơ chế phân trang (`cursor`, `limit-offset`, `page-size`, `next_link`), Rate Limit 429 |

---

## 2. CHI TIẾT ĐẦU API CỦA TỪNG LOẠI LOG SOURCE

---

### 1. AZURE POLLER (`input/azurepoller`)

Mã nguồn đối chiếu: [`input/azurepoller/input.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/input/azurepoller/input.go)

#### 1.1. API Lấy OAuth2 Token
* **Trạng thái**: Đã có (`02_azure.json`)
* **Endpoint Direct**: `POST http://localhost:8881/mock/azure/token`
* **Endpoint Proxy**: `POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
* **Request Header**: `Content-Type: application/x-www-form-urlencoded`
* **Request Body**: `client_id=...&client_secret=...&grant_type=client_credentials&scope=https%3A%2F%2Fgraph.microsoft.com%2F.default`
* **Response (HTTP 200)**:
  ```json
  {
    "token_type": "Bearer",
    "expires_in": 3600,
    "access_token": "mock_jwt_access_token_azure_12345"
  }
  ```

#### 1.2. API Lấy Sign-in Logs (`/auditLogs/signIns`)
* **Trạng thái**: Đã có (`azure/sign_ins.json`)
* **Endpoint**: `GET https://graph.microsoft.com/v1.0/auditLogs/signIns`
* **Query Params**:
  * `$filter=createdDateTime gt 2026-10-07T00:00:00Z`
  * `$orderby=createdDateTime asc`
* **Trường thời gian checkpoint**: `createdDateTime`

#### 1.3. API Lấy Directory Audit Logs (`/auditLogs/directoryAudits`) — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Thu thập log kiểm toán thay đổi cấu hình thư mục AD (tạo user, đổi group, đổi quyền).
* **Endpoint**: `GET https://graph.microsoft.com/v1.0/auditLogs/directoryAudits`
* **Query Params**:
  * `$filter=activityDateTime gt 2026-10-07T00:00:00Z`
  * `$orderby=activityDateTime asc`
* **Lưu ý đặc biệt**: Code Shipper dòng 217 đọc trường thời gian là **`activityDateTime`** (khác với `createdDateTime` của sign-in).
* **Response Mock mẫu (HTTP 200)**:
  ```json
  {
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#auditLogs/directoryAudits",
    "@odata.nextLink": null,
    "value": [
      {
        "id": "Directory_da-{{TIMESTAMP}}-01",
        "category": "UserManagement",
        "activityDateTime": "{{NOW_ISO}}",
        "activityDisplayName": "Add user",
        "result": "success",
        "initiatedBy": {
          "user": {
            "userPrincipalName": "admin@contoso.onmicrosoft.com",
            "ipAddress": "118.70.1.2"
          }
        },
        "targetResources": [
          {
            "displayName": "User Test 01",
            "type": "User"
          }
        ]
      }
    ]
  }
  ```

#### 1.4. Kịch bản Phân trang (`@odata.nextLink`) — ⚠️ CẦN BỔ SUNG
* **Cơ chế**:
  * **Trang 1**: Trả về 100 sự kiện và `@odata.nextLink: "https://graph.microsoft.com/v1.0/auditLogs/signIns?$skiptoken=skip_token_page_2"`.
  * **Trang 2**: Trả về 50 sự kiện và `@odata.nextLink: null` (hoặc `""`).

---

### 2. MICROSOFT DEFENDER (`input/microsoft_defender`)

Mã nguồn đối chiếu: [`input/microsoft_defender/microsoft_defender.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/input/microsoft_defender/microsoft_defender.go)

#### 2.1. API Lấy OAuth2 Token
* **Trạng thái**: Đã có direct (`03_defender.json`), cần bổ sung rule Proxy qua `login.microsoftonline.com`.
* **Endpoint**: `POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
* **Scope**: `https://api.securitycenter.microsoft.com/.default`

#### 2.2. API Lấy Defender EDR Alerts (`/api/alerts`)
* **Trạng thái**: Đã có (`defender/alerts.json`)
* **Endpoint**: `GET https://api.securitycenter.microsoft.com/api/alerts`
* **Query Params**:
  * `$filter=alertCreationTime ge <startTime> and alertCreationTime le <endTime>`
* **Trường thời gian**: `alertCreationTime`
* **Lưu ý**: Cần có cả field `"id"` và `"event_id"` trong từng alert object để Kafka nhận được `event_id`.

#### 2.3. API Lấy Incidents (`/api/incidents`) — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Thu thập danh sách các Incident bảo mật (MTP/XDR Incident API khi tenant không có quyền Alert.Read.All).
* **Endpoint**: `GET https://api.securitycenter.microsoft.com/api/incidents`
* **Query Params**:
  * `$filter=createdTime ge <startTime> and createdTime le <endTime>`
* **Trường thời gian**: `createdTime`
* **Response Mock mẫu (HTTP 200)**:
  ```json
  {
    "@odata.nextLink": null,
    "value": [
      {
        "incidentId": 10245,
        "incidentName": "Multi-stage incident involving Initial Access and Lateral Movement",
        "createdTime": "{{NOW_ISO}}",
        "lastUpdateTime": "{{NOW_ISO}}",
        "status": "Active",
        "severity": "High",
        "classification": "TruePositive",
        "determination": "Malware",
        "alertsCount": 3,
        "alerts": [
          {
            "alertId": "da-{{TIMESTAMP}}-01",
            "title": "Suspicious PowerShell invocation"
          }
        ]
      }
    ]
  }
  ```

#### 2.4. API Microsoft Graph Security V2 (`/v1.0/security/alerts_v2`) — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Thu thập cảnh báo Defender qua chuẩn Microsoft Graph Security v2.
* **Endpoint**: `GET https://graph.microsoft.com/v1.0/security/alerts_v2`
* **Query Params**:
  * `$filter=createdDateTime ge <startTime> and createdDateTime le <endTime>`
* **Trường thời gian**: `createdDateTime`

#### 2.5. Phân trang `@odata.nextLink` (Đã URL-encode) — ⚠️ CẦN BỔ SUNG
* **Cơ chế**:
  * `@odata.nextLink` trả về URL **bắt buộc phải encode khoảng trắng thành `%20` hoặc `+`**:
    `https://api.securitycenter.microsoft.com/api/alerts?$filter=alertCreationTime%20ge%20...&$top=100&$skip=100`

---

### 3. MICROSOFT 365 (`input/microsoft365`)

Mã nguồn đối chiếu: [`internal/microsoft365/client.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/internal/microsoft365/client.go)

#### 3.1. API Quản lý Subscription
* **OAuth2 Token**: `POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
* **Start Subscription**: `POST https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/start?contentType=Audit.AzureActiveDirectory&PublisherIdentifier={tenant_id}`
* **List Subscriptions**: `GET https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/list?PublisherIdentifier={tenant_id}`
* **Stop Subscription (Cần bổ sung)**: `POST https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/stop?contentType=Audit.AzureActiveDirectory&PublisherIdentifier={tenant_id}`

#### 3.2. API Lấy Danh sách Blobs (`/subscriptions/content`)
* **Endpoint**: `GET https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?contentType=Audit.AzureActiveDirectory&startTime=...&endTime=...`
* **Response Body**: Danh sách các blob metadata (`contentUri`, `contentId`, `contentCreated`).

#### 3.3. Phân trang Blob qua Header `NextPageUri` — ⚠️ CẦN BỔ SUNG
* **Cơ chế đặc thù**: Office 365 Management API **không** trả link trang sau trong body mà trả qua HTTP Response Header:
  * **Header trả về**: `NextPageUri: https://manage.office.com/api/v1.0/{tenant_id}/activity/feed/subscriptions/content?nextPage=page_2`
  * Trang cuối cùng: **Không có** header `NextPageUri`.

#### 3.4. Mock Đa dạng các Content Types tải Blob — ⚠️ CẦN BỔ SUNG
Shipper cấu hình danh sách `content_types`: `["Audit.AzureActiveDirectory", "Audit.Exchange", "Audit.SharePoint", "Audit.General", "DLP.All"]`. Khi tải blob từ `contentUri`, cần mock các payload tương ứng:

1. **`Audit.Exchange`**:
   ```json
   [{
     "CreationTime": "{{NOW_ISO}}", "Id": "ex-{{TIMESTAMP}}", "Operation": "SendAs",
     "OrganizationId": "tenant-01", "RecordType": 2, "ResultStatus": "Succeeded",
     "UserId": "user@contoso.com", "MailboxOwnerUPN": "ceo@contoso.com", "ClientIPAddress": "1.2.3.4"
   }]
   ```
2. **`Audit.SharePoint`**:
   ```json
   [{
     "CreationTime": "{{NOW_ISO}}", "Id": "sp-{{TIMESTAMP}}", "Operation": "FileDownloaded",
     "OrganizationId": "tenant-01", "RecordType": 6, "ResultStatus": "Success",
     "UserId": "employee@contoso.com", "SourceFileName": "Financial_Report_2026.xlsx", "SiteUrl": "https://contoso.sharepoint.com/sites/finance"
   }]
   ```
3. **`Audit.General`** (Teams):
   ```json
   [{
     "CreationTime": "{{NOW_ISO}}", "Id": "tm-{{TIMESTAMP}}", "Operation": "MemberAdded",
     "OrganizationId": "tenant-01", "RecordType": 25, "ResultStatus": "Success",
     "UserId": "admin@contoso.com", "TeamName": "Security Incident Team"
   }]
   ```
4. **`DLP.All`**:
   ```json
   [{
     "CreationTime": "{{NOW_ISO}}", "Id": "dlp-{{TIMESTAMP}}", "Operation": "DlpRuleMatch",
     "PolicyDetails": [{"PolicyName": "PCI-DSS Credit Card Detection", "Rules": [{"RuleName": "Detect Credit Card Numbers"}]}]
   }]
   ```

---

### 4. AWS CLOUDWATCH (`input/aws_cloud/aws_cloudwatch`)

Mã nguồn đối chiếu: [`input/aws_cloud/aws_cloudwatch/interface.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/input/aws_cloud/aws_cloudwatch/interface.go)

#### 4.1. Các API Đã Mock Đầy Đủ (20 Scenarios)
* **`DescribeLogGroups`**: `POST /` với Header `X-Amz-Target: Logs_20140328.DescribeLogGroups`
* **`DescribeLogStreams`**: `POST /` với Header `X-Amz-Target: Logs_20140328.DescribeLogStreams`
* **`FilterLogEvents`**: `POST /` với Header `X-Amz-Target: Logs_20140328.FilterLogEvents`
  *(Đã có 20 kịch bản phân trang, nextToken, delayed last page, throttle 429, empty batch...)*

#### 4.2. API Đọc Log theo Stream (`GetLogEvents`) — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Dành cho luồng đọc trực tiếp từng stream cố định.
* **Header**: `X-Amz-Target: Logs_20140328.GetLogEvents`
* **Request Body**: `{"logGroupName": "...", "logStreamName": "...", "startTime": 1791280000000}`
* **Response Mock mẫu (HTTP 200)**:
  ```json
  {
    "events": [
      {
        "timestamp": {{NOW_MS}},
        "message": "{\"level\":\"info\",\"msg\":\"Service health check passed\"}",
        "ingestionTime": {{NOW_MS}}
      }
    ],
    "nextForwardToken": "f/mock_next_fwd_token_123",
    "nextBackwardToken": "b/mock_next_bwd_token_123"
  }
  ```

#### 4.3. API AWS STS AssumeRole — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Khi khách cấu hình xác thực qua IAM Role ARN (`role_arn`).
* **Endpoint**: `POST https://sts.amazonaws.com/` (hoặc proxy)
* **Body chứa**: `Action=AssumeRole&RoleArn=arn:aws:iam::123456789012:role/MockShipperRole`
* **Response (HTTP 200 XML)**: Trả về `Credentials` tạm thời (`AccessKeyId`, `SecretAccessKey`, `SessionToken`, `Expiration`).

---

### 5. AWS S3-SQS (`input/aws_cloud/aws_s3sqs`)

Mã nguồn đối chiếu: [`input/aws_cloud/aws_s3sqs/interface.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/input/aws_cloud/aws_s3sqs/interface.go)

#### 5.1. Các API SQS & S3 Đã Có
* SQS `ReceiveMessage` (`POST /` với `Action=ReceiveMessage`)
* SQS `DeleteMessage` (`POST /` với `Action=DeleteMessage`)
* SQS `GetQueueAttributes` (`POST /` với `Action=GetQueueAttributes`)
* S3 `GetObject` (`GET /mock-s3-bucket/...`) — File text
* S3 `HeadObject` (`HEAD /mock-s3-bucket/...`)

#### 5.2. SQS `ChangeMessageVisibility` — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Interface `ISQSClient` của Shipper gọi khi worker xử lý log tốn thời gian nhằm gia hạn thời gian ẩn message trên SQS, tránh việc message bị worker khác lấy lại.
* **Request Body**: `Action=ChangeMessageVisibility&QueueUrl=...&ReceiptHandle=...&VisibilityTimeout=300`
* **Response (HTTP 200 XML)**:
  ```xml
  <ChangeMessageVisibilityResponse xmlns="http://queue.amazonaws.com/doc/2012-11-05/">
    <ResponseMetadata>
      <RequestId>req-vis-{{TIMESTAMP}}</RequestId>
    </ResponseMetadata>
  </ChangeMessageVisibilityResponse>
  ```

#### 5.3. S3 GetObject Trả về File Nén Gzip (`.gz`) — ⚠️ CẦN BỔ SUNG
* **Mục đích**: AWS CloudTrail và VPC Flow Logs thực tế khi export vào S3 đều có đuôi `.json.gz` hoặc `.log.gz`.
* **Cơ chế Mock**:
  * Khi path kết thúc bằng `.gz`: Response trả về `Content-Type: application/gzip` và body là chuỗi byte đã được nén Gzip thực sự.
  * Giúp kiểm thử module giải nén `gzip.NewReader` của Shipper.

#### 5.4. SQS Message Body bọc qua Amazon SNS Envelope — ⚠️ CẦN BỔ SUNG
* **Mục đích**: Mô hình phổ biến trong thực tế: `S3 ObjectCreated -> SNS Topic -> SQS Queue`.
* **Message Body mẫu**:
  ```json
  {
    "Type": "Notification",
    "MessageId": "sns-msg-{{UUID}}",
    "TopicArn": "arn:aws:sns:us-east-1:123456789012:s3-notify-topic",
    "Message": "{\"Records\":[{\"eventVersion\":\"2.1\",\"s3\":{\"bucket\":{\"name\":\"mock-s3-bucket\"},\"object\":{\"key\":\"logs/app.log\"}}}]}"
  }
  ```

---

### 6. GENERIC REST API (`input/restapi`)

Mã nguồn đối chiếu: [`input/restapi/paging.go`](file:///home/hoangnx/Desktop/Playbox/cym-log-shipper-temp/input/restapi/paging.go)

Module Generic REST API được thiết kế linh hoạt nhất trong Shipper. Cần mock đầy đủ 4 mô hình phân trang để đáp ứng các loại API bên thứ ba:

#### 6.1. Phân trang Cursor-Based (`cursor_param_key` + `cursor_data_key`) — ⚠️ CẦN BỔ SUNG
* **Cấu hình shipper**: `cursor_param_key: "cursor"`, `cursor_data_key: "next_cursor"`.
* **Trang 1**: `GET /mock/rest_api/logs`
  ```json
  {
    "events": [{"id": 1, "timestamp": "{{NOW_ISO}}", "message": "Event 1"}],
    "next_cursor": "cursor_token_xyz_page_2"
  }
  ```
* **Trang 2**: `GET /mock/rest_api/logs?cursor=cursor_token_xyz_page_2`
  ```json
  {
    "events": [{"id": 2, "timestamp": "{{NOW_ISO}}", "message": "Event 2"}],
    "next_cursor": null
  }
  ```

#### 6.2. Phân trang Limit - Offset (`limit_key` + `offset_key`) — ⚠️ CẦN BỔ SUNG
* **Cấu hình shipper**: `limit_key: "limit"`, `offset_key: "offset"`, `limit_value: 100`.
* **Trang 1**: `GET /mock/rest_api/logs?limit=100&offset=0` -> Trả về 100 items.
* **Trang 2**: `GET /mock/rest_api/logs?limit=100&offset=100` -> Trả về 0 items (kết thúc).

#### 6.3. Phân trang Page - Size (`page_key` + `size_key`) — ⚠️ CẦN BỔ SUNG
* **Cấu hình shipper**: `page_key: "page"`, `size_key: "size"`, `page_value: 1`, `size_value: 50`.
* **Trang 1**: `GET /mock/rest_api/logs?page=1&size=50`
* **Trang 2**: `GET /mock/rest_api/logs?page=2&size=50` (empty events).

#### 6.4. Phân trang NextLink (`next_link_key`) — ⚠️ CẦN BỔ SUNG
* **Cấu hình shipper**: `next_link_key: "next_page_url"`.
* **Trang 1**: Response trả về trường `"next_page_url": "http://localhost:8881/mock/rest_api/logs?page=2"`.
* **Trang 2**: Response trả về `"next_page_url": null`.

#### 6.5. Kịch bản Rate Limiting (HTTP 429) & Exponential Backoff — ⚠️ CẦN BỔ SUNG
* **Response (HTTP 429 Too Many Requests)**:
  * Headers: `Retry-After: 5`
  * Body: `{"error": "Too Many Requests", "message": "Quota exceeded, please retry after 5 seconds"}`
* **Mục đích**: Kiểm tra Shipper có tự động dừng đúng 5 giây trước khi thực hiện request tiếp theo hay không.

---

## 3. LỘ TRÌNH THỰC HIỆN CẬP NHẬT MOCK SERVER

1. **Giai đoạn 1 (Ưu tiên cao - Sửa lỗi tương thích & Mock trực tiếp)**:
   * Thêm rule cho `GET /auditLogs/directoryAudits` vào `rules/02_azure.json`.
   * Thêm rule cho `GET /api/incidents` vào `rules/03_defender.json`.
   * Thêm kịch bản phân trang chuẩn URL-encoded cho Defender EDR.
   * Cập nhật `01_rest_api.json` với kịch bản Cursor-based pagination.
2. **Giai đoạn 2 (Hoàn thiện nghiệp vụ nâng cao)**:
   * Bổ sung Header `NextPageUri` và các file fixture cho M365 (`Exchange`, `SharePoint`).
   * Thêm SQS `ChangeMessageVisibility` vào `rules/06_aws_s3sqs_proxy.json`.
   * Mock file nén Gzip `.gz` cho AWS S3 GetObject.
3. **Giai đoạn 3 (Kịch bản biên & Chịu lỗi)**:
   * Giả lập HTTP 401 token expired (cho Azure, Defender, M365).
   * Giả lập HTTP 429 Rate Limit (cho REST API, CloudWatch).
