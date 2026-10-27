# Nexpose mock (Rapid7 InsightVM on-prem API v3)

Mock cho job `sync_rapid7_nexpose` của **siem-va-integrate**.

| Endpoint | Job dùng khi | Mock trả về |
|---|---|---|
| `GET /api/3/assets?page=&size=` | Lần sync đầu (chưa có run FINISHED) | Toàn bộ asset ban đầu (`--initial`) |
| `POST /api/3/assets/search?page=&size=` | Các lần cron sau | Asset có `last-scan-date` trong khoảng filter |

Mỗi lần job gọi search ở `page=0` (tức mỗi lần `R7_JOB_CRON` chạy), mock giả lập một đợt scan mới:
rescan `--rescan` asset cũ và sinh `--new` asset mới với last scan = bây giờ. Nhờ vậy mỗi lần cron
đều có dữ liệu để upsert vào collection `r7_assets`.

## Chạy

```bash
python3 nexpose_mock_server.py                       # https://localhost:3780/api/3, 120 asset, rescan 5, new 2
python3 nexpose_mock_server.py --initial 500 --rescan 20 --new 10
python3 nexpose_mock_server.py --user ubuntu --password '098poiA#'   # kiểm tra đúng Basic Auth
```

Mặc định khớp `config.yaml` của siem-va-integrate (`NEXPOSE_API: https://localhost:3780/api/3`,
`NEXPOSE_SSL: False`), không cần sửa config. Dữ liệu nằm trong RAM: restart mock là sinh lại.
`--tz` (mặc định `Asia/Ho_Chi_Minh`) phải khớp `JOB_TZ` để lọc theo ngày đúng.
