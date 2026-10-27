# snmpd-mock

SNMP agent giả lập (net-snmp trong Docker) để test 2 input của CyM-Log-Shipper:

| Input shipper | Chiều | Cách dùng |
|---|---|---|
| `snmp` (polling) | collector -> container | collector poll `udp:<IP máy chạy Docker>/1161/cym_ro_2026` |
| `snmptrap` | container -> collector | `docker exec snmpd-mock send_trap.sh <IP_COLLECTOR:PORT> ...` |

## Chạy

```bash
docker compose up -d --build
```

Sửa `snmpd.conf` (được mount vào container) rồi:

```bash
docker compose restart
```

Dừng và xóa:

```bash
docker compose down
```

## Polling: cấu hình input snmp

```yaml
- type: snmp
  hosts: ["udp:<IP máy chạy Docker>/1161/cym_ro_2026"]   # hoặc tcp:...
  get:   ["1.3.6.1.2.1.1.5.0", "1.3.6.1.4.1.99999.1.2.0"]
  walk:  ["1.3.6.1.4.1.8072.1.3.2.3.1.1"]                  # message mock (extend)
  interval: 30
```

Dữ liệu mock trong `snmpd.conf`:

| OID | Giá trị | Nguồn |
|---|---|---|
| `1.3.6.1.2.1.1.5.0` | `mock-snmp-01` | `sysName` |
| `1.3.6.1.4.1.8072.1.3.2.3.1.1.7.99.121.109.95.109.115.103` | JSON, timestamp mới mỗi lần poll | `extend cym_msg` -> `cym_msg.sh` |
| `1.3.6.1.4.1.8072.1.3.2.3.1.1.9.99.121.109.95.102.105.120.101.100` | JSON cố định | `extend cym_fixed` |
| `1.3.6.1.4.1.99999.1.1.0` / `.1.2.0` / `.1.3.0` | chuỗi / số nguyên / counter | `override` |

Trong event của shipper, tên field là OID với dấu chấm đổi thành `_`, vd `1_3_6_1_2_1_1_5_0`.

Kiểm tra từ máy collector:

```bash
snmpwalk -v2c -c cym_ro_2026 udp:<IP máy chạy Docker>:1161 1.3.6.1.4.1.8072.1.3.2.3.1.1
```

## Trap: bắn riêng bằng docker exec

```bash
docker exec snmpd-mock send_trap.sh <IP_COLLECTOR>:162
```

```bash
docker exec snmpd-mock send_trap.sh <IP_COLLECTOR>:162 '{"state":"failed","action":"NODE_LOGIN"}' luudinhthi NODE_LOGIN
```

Tham số: `<IP:PORT> [message] [user] [action]`; community lấy từ biến `COMMUNITY` (mặc định `cym_ro_2026`).
Trap v2c, trap OID `1.3.6.1.4.1.99999.0.1`, 3 biến: `.99999.2.1` message, `.99999.2.2` user, `.99999.2.3` action.

Input snmptrap tương ứng trên collector:

```yaml
- type: snmptrap
  host: "0.0.0.0"
  port: 162
  protocol: udp
```

Collector chạy trên chính máy Docker thì `<IP_COLLECTOR>` là gateway của network compose
(xem: `docker inspect snmpd-mock --format '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}'`).

## Lưu ý

- `rocommunity ... default` cho mọi IP poll vào: chỉ dùng trong lab.
- Cổng 1161 được map trên mọi IP của máy (`0.0.0.0`); muốn chỉ cho local thì đổi thành `127.0.0.1:1161:161/udp`.
- Dockerfile chạy `snmpd -C -c ...`: thiếu `-C` snmpd đọc file 2 lần và lỗi `Address in use`.
