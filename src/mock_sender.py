"""
Mock Sender: chủ động bắn log tới collector (độc lập với phần mock API cloud).

Hiện hỗ trợ loại "syslog" qua UDP hoặc TCP:
  - format rfc3164 : <PRI>Mmm dd hh:mm:ss HOST APP[PID]: MSG
  - format rfc5424 : <PRI>1 2026-10-14T10:00:00.000Z HOST APP PID MSGID - MSG
  - format raw     : gửi nguyên nội dung message (đã tự có header syslog)
TCP đóng khung theo newline (mặc định) hoặc octet-counting (RFC 6587).

Loại "udp" / "tcp": gửi bằng thư viện logging chuẩn của Python
  - udp: logging.handlers.DatagramHandler, tcp: logging.handlers.SocketHandler
  - ghi đè makePickle() để gửi dòng text đã qua logging.Formatter (mặc định 2 handler này gửi pickle,
    collector không đọc được)

Loại "redis": kết nối Redis (giao thức RESP, không cần thư viện ngoài), AUTH + SELECT db,
  rồi RPUSH / LPUSH / PUBLISH nội dung vào key tùy chỉnh (input redis của shipper đọc LIST bằng LRANGE + LTRIM).

Loại "http": làm client đẩy log vào input http của shipper (shipper là HTTP server Gin):
  POST {path} (/log mặc định) body = mảng JSON gồm batch_size log, header X-API-KEY là token RSA do mock tự ký
  (shipper phải có PUB_KEY / SSL_CERT / SSL_KEY lấy từ GET /mock/admin/api/http_input/env).

Loại "beats": giả làm Filebeat đẩy log vào input beats của shipper bằng giao thức Lumberjack v2 (TCP, TLS tùy chọn):
  mỗi lượt gửi 1 batch = frame "2W" (số event) + các frame "2J" (seq 1..n, JSON), nén zlib trong frame "2C"
  nếu bật compress, rồi chờ ACK "2A" tới seq = n. Event không có trường "message" sẽ bị shipper bỏ.

Message hỗ trợ placeholder của TemplateEngine ({{NOW_ISO}}, {{UUID}}, {{RANDOM_INT:1:9}}...)
và thêm {{SEQ}} = số thứ tự trong job (1, 2, 3...), {{USER}} / {{ACTION}} lấy từ form.
"""
import http.client
import json
import logging
import logging.handlers
import os
import ssl
import struct
import sys
import socket
import threading
import time
import uuid
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .template_engine import TemplateEngine

SENDER_TYPES = ("syslog", "udp", "tcp", "redis", "http", "beats")   # udp / tcp: logging; redis: RESP; http: POST JSON; beats: Lumberjack v2
REDIS_COMMANDS = ("rpush", "lpush", "publish")
TRANSPORTS = ("udp", "tcp")
FORMATS = ("rfc3164", "rfc5424", "raw")
TCP_FRAMINGS = ("newline", "octet")
MAX_JOBS = 20                       # số job lưu trong bộ nhớ (cả đang chạy lẫn đã xong)
MAX_RUNNING = 10
MAX_RATE = 5000.0
MAX_MESSAGE_BYTES = 64 * 1024

FACILITIES = {
    "kern": 0, "user": 1, "mail": 2, "daemon": 3, "auth": 4, "syslog": 5, "lpr": 6, "news": 7,
    "uucp": 8, "cron": 9, "authpriv": 10, "ftp": 11, "local0": 16, "local1": 17, "local2": 18,
    "local3": 19, "local4": 20, "local5": 21, "local6": 22, "local7": 23,
}
SEVERITIES = {
    "emerg": 0, "alert": 1, "crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7,
}

LOG_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
              "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DEFAULT_LOGGER_NAME = "mock_sender"

DEFAULT_MESSAGES = [
    '<14>{"state": "success", "action": "{{ACTION}}", "user": "{{USER}}", "timestamp": {{NOW_MS}} }',
]

DEFAULT_LOGGING_MESSAGES = [
    '{"state": "success", "action": "{{ACTION}}", "user": "{{USER}}", "timestamp": {{NOW_MS}} }',
]

DEFAULT_BEATS_MESSAGES = [
    # Mẫu đã xác nhận hiển thị được trên portal (17/10/2026). log_parser: web_access nằm trong danh sách parser
    # ở output; KHÔNG gửi "type": "nginx_access" (parser này không có -> topic raw_input)
    '{"message": "hoangnx", "beat": {"name": "mock-web-01", "hostname": "mock-web-01", "version": "6.8.23"}, "source": "/var/log/nginx/access.log", "log_parser": "web_access", "input_type": "log", "offset": 1}',
]

DEFAULT_HTTP_MESSAGES = [
    '{"state": "success", "action": "{{ACTION}}", "user": "{{USER}}", "timestamp": {{NOW_MS}}, "seq": {{SEQ}}, "event_id": "{{UUID}}"}',
]

# Giá trị điền sẵn cho form Mock Sender (chỉ điền form, không tự gửi)
DEFAULT_FORM = {
    "host": "10.255.251.133",
    "port": 10514,
    "transport": "udp",
    "format": "raw",
    "append_newline": True,
    "count": 1,
    "user": "hoangnx",
    "action": "NODE_POST_INFO_1",
    "message": DEFAULT_MESSAGES[0],
}
_LOGGING_FORM = {
    "host": "10.255.250",
    "port": 10514,
    "append_newline": True,
    "split_lines": True,
    "count": 1,
    "user": "hoangnx",
    "action": "NODE_POST_INFO_1",
    "level": "INFO",
    "logger_name": DEFAULT_LOGGER_NAME,
    "log_format": "%(message)s",
    "message": DEFAULT_LOGGING_MESSAGES[0],
}
DEFAULT_FORMS = {
    "redis": {
        "type": "redis", "transport": "redis",
        "host": "", "port": 6379, "db": 0, "key": "cym_logs", "redis_command": "rpush",
        "split_lines": True, "count": 1, "user": "hoangnx", "action": "NODE_POST_INFO_1",
        "message": DEFAULT_LOGGING_MESSAGES[0],
    },
    "http": {
        "type": "http", "transport": "http",
        "host": "127.0.0.1", "port": 8080, "path": "/log", "tls": False, "batch_size": 10,
        "split_lines": True, "count": 1, "rate": 1, "user": "hoangnx", "action": "NODE_POST_INFO_1",
        "message": DEFAULT_HTTP_MESSAGES[0],
    },
    "beats": {
        "type": "beats", "transport": "tcp",
        "host": "127.0.0.1", "port": 5044, "tls": False, "batch_size": 50, "compress": True,
        "split_lines": True, "count": 1, "rate": 1, "user": "hoangnx", "action": "NODE_POST_INFO_1",
        "message": DEFAULT_BEATS_MESSAGES[0],
    },
    "syslog": DEFAULT_FORM,
    "udp": dict(_LOGGING_FORM, type="udp", transport="udp"),
    "tcp": dict(_LOGGING_FORM, type="tcp", transport="tcp"),
}


class SenderError(ValueError):
    pass


def _as_int(v: Any, name: str, lo: int, hi: int, default: Optional[int] = None) -> int:
    if v is None or v == "":
        if default is None:
            raise SenderError(f"Thiếu '{name}'")
        return default
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        raise SenderError(f"'{name}' phải là số")
    if n < lo or n > hi:
        raise SenderError(f"'{name}' phải trong khoảng {lo}..{hi}")
    return n


def _as_float(v: Any, name: str, lo: float, hi: float, default: float) -> float:
    if v is None or v == "":
        return default
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise SenderError(f"'{name}' phải là số")
    if n < lo or n > hi:
        raise SenderError(f"'{name}' phải trong khoảng {lo:g}..{hi:g}")
    return n


def _choice(v: Any, name: str, allowed, default: str) -> str:
    v = (v or default)
    v = str(v).strip().lower()
    if v not in allowed:
        raise SenderError(f"'{name}' không hợp lệ: {v} (cho phép: {', '.join(allowed)})")
    return v


def _token(v: Any, default: str, max_len: int) -> str:
    """Trường header syslog: không được chứa khoảng trắng."""
    s = str(v or "").strip() or default
    return "".join(ch for ch in s if ch.isprintable() and not ch.isspace())[:max_len] or default


def validate_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise SenderError("Body phải là JSON object")
    cfg: Dict[str, Any] = {}
    cfg["type"] = _choice(raw.get("type"), "type", SENDER_TYPES, "syslog")
    host = str(raw.get("host") or "").strip()
    if not host:
        raise SenderError("Thiếu 'host' (IP collector)")
    cfg["host"] = host
    cfg["port"] = _as_int(raw.get("port"), "port", 1, 65535)
    if cfg["type"] in ("udp", "tcp"):
        cfg["transport"] = cfg["type"]
        cfg["format"] = "raw"
        _validate_logging(raw, cfg)
    elif cfg["type"] == "redis":
        cfg["transport"] = "redis"
        cfg["format"] = "raw"
        _validate_redis(raw, cfg)
    elif cfg["type"] == "http":
        cfg["format"] = "raw"
        _validate_http(raw, cfg)
    elif cfg["type"] == "beats":
        cfg["format"] = "raw"
        _validate_beats(raw, cfg)
    else:
        cfg["transport"] = _choice(raw.get("transport"), "transport", TRANSPORTS, "udp")
        cfg["format"] = _choice(raw.get("format"), "format", FORMATS, "rfc3164")
    cfg["tcp_framing"] = _choice(raw.get("tcp_framing"), "tcp_framing", TCP_FRAMINGS, "newline")
    cfg["facility"] = _choice(raw.get("facility"), "facility", FACILITIES.keys(), "user")
    cfg["severity"] = _choice(raw.get("severity"), "severity", SEVERITIES.keys(), "info")
    cfg["hostname"] = _token(raw.get("hostname"), "mock-sender", 255)
    cfg["app_name"] = _token(raw.get("app_name"), "mock_sender", 48)
    cfg["rate"] = _as_float(raw.get("rate"), "rate", 0.1, MAX_RATE, 10.0)
    cfg["count"] = _as_int(raw.get("count"), "count", 0, 100_000_000, 100)
    cfg["duration"] = _as_int(raw.get("duration"), "duration", 0, 7 * 86400, 0)
    cfg["utc"] = bool(raw.get("utc", True))
    # Thêm "\n" cuối mỗi gói UDP (giống lệnh: echo '...' > /dev/udp/IP/PORT)
    cfg["append_newline"] = bool(raw.get("append_newline", False))

    # Biến người dùng điền trên form, chèn vào log qua {{USER}} / {{ACTION}}
    cfg["vars"] = {}
    for key in ("user", "action"):
        val = raw.get(key)
        val = "" if val is None else str(val)
        if len(val) > 256 or "\n" in val or "\r" in val:
            raise SenderError(f"'{key}' tối đa 256 ký tự và không được xuống dòng")
        cfg["vars"][key.upper()] = val
    split_lines = bool(raw.get("split_lines", True))
    text = raw.get("message")
    if text is None or str(text).strip() == "":
        messages = list(DEFAULT_HTTP_MESSAGES if cfg["type"] == "http" else
                        DEFAULT_BEATS_MESSAGES if cfg["type"] == "beats" else
                        DEFAULT_LOGGING_MESSAGES if cfg["type"] in ("udp", "tcp", "redis") else DEFAULT_MESSAGES)
    else:
        text = str(text)
        if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise SenderError(f"Message quá lớn (tối đa {MAX_MESSAGE_BYTES // 1024}KB)")
        messages = [ln for ln in text.splitlines() if ln.strip()] if split_lines else [text.strip("\r\n")]
        if not messages:
            raise SenderError("Message rỗng")
    cfg["split_lines"] = split_lines
    cfg["messages"] = messages
    if cfg["type"] in ("http", "beats"):
        cfg["messages"] = _merge_multiline_json(cfg, messages)
    if cfg["count"] == 0 and cfg["duration"] == 0:
        cfg["infinite"] = True  # chạy tới khi bấm Dừng
    return cfg


def _validate_logging(raw: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    level = str(raw.get("level") or "INFO").strip().upper()
    if level not in LOG_LEVELS:
        raise SenderError(f"'level' không hợp lệ: {level} (cho phép: {', '.join(LOG_LEVELS)})")
    cfg["level"] = level
    name = str(raw.get("logger_name") or "").strip() or DEFAULT_LOGGER_NAME
    if len(name) > 128 or any(ch.isspace() for ch in name):
        raise SenderError("'logger_name' tối đa 128 ký tự, không chứa khoảng trắng")
    cfg["logger_name"] = name
    fmt = str(raw.get("log_format") or "").strip("\r\n") or DEFAULT_LOG_FORMAT
    if len(fmt) > 1024 or "\n" in fmt:
        raise SenderError("'log_format' tối đa 1024 ký tự, trên 1 dòng")
    try:
        formatter = logging.Formatter(fmt, validate=True)
        formatter.format(logging.LogRecord(name, LOG_LEVELS[level], __file__, 0, "test", None, None))
    except (ValueError, KeyError, TypeError) as e:
        raise SenderError(f"'log_format' không hợp lệ: {e}")
    cfg["log_format"] = fmt


def _validate_redis(raw: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    key = str(raw.get("key") or "").strip()
    if not key:
        raise SenderError("Thiếu 'key' (tên key Redis)")
    if len(key) > 512 or "\n" in key or "\r" in key:
        raise SenderError("'key' tối đa 512 ký tự, không xuống dòng")
    cfg["key"] = key
    cfg["redis_command"] = _choice(raw.get("redis_command"), "redis_command", REDIS_COMMANDS, "rpush")
    cfg["db"] = _as_int(raw.get("db"), "db", 0, 1000, 0)
    for k in ("password", "username"):
        v = "" if raw.get(k) is None else str(raw.get(k))
        if len(v) > 512 or "\n" in v or "\r" in v:
            raise SenderError(f"'{k}' tối đa 512 ký tự, không xuống dòng")
        cfg[k] = v


def _validate_http(raw: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    path = str(raw.get("path") or "/log").strip()
    if not path.startswith("/") or len(path) > 512 or any(ch.isspace() for ch in path):
        raise SenderError("'path' phải bắt đầu bằng '/', không chứa khoảng trắng (vd /log)")
    cfg["path"] = path
    cfg["tls"] = bool(raw.get("tls", False))
    cfg["transport"] = "https" if cfg["tls"] else "http"
    cfg["batch_size"] = _as_int(raw.get("batch_size"), "batch_size", 1, 10000, 1)
    api_key = "" if raw.get("api_key") is None else str(raw.get("api_key")).strip()
    if len(api_key) > 8192 or "\n" in api_key:
        raise SenderError("'api_key' tối đa 8192 ký tự, trên 1 dòng")
    cfg["api_key"] = api_key          # để trống = mock tự ký token khớp PUB_KEY của mock


def _validate_beats(raw: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    cfg["tls"] = bool(raw.get("tls", False))
    cfg["transport"] = "tcp"
    cfg["batch_size"] = _as_int(raw.get("batch_size"), "batch_size", 1, 10000, 50)
    cfg["compress"] = bool(raw.get("compress", True))


def _is_json_object(cfg: Dict[str, Any], template: str) -> bool:
    try:
        return isinstance(json.loads(_render_body(cfg, template, 1)), dict)
    except ValueError:
        return False


def _merge_multiline_json(cfg: Dict[str, Any], messages: List[str]) -> List[str]:
    """http / beats: mỗi dòng phải là 1 object JSON. Nếu người dùng dán 1 object JSON viết trên nhiều dòng
    (các dòng lẻ không phải JSON nhưng ghép lại thì hợp lệ, kể cả dấu phẩy thừa ở cuối) -> coi cả khối là 1 log."""
    if len(messages) < 2 or all(_is_json_object(cfg, m) for m in messages):
        return messages
    joined = " ".join(m.strip() for m in messages).rstrip().rstrip(",").rstrip()
    if _is_json_object(cfg, joined):
        return [joined]
    return messages


def _render_body(cfg: Dict[str, Any], template: str, seq: int) -> str:
    for name, val in cfg.get("vars", {}).items():
        template = template.replace("{{" + name + "}}", val)
    return TemplateEngine.render_string(template.replace("{{SEQ}}", str(seq)))


def format_logging_line(cfg: Dict[str, Any], body: str) -> str:
    """Dòng text mà logging.Formatter tạo ra cho 1 log (dùng cho xem trước)."""
    record = logging.LogRecord(cfg["logger_name"], LOG_LEVELS[cfg["level"]], __file__, 0, body, None, None)
    return logging.Formatter(cfg["log_format"]).format(record)


def render_message(cfg: Dict[str, Any], template: str, seq: int) -> str:
    body = _render_body(cfg, template, seq)
    if cfg["type"] in ("udp", "tcp"):
        return format_logging_line(cfg, body)
    if cfg["type"] in ("redis", "http", "beats"):
        return body
    if cfg["format"] == "raw":
        return body
    pri = FACILITIES[cfg["facility"]] * 8 + SEVERITIES[cfg["severity"]]
    now = datetime.now(timezone.utc) if cfg["utc"] else datetime.now().astimezone()
    pid = os.getpid()
    if cfg["format"] == "rfc5424":
        ts = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return f"<{pri}>1 {ts} {cfg['hostname']} {cfg['app_name']} {pid} - - {body}"
    # RFC3164: ngày 1 chữ số đệm bằng dấu cách ("Oct  5")
    ts = f"{now:%b} {now.day:2d} {now:%H:%M:%S}"
    return f"<{pri}>{ts} {cfg['hostname']} {cfg['app_name']}[{pid}]: {body}"


# ---------------------------------------------------------------- xem trước + lệnh bash tương đương
_SEQ_MARK = "\x00SEQ\x00"


def _bash_quote(text: str) -> str:
    """Đặt chuỗi trong nháy đơn cho bash (nháy đơn bên trong -> '"'"')."""
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _wire_text(cfg: Dict[str, Any], line: str) -> Tuple[str, bool]:
    """(nội dung gửi, có ký tự xuống dòng cuối không) - giống hệt SenderJob._frame."""
    if cfg["transport"] == "tcp":
        if cfg["tcp_framing"] == "octet":
            return f"{len(line.encode('utf-8'))} {line}", False
        return line, True
    return line, bool(cfg.get("append_newline"))


def _fmt_rate(rate: float) -> str:
    return f"{rate:g}"


def _python_code(cfg: Dict[str, Any]) -> str:
    """Đoạn code Python (thư viện logging) tương đương với lượt gửi."""
    tcp = cfg["type"] == "tcp"
    nl = True if tcp else bool(cfg.get("append_newline"))
    base = "SocketHandler" if tcp else "DatagramHandler"
    cls = "TextTCPHandler" if tcp else "TextUDPHandler"
    end = ' + "\\n"' if nl else ""
    msg = _render_body(cfg, cfg["messages"][0].replace("{{SEQ}}", _SEQ_MARK), 1)
    has_seq = _SEQ_MARK in msg
    msg_expr = repr(msg.replace(_SEQ_MARK, "{{SEQ}}"))
    level = cfg["level"].lower()
    call = f'logger.{level}(MSG.replace("{{{{SEQ}}}}", str(i)))' if has_seq else f"logger.{level}(MSG)"
    lines = [
        "import logging",
        "import logging.handlers",
        "import time",
        "",
        "",
        f"class {cls}(logging.handlers.{base}):",
        f'    """Gửi dòng text đã format (mặc định {base} gửi pickle)."""',
        "    def makePickle(self, record):",
        f'        return (self.format(record){end}).encode("utf-8")',
        "",
        "",
        f"handler = {cls}({cfg['host']!r}, {cfg['port']})",
        f"handler.setFormatter(logging.Formatter({cfg['log_format']!r}))",
        "",
        f"logger = logging.getLogger({cfg['logger_name']!r})",
        "logger.setLevel(logging.DEBUG)",
        "logger.propagate = False",
        "logger.addHandler(handler)",
        "",
        f"MSG = {msg_expr}",
    ]
    count, rate, duration = cfg["count"], cfg["rate"], cfg["duration"]
    sleep = f"    time.sleep({1.0 / rate:.3g})"
    if count == 1:
        lines.append(call.replace("str(i)", "str(1)"))
    elif count and not duration:
        lines += [f"for i in range(1, {count} + 1):", "    " + call, sleep]
    else:
        cond = []
        if duration:
            lines.append(f"end = time.time() + {duration}")
            cond.append("time.time() < end")
        if count:
            cond.append(f"i < {count}")
        lines += ["i = 0", f"while {' and '.join(cond) or 'True'}:", "    i += 1", "    " + call, sleep]
    lines.append("handler.close()")
    return "\n".join(lines)


def _redis_cli(cfg: Dict[str, Any]) -> str:
    parts = ["redis-cli", "-h", cfg["host"], "-p", str(cfg["port"])]
    if cfg["db"]:
        parts += ["-n", str(cfg["db"])]
    if cfg["username"]:
        parts += ["--user", _bash_quote(cfg["username"])]
    if cfg["password"]:
        parts += ["-a", "'******'", "--no-auth-warning"]   # không lộ mật khẩu trên giao diện
    return " ".join(parts)


def build_redis_preview(cfg: Dict[str, Any], n: int = 3) -> Dict[str, Any]:
    msgs = cfg["messages"]
    cmd = cfg["redis_command"].upper()
    packets = []
    for i in range(min(n, len(msgs)) or 1):
        body = _render_body(cfg, msgs[i % len(msgs)], i + 1)
        packets.append({"text": body, "newline": False, "bytes": len(body.encode("utf-8"))})
    cli = _redis_cli(cfg)
    key_q = _bash_quote(cfg["key"])
    single = f"{cli} {cmd} {key_q} {_bash_quote(packets[0]['text'])}"
    loop = None
    count, rate, duration = cfg["count"], cfg["rate"], cfg["duration"]
    if count != 1:
        tpl = msgs[0]
        if "{{SEQ}}" in tpl:
            body = _render_body(cfg, tpl.replace("{{SEQ}}", _SEQ_MARK), 1)
            quoted = "\"$i\"".join(_bash_quote(part) for part in body.split(_SEQ_MARK))
        else:
            quoted = _bash_quote(packets[0]["text"])
        inner = f"{cli} {cmd} {key_q} {quoted} > /dev/null; sleep {1.0 / rate:.3g}"
        loop = (f"for i in $(seq 1 {count}); do {inner}; done" if count
                else f"i=0; while true; do i=$((i+1)); {inner}; done")
        if duration:
            loop = f"timeout {duration} bash -c {_bash_quote(loop)}"

    target = f"Redis {cfg['host']}:{cfg['port']} db {cfg['db']}"
    where = f"kênh '{cfg['key']}'" if cmd == "PUBLISH" else f"key '{cfg['key']}'"
    if count == 1:
        plan = f"{cmd} 1 log vào {where} trên {target}."
    elif count and duration:
        plan = f"{cmd} tối đa {count} log hoặc {duration} giây vào {where}, {_fmt_rate(rate)} log/giây, trên {target}."
    elif count:
        plan = f"{cmd} {count} log (khoảng {count / rate:.1f} giây) vào {where}, {_fmt_rate(rate)} log/giây, trên {target}."
    elif duration:
        plan = f"{cmd} liên tục {duration} giây (khoảng {int(rate * duration)} log) vào {where}, {_fmt_rate(rate)} log/giây, trên {target}."
    else:
        plan = f"{cmd} liên tục tới khi bấm Dừng vào {where}, {_fmt_rate(rate)} log/giây, trên {target}."
    if len(msgs) > 1:
        plan += f" Lần lượt quay vòng {len(msgs)} log đã nhập."

    notes = []
    if cmd == "RPUSH":
        notes.append("RPUSH thêm vào cuối LIST; input redis của shipper đọc từ đầu (LRANGE + LTRIM) nên giữ đúng thứ tự gửi.")
    elif cmd == "LPUSH":
        notes.append("LPUSH thêm vào đầu LIST: shipper đọc từ đầu nên log mới nhất được đọc trước (ngược thứ tự).")
    else:
        notes.append("PUBLISH gửi vào kênh Pub/Sub: input redis của shipper chỉ đọc LIST nên sẽ KHÔNG nhận được.")
    if cmd != "PUBLISH":
        notes.append("Key phải là kiểu LIST (hoặc chưa tồn tại); key đã có kiểu khác sẽ báo lỗi WRONGTYPE.")
    if cfg["password"]:
        notes.append("Mật khẩu được ẩn (******) trong lệnh mẫu; khi bấm Gửi mock dùng mật khẩu thật.")
    if "{{" in msgs[0].replace("{{SEQ}}", "").replace("{{USER}}", "").replace("{{ACTION}}", ""):
        notes.append("Trong lệnh mẫu, giá trị tự sinh (trừ {{SEQ}}) chỉ là giá trị mẫu cố định; khi bấm Gửi, mock sinh giá trị mới cho từng log.")
    return {"lines": [p["text"] for p in packets], "packets": packets, "command": single, "loop_command": loop,
            "python_code": None, "summary": plan, "notes": notes}


def _http_event(cfg: Dict[str, Any], template: str, seq: int) -> Any:
    """1 log -> 1 object JSON trong mảng gửi đi; log không phải JSON object thì bọc thành {"message": ...}."""
    body = _render_body(cfg, template, seq)
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    return {"message": body}


def _http_batch(cfg: Dict[str, Any], first_seq: int) -> List[Any]:
    msgs = cfg["messages"]
    return [_http_event(cfg, msgs[(first_seq + i - 1) % len(msgs)], first_seq + i) for i in range(cfg["batch_size"])]


def build_http_preview(cfg: Dict[str, Any], n: int = 3) -> Dict[str, Any]:
    batch = _http_batch(cfg, 1)
    body = json.dumps(batch, ensure_ascii=False)
    url = f"{cfg['transport']}://{cfg['host']}:{cfg['port']}{cfg['path']}"
    key_note = "$CYM_API_KEY" if not cfg["api_key"] else "<api_key đã nhập>"
    curl = (f"curl -s{'k' if cfg['tls'] else ''} -X POST {_bash_quote(url)} -H 'Content-Type: application/json' "
            f"-H \"X-API-KEY: {key_note}\" -d {_bash_quote(body)}")
    count, rate, duration = cfg["count"], cfg["rate"], cfg["duration"]
    per = f"mỗi request {cfg['batch_size']} log"
    if count == 1:
        plan = f"POST 1 request ({per}) tới {url}."
    elif count and duration:
        plan = f"POST tối đa {count} request hoặc {duration} giây, {_fmt_rate(rate)} request/giây ({per}) tới {url}."
    elif count:
        plan = f"POST {count} request ({count * cfg['batch_size']} log), {_fmt_rate(rate)} request/giây ({per}) tới {url}."
    elif duration:
        plan = f"POST liên tục {duration} giây, {_fmt_rate(rate)} request/giây ({per}) tới {url}."
    else:
        plan = f"POST liên tục tới khi bấm Dừng, {_fmt_rate(rate)} request/giây ({per}) tới {url}."
    notes = _not_json_notes(cfg) + ["Shipper chỉ nhận token ký bằng khóa khớp PUB_KEY: lấy PUB_KEY / SSL_CERT / SSL_KEY tại "
             "GET /mock/admin/api/http_input/env (hoặc .../env?format=shell) rồi export trước khi chạy shipper.",
             "Lệnh curl mẫu: lấy token bằng: export CYM_API_KEY=$(curl -s http://<mock>:8081/mock/admin/api/http_input/token)"]
    if cfg["path"] == "/data":
        notes.append("/data đẩy log sang NATS (subject cym_data) chứ không vào pipeline shipper; muốn thấy log ở output thì dùng /log.")
    if cfg["tls"]:
        notes.append("Bật TLS: shipper dùng SSL_CERT của mock (Mock CA); mock gửi không kiểm tra chứng chỉ.")
    shipper_config = "\n".join([
        "input:",
        "  - type: http",
        f"    port: {cfg['port']}",
        "    consumer_threads: 2",
        "    batch_size: 1000",
        f"    tls: {'true' if cfg['tls'] else 'false'}",
        "# Shipper cần biến môi trường PUB_KEY / SSL_CERT / SSL_KEY: bấm 'Lấy biến môi trường cho shipper'",
    ])
    return {"lines": [json.dumps(e, ensure_ascii=False) for e in batch[:n]],
            "packets": [{"text": body, "newline": False, "bytes": len(body.encode("utf-8"))}],
            "shipper_config": shipper_config,
            "command": curl, "loop_command": None, "python_code": None, "summary": plan, "notes": notes}


def _not_json_notes(cfg: Dict[str, Any]) -> List[str]:
    bad = [i + 1 for i, m in enumerate(cfg["messages"]) if not _is_json_object(cfg, m)]
    if not bad:
        return []
    lines = ", ".join(map(str, bad[:10])) + ("..." if len(bad) > 10 else "")
    return [f"⚠ Log thứ {lines} không phải object JSON nên sẽ bị bọc thành {{\"message\": \"...\"}} "
            "(mất các trường như source, log_parser). Mỗi log phải là 1 object JSON viết trên 1 dòng; "
            "hoặc bỏ chọn \"Mỗi dòng là một log riêng\" nếu chỉ gửi 1 object viết nhiều dòng."]


def build_beats_preview(cfg: Dict[str, Any], n: int = 3) -> Dict[str, Any]:
    batch = _http_batch(cfg, 1)
    target = f"{cfg['host']}:{cfg['port']}"
    count, rate, duration = cfg["count"], cfg["rate"], cfg["duration"]
    per = f"mỗi batch {cfg['batch_size']} event{', nén zlib' if cfg['compress'] else ''}{', TLS' if cfg['tls'] else ''}"
    if count == 1:
        plan = f"Gửi 1 batch Lumberjack v2 ({per}) tới input beats {target}, chờ ACK."
    elif count and duration:
        plan = f"Gửi tối đa {count} batch hoặc {duration} giây, {_fmt_rate(rate)} batch/giây ({per}) tới {target}."
    elif count:
        plan = f"Gửi {count} batch ({count * cfg['batch_size']} event), {_fmt_rate(rate)} batch/giây ({per}) tới {target}."
    elif duration:
        plan = f"Gửi liên tục {duration} giây, {_fmt_rate(rate)} batch/giây ({per}) tới {target}."
    else:
        plan = f"Gửi liên tục tới khi bấm Dừng, {_fmt_rate(rate)} batch/giây ({per}) tới {target}."
    sample = json.dumps(batch[0], ensure_ascii=False)
    python_code = "\n".join([
        "import json, socket, struct, zlib",
        f"events = [{sample}]",
        f"sock = socket.create_connection(({cfg['host']!r}, {cfg['port']}))",
        "frames = b''.join(b'2J' + struct.pack('>II', i + 1, len(d)) + d",
        "                  for i, d in enumerate(json.dumps(e).encode() for e in events))",
        "z = zlib.compress(frames)",
        "sock.sendall(b'2W' + struct.pack('>I', len(events)) + b'2C' + struct.pack('>I', len(z)) + z)",
        "while True:  # ACK: b'2A' + seq, đủ khi seq == số event",
        "    ack = sock.recv(6)",
        "    if not ack or struct.unpack('>I', ack[2:6])[0] >= len(events): break",
    ])
    notes = _not_json_notes(cfg) + ["Shipper chỉ giữ event có trường \"message\" (codec chạy trên message); event thiếu message bị bỏ.",
             "Bộ lọc genconfig cho beats dùng beat.name -> server_id, source -> log_file; log_parser có sẵn trong event "
             "được giữ nguyên, nếu không thì suy từ type / source. log_parser phải nằm trong danh sách parser ở output "
             "(vd web_access, apache_access), nếu không log rơi vào topic raw_input.",
             "Shipper ACK ngay khi nhận batch (trước khi xử lý)."]
    if cfg["tls"]:
        notes.append("Bật TLS: input beats phải có ssl: true + ssl_certificate / ssl_key; mock không kiểm tra chứng chỉ.")
    shipper_config = "\n".join([
        "input:",
        "  - type: beats",
        '    host: "0.0.0.0"',
        f"    port: {cfg['port']}",
        "    num_of_workers: 16",
        "    batch_size: 1000",
        "    codec:",
        "      type: plain",
    ] + ([
        "    ssl: true",
        "    ssl_certificate: /path/server.crt",
        "    ssl_key: /path/server.key",
        "    ssl_verify: false",
    ] if cfg["tls"] else []))
    filebeat = "\n".join([
        "# filebeat.yml tương đương (Filebeat thật gửi cùng giao thức)",
        "filebeat.inputs:",
        "  - type: log",
        "    paths: [/var/log/nginx/access.log]",
        "    fields: {log_parser: web_access}",
        "    fields_under_root: true",
        "output.logstash:",
        f'  hosts: ["{target}"]',
    ] + (["  ssl.verification_mode: none"] if cfg["tls"] else []))
    return {"lines": [json.dumps(e, ensure_ascii=False) for e in batch[:n]],
            "packets": [{"text": sample, "newline": False, "bytes": len(sample.encode("utf-8"))}],
            "shipper_config": shipper_config,
            "command": filebeat,
            "loop_command": None, "python_code": python_code, "summary": plan, "notes": notes}


def build_preview(cfg: Dict[str, Any], n: int = 3) -> Dict[str, Any]:
    if cfg["type"] == "beats":
        return build_beats_preview(cfg, n)
    if cfg["type"] == "redis":
        return build_redis_preview(cfg, n)
    if cfg["type"] == "http":
        return build_http_preview(cfg, n)
    msgs = cfg["messages"]
    packets = []
    for i in range(min(n, len(msgs)) or 1):
        line = render_message(cfg, msgs[i % len(msgs)], i + 1)
        wire, nl = _wire_text(cfg, line)
        packets.append({"text": wire, "newline": nl, "bytes": len(wire.encode("utf-8")) + (1 if nl else 0)})

    dev = f"/dev/{cfg['transport']}/{cfg['host']}/{cfg['port']}"
    echo = "echo" if packets[0]["newline"] else "echo -n"
    single = f"{echo} {_bash_quote(packets[0]['text'])} > {dev}"
    python_code = _python_code(cfg) if cfg["type"] in ("udp", "tcp") else None

    # Lệnh lặp: {{SEQ}} -> biến $i của bash (trừ octet-counting vì độ dài thay đổi theo $i)
    loop = None
    count, rate, duration = cfg["count"], cfg["rate"], cfg["duration"]
    if count != 1:
        tpl = msgs[0]
        if "{{SEQ}}" in tpl and not (cfg["transport"] == "tcp" and cfg["tcp_framing"] == "octet"):
            line = render_message(cfg, tpl.replace("{{SEQ}}", _SEQ_MARK), 1)
            wire, _ = _wire_text(cfg, line)
            quoted = "\"$i\"".join(_bash_quote(part) for part in wire.split(_SEQ_MARK))
        else:
            quoted = _bash_quote(packets[0]["text"])
        sleep = f"sleep {1.0 / rate:.3g}"
        body = f"{echo} {quoted} > {dev}; {sleep}"
        if count:
            loop = f"for i in $(seq 1 {count}); do {body}; done"
        else:
            loop = f"i=0; while true; do i=$((i+1)); {body}; done"
        if duration:
            loop = f"timeout {duration} bash -c {_bash_quote(loop)}"

    # Mô tả bằng lời
    target = f"{cfg['transport'].upper()} {cfg['host']}:{cfg['port']}"
    if count == 1:
        plan = f"Gửi 1 log tới {target}."
    else:
        if count and duration:
            amount = f"tối đa {count} log hoặc {duration} giây (điều kiện nào tới trước)"
        elif count:
            amount = f"{count} log (khoảng {count / rate:.1f} giây)"
        elif duration:
            amount = f"liên tục trong {duration} giây (khoảng {int(rate * duration)} log)"
        else:
            amount = "liên tục tới khi bấm Dừng"
        plan = f"Gửi {amount}, {_fmt_rate(rate)} log/giây, tới {target}."
    if len(msgs) > 1:
        plan += f" Lần lượt quay vòng {len(msgs)} log đã nhập."

    notes = []
    if python_code:
        notes.append("Thời gian %(asctime)s trong gói tin là lúc gửi; xem trước chỉ là giá trị mẫu.")
    if cfg["format"] != "raw":
        pri = FACILITIES[cfg["facility"]] * 8 + SEVERITIES[cfg["severity"]]
        notes.append(f"Header syslog do mock tự thêm: PRI <{pri}> = {cfg['facility']}({FACILITIES[cfg['facility']]}) x 8 + "
                     f"{cfg['severity']}({SEVERITIES[cfg['severity']]}); thời gian trong header là lúc gửi.")
    elif cfg["type"] == "syslog" and not packets[0]["text"].startswith("<"):
        notes.append("Đang gửi nguyên văn nhưng log không bắt đầu bằng <PRI> (vd <14>): "
                     "input syslog có thể coi là log không đúng chuẩn syslog.")
    if len(msgs) > 1 and loop:
        notes.append("Lệnh lặp bash chỉ dùng dòng log đầu tiên; khi bấm Gửi, mock sẽ quay vòng tất cả các dòng.")
    if "{{" in msgs[0].replace("{{SEQ}}", "").replace("{{USER}}", "").replace("{{ACTION}}", ""):
        notes.append("Trong lệnh mẫu, giá trị tự sinh (trừ {{SEQ}}) chỉ là giá trị mẫu cố định; khi bấm Gửi, mock sinh giá trị mới cho từng log.")
    if cfg["transport"] == "tcp" and loop and not python_code:
        notes.append("Lệnh lặp bash mở một kết nối TCP mới cho mỗi log; khi bấm Gửi, mock gửi tất cả trên cùng một kết nối.")
    if cfg["transport"] == "udp" and max(p["bytes"] for p in packets) > 1400:
        notes.append("Gói UDP lớn hơn ~1400 byte có thể bị phân mảnh hoặc rớt trên đường truyền.")

    return {"lines": [p["text"] for p in packets], "packets": packets,
            "command": single, "loop_command": loop, "python_code": python_code,
            "summary": plan, "notes": notes}


class SenderJob:
    def __init__(self, cfg: Dict[str, Any]):
        self.id = uuid.uuid4().hex[:8]
        self.cfg = cfg
        self.status = "starting"     # starting | running | stopped | done | error
        self.sent = 0
        self.errors = 0
        self.bytes_sent = 0
        self.last_error = ""
        self.last_message = ""
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self._first_sent_at: Optional[float] = None   # thời điểm gửi log đầu / cuối (monotonic) để tính tốc độ thực
        self._last_sent_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"mock-sender-{self.id}", daemon=True)
        self._lock = threading.Lock()

    # -------------------------------------------------- vòng gửi
    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    @property
    def running(self) -> bool:
        return self.status in ("starting", "running")

    def _open(self) -> Tuple[socket.socket, Tuple[str, int]]:
        cfg = self.cfg
        infos = socket.getaddrinfo(cfg["host"], cfg["port"], 0,
                                   socket.SOCK_DGRAM if cfg["transport"] == "udp" else socket.SOCK_STREAM)
        family, socktype, proto, _, addr = infos[0]
        sock = socket.socket(family, socktype, proto)
        if cfg["transport"] == "tcp":
            sock.settimeout(5)
            sock.connect(addr)
            sock.settimeout(10)
        return sock, addr

    def _frame(self, line: str) -> bytes:
        data = line.encode("utf-8")
        if self.cfg["transport"] == "tcp":
            if self.cfg["tcp_framing"] == "octet":
                return str(len(data)).encode() + b" " + data
            return data + b"\n"
        if self.cfg.get("append_newline"):
            return data + b"\n"
        return data

    def _fail(self, err: Exception):
        with self._lock:
            self.errors += 1
            self.last_error = f"{type(err).__name__}: {err}"

    # Kênh gửi syslog: socket trực tiếp
    def _setup(self):
        self._sock, self._addr = self._open()

    def _emit(self, line: str) -> int:
        """Gửi 1 dòng, trả số byte đã gửi; lỗi thì raise OSError."""
        payload = self._frame(line)
        try:
            if self.cfg["transport"] == "udp":
                self._sock.sendto(payload, self._addr)
            else:
                self._sock.sendall(payload)
        except OSError:
            if self.cfg["transport"] == "tcp":   # mất kết nối TCP: thử kết nối lại, chờ 1s
                try:
                    self._sock.close()
                except OSError:
                    pass
                if not self._stop.wait(1.0):
                    try:
                        self._sock, self._addr = self._open()
                    except Exception as e2:
                        self._fail(e2)
            raise
        return len(payload)

    def _teardown(self):
        sock = getattr(self, "_sock", None)
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    def _run(self):
        cfg = self.cfg
        try:
            self._setup()
        except Exception as e:  # DNS sai, TCP bị từ chối...
            self._fail(e)
            self.status = "error"
            self.finished_at = time.time()
            self._teardown()
            return

        self.status = "running"
        self.started_at = time.monotonic()
        wall_start = time.time()
        interval = 1.0 / cfg["rate"]
        next_send = self.started_at
        msgs = cfg["messages"]
        seq = 0
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                if cfg["count"] and self.sent + self.errors >= cfg["count"]:
                    break
                if cfg["duration"] and now - self.started_at >= cfg["duration"]:
                    break
                if now - next_send > 1.0:          # bị trễ: chỉ bù tối đa 1 giây
                    next_send = now - 1.0
                while next_send <= now and not self._stop.is_set():
                    if cfg["count"] and self.sent + self.errors >= cfg["count"]:
                        break
                    seq += 1
                    template = msgs[(seq - 1) % len(msgs)]
                    try:
                        line, nbytes = self._send_one(template, seq)
                        sent_at = time.monotonic()
                        with self._lock:
                            self.sent += 1
                            self.bytes_sent += nbytes
                            self.last_message = line
                            if self._first_sent_at is None:
                                self._first_sent_at = sent_at
                            self._last_sent_at = sent_at
                    except OSError as e:
                        self._fail(e)
                    next_send += interval
                self._stop.wait(max(0.0, min(next_send - time.monotonic(), 0.05)))
            self.status = "stopped" if self._stop.is_set() else "done"
        except Exception as e:
            self._fail(e)
            self.status = "error"
        finally:
            self._teardown()
            self.finished_at = time.time()
            self._elapsed = time.time() - wall_start

    def _send_one(self, template: str, seq: int) -> Tuple[str, int]:
        line = render_message(self.cfg, template, seq)
        return line, self._emit(line)

    # -------------------------------------------------- trạng thái
    def to_dict(self) -> Dict[str, Any]:
        cfg = self.cfg
        if self.started_at is None:
            elapsed = 0.0
        elif self.finished_at is not None:
            elapsed = getattr(self, "_elapsed", 0.0)
        else:
            elapsed = time.monotonic() - self.started_at
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "type": cfg["type"],
                "target": (f"redis://{cfg['host']}:{cfg['port']}/{cfg['db']} {cfg['redis_command'].upper()} {cfg['key']}"
                           if cfg["type"] == "redis" else
                           f"{cfg['transport']}://{cfg['host']}:{cfg['port']}{cfg['path']} (x{cfg['batch_size']}/request)"
                           if cfg["type"] == "http" else
                           f"lumberjack{'+tls' if cfg.get('tls') else ''}://{cfg['host']}:{cfg['port']} (x{cfg['batch_size']}/batch)"
                           if cfg["type"] == "beats" else f"{cfg['transport']}://{cfg['host']}:{cfg['port']}"),
                "path": cfg.get("path"), "batch_size": cfg.get("batch_size"), "tls": cfg.get("tls"),
                "key": cfg.get("key"), "redis_command": cfg.get("redis_command"), "db": cfg.get("db"),
                "host": cfg["host"], "port": cfg["port"], "transport": cfg["transport"],
                "format": cfg["format"], "tcp_framing": cfg["tcp_framing"],
                "append_newline": cfg.get("append_newline", False),
                "user": cfg.get("vars", {}).get("USER", ""), "action": cfg.get("vars", {}).get("ACTION", ""),
                "facility": cfg["facility"], "severity": cfg["severity"],
                "level": cfg.get("level"), "logger_name": cfg.get("logger_name"), "log_format": cfg.get("log_format"),
                "rate": cfg["rate"], "count": cfg["count"], "duration": cfg["duration"],
                "message_templates": len(cfg["messages"]),
                "sent": self.sent, "errors": self.errors, "bytes_sent": self.bytes_sent,
                "elapsed_seconds": round(elapsed, 1),
                # N log cách nhau N-1 khoảng: tốc độ = (N-1) / (thời điểm log cuối - log đầu)
                "actual_rate": round((self.sent - 1) / (self._last_sent_at - self._first_sent_at), 1)
                if self.sent > 1 and self._last_sent_at > self._first_sent_at else 0.0,
                "last_error": self.last_error,
                "last_message": self.last_message,
                "created_at": datetime.fromtimestamp(self.created_at, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }


class _TextHandlerMixin:
    """makePickle -> dòng text đã format; lỗi gửi được ghi lại cho job thay vì in traceback ra stderr."""
    append_newline = False

    def makePickle(self, record):
        self.last_text = self.format(record)
        data = (self.last_text + ("\n" if self.append_newline else "")).encode("utf-8")
        self.last_bytes = len(data)
        return data

    def handleError(self, record):
        # Không gọi Handler.handleError gốc (in traceback ra stderr): chỉ ghi nhận lỗi cho job
        self.last_error = sys.exc_info()[1] or OSError("send failed")
        if getattr(self, "closeOnError", False) and getattr(self, "sock", None):
            try:
                self.sock.close()
            finally:
                self.sock = None   # SocketHandler sẽ tự kết nối lại ở lần gửi sau


class TextDatagramHandler(_TextHandlerMixin, logging.handlers.DatagramHandler):
    pass


class TextSocketHandler(_TextHandlerMixin, logging.handlers.SocketHandler):
    append_newline = True   # TCP: mỗi log kết thúc bằng xuống dòng để collector tách được

    def send(self, s):
        # SocketHandler gốc âm thầm bỏ log khi chưa kết nối được -> báo lỗi để job đếm
        if self.sock is None:
            self.createSocket()
        if self.sock is None:
            raise ConnectionError(f"Chưa kết nối được TCP {self.host}:{self.port} (sẽ thử lại)")
        try:
            self.sock.sendall(s)
        except OSError:
            # giống SocketHandler gốc: bỏ socket hỏng để lần gửi sau kết nối lại
            try:
                self.sock.close()
            finally:
                self.sock = None
            raise


class LoggingSenderJob(SenderJob):
    """Gửi bằng logging.Logger + DatagramHandler (UDP) / SocketHandler (TCP)."""

    def _setup(self):
        cfg = self.cfg
        socket.getaddrinfo(cfg["host"], cfg["port"])          # DNS sai -> lỗi ngay
        if cfg["type"] == "tcp":
            handler = TextSocketHandler(cfg["host"], cfg["port"])
            handler.retryStart, handler.retryMax = 1.0, 5.0
            handler.createSocket()
            if handler.sock is None:                          # không kết nối được -> báo lỗi ngay
                handler.close()
                raise ConnectionRefusedError(f"Không kết nối được TCP {cfg['host']}:{cfg['port']}")
        else:
            handler = TextDatagramHandler(cfg["host"], cfg["port"])
            handler.append_newline = bool(cfg.get("append_newline"))
        handler.setFormatter(logging.Formatter(cfg["log_format"]))
        # Logger riêng cho job (không đăng ký vào logging.getLogger toàn cục, không lan sang root)
        logger = logging.Logger(cfg["logger_name"], logging.DEBUG)
        logger.propagate = False
        logger.addHandler(handler)
        self._handler, self._logger = handler, logger
        self._level = LOG_LEVELS[cfg["level"]]

    def _send_one(self, template: str, seq: int) -> Tuple[str, int]:
        handler = self._handler
        handler.last_error, handler.last_bytes, handler.last_text = None, 0, ""
        self._logger.log(self._level, _render_body(self.cfg, template, seq))
        if handler.last_error is not None:
            err = handler.last_error
            raise err if isinstance(err, OSError) else OSError(f"{type(err).__name__}: {err}")
        return handler.last_text, handler.last_bytes

    def _teardown(self):
        handler = getattr(self, "_handler", None)
        if handler is not None:
            try:
                handler.close()
            except Exception:
                pass


class RedisReplyError(OSError):
    """Redis trả lỗi (-ERR, -WRONGTYPE, -NOAUTH...)."""


class RedisSenderJob(SenderJob):
    """Client RESP tối giản: AUTH, SELECT, PING, RPUSH/LPUSH/PUBLISH."""

    def _connect(self):
        cfg = self.cfg
        sock = socket.create_connection((cfg["host"], cfg["port"]), timeout=5)
        sock.settimeout(10)
        self._sock, self._rfile = sock, sock.makefile("rb")
        if cfg["password"]:
            if cfg["username"]:
                self._cmd("AUTH", cfg["username"], cfg["password"])
            else:
                self._cmd("AUTH", cfg["password"])
        if cfg["db"]:
            self._cmd("SELECT", str(cfg["db"]))
        self._cmd("PING")

    def _close(self):
        for obj in (getattr(self, "_rfile", None), getattr(self, "_sock", None)):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._sock = self._rfile = None

    @staticmethod
    def _encode(args) -> bytes:
        out = [b"*%d\r\n" % len(args)]
        for a in args:
            b = a if isinstance(a, bytes) else str(a).encode("utf-8")
            out.append(b"$%d\r\n%s\r\n" % (len(b), b))
        return b"".join(out)

    def _read_reply(self):
        line = self._rfile.readline()
        if not line:
            raise ConnectionError("Redis đóng kết nối")
        kind, rest = line[:1], line[1:].rstrip(b"\r\n")
        if kind == b"+":
            return rest.decode()
        if kind == b"-":
            raise RedisReplyError(rest.decode(errors="replace"))
        if kind == b":":
            return int(rest)
        if kind == b"$":
            n = int(rest)
            return None if n < 0 else self._rfile.read(n + 2)[:-2]
        if kind == b"*":
            n = int(rest)
            return None if n < 0 else [self._read_reply() for _ in range(n)]
        raise ConnectionError(f"Phản hồi Redis không hợp lệ: {line[:50]!r}")

    def _cmd(self, *args):
        self._sock.sendall(self._encode(args))
        return self._read_reply()

    def _setup(self):
        self._connect()

    def _send_one(self, template: str, seq: int) -> Tuple[str, int]:
        cfg = self.cfg
        body = _render_body(cfg, template, seq)
        if self._sock is None:
            self._connect()
        try:
            self._cmd(cfg["redis_command"].upper(), cfg["key"], body)
        except RedisReplyError:
            raise                              # lỗi logic (WRONGTYPE...): kết nối vẫn dùng được
        except OSError:
            self._close()                      # mất kết nối: lần sau tự kết nối lại (chờ 1s)
            self._stop.wait(1.0)
            raise
        return body, len(body.encode("utf-8"))

    def _teardown(self):
        self._close()


class HttpSenderJob(SenderJob):
    """POST mảng JSON (batch_size log) tới input http của shipper, header X-API-KEY ký bằng khóa của mock."""

    def _connect(self):
        cfg = self.cfg
        if cfg["tls"]:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._conn = http.client.HTTPSConnection(cfg["host"], cfg["port"], timeout=10, context=ctx)
        else:
            self._conn = http.client.HTTPConnection(cfg["host"], cfg["port"], timeout=10)

    def _setup(self):
        from .http_input_keys import make_token
        self._token = self.cfg["api_key"] or make_token()
        self._connect()
        self._conn.connect()                  # cổng chưa mở -> báo lỗi ngay

    def _send_one(self, template: str, seq: int) -> Tuple[str, int]:
        cfg = self.cfg
        first = (seq - 1) * cfg["batch_size"] + 1
        body = json.dumps(_http_batch(cfg, first), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-API-KEY": self._token}
        try:
            self._conn.request("POST", cfg["path"], body=body, headers=headers)
            resp = self._conn.getresponse()
            data = resp.read()
        except (OSError, http.client.HTTPException) as e:
            self._conn.close()                 # mất kết nối: lần sau mở lại (chờ 1s)
            self._connect()
            self._stop.wait(1.0)
            raise OSError(f"{type(e).__name__}: {e}")
        if resp.status >= 300:
            raise OSError(f"HTTP {resp.status}: {data[:200].decode('utf-8', 'replace')}")
        return f"[{cfg['batch_size']} log] HTTP {resp.status} {data[:120].decode('utf-8', 'replace')}", len(body)

    def _teardown(self):
        conn = getattr(self, "_conn", None)
        if conn is not None:
            conn.close()


class BeatsSenderJob(SenderJob):
    """Client Lumberjack v2 (giao thức Filebeat -> Logstash) đẩy batch event vào input beats của shipper."""

    def _connect(self):
        cfg = self.cfg
        sock = socket.create_connection((cfg["host"], cfg["port"]), timeout=10)
        if cfg["tls"]:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(sock, server_hostname=cfg["host"])
        sock.settimeout(30)
        self._sock = sock

    def _close(self):
        sock = getattr(self, "_sock", None)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._sock = None

    def _setup(self):
        self._connect()

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Shipper đóng kết nối")
            buf += chunk
        return buf

    def _send_one(self, template: str, seq: int) -> Tuple[str, int]:
        cfg = self.cfg
        first = (seq - 1) * cfg["batch_size"] + 1
        events = _http_batch(cfg, first)
        frames = b"".join(b"2J" + struct.pack(">II", i + 1, len(d)) + d
                          for i, d in enumerate(json.dumps(e, ensure_ascii=False).encode("utf-8") for e in events))
        if cfg["compress"]:
            z = zlib.compress(frames)
            payload = b"2W" + struct.pack(">I", len(events)) + b"2C" + struct.pack(">I", len(z)) + z
        else:
            payload = b"2W" + struct.pack(">I", len(events)) + frames
        if self._sock is None:
            self._connect()
        try:
            self._sock.sendall(payload)
            acked = 0
            while acked < len(events):            # server có thể gửi ACK từng phần
                ack = self._recv_exact(6)
                if ack[:2] != b"2A":
                    raise ConnectionError(f"Phản hồi không phải ACK: {ack!r}")
                acked = struct.unpack(">I", ack[2:])[0]
        except (OSError, ssl.SSLError) as e:
            self._close()                          # mất kết nối: lần sau mở lại (chờ 1s)
            self._stop.wait(1.0)
            raise OSError(f"{type(e).__name__}: {e}")
        return f"[{len(events)} event] ACK seq={acked}", len(payload)

    def _teardown(self):
        self._close()


class MockSenderManager:
    def __init__(self):
        self._jobs: Dict[str, SenderJob] = {}
        self._lock = threading.Lock()

    def preview(self, raw: Dict[str, Any], n: int = 3) -> Dict[str, Any]:
        return build_preview(validate_config(raw), n)

    def start(self, raw: Dict[str, Any]) -> SenderJob:
        cfg = validate_config(raw)
        with self._lock:
            if sum(1 for j in self._jobs.values() if j.running) >= MAX_RUNNING:
                raise SenderError(f"Đang chạy tối đa {MAX_RUNNING} job, hãy dừng bớt")
            # Giữ tối đa MAX_JOBS: bỏ job đã kết thúc cũ nhất
            finished = sorted((j for j in self._jobs.values() if not j.running), key=lambda j: j.created_at)
            while len(self._jobs) >= MAX_JOBS and finished:
                self._jobs.pop(finished.pop(0).id, None)
            job_cls = {"udp": LoggingSenderJob, "tcp": LoggingSenderJob, "redis": RedisSenderJob,
                       "http": HttpSenderJob, "beats": BeatsSenderJob}.get(cfg["type"], SenderJob)
            job = job_cls(cfg)
            self._jobs[job.id] = job
        job.start()
        return job

    def stop(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.stop()
        return True

    def stop_all(self) -> int:
        n = 0
        for job in list(self._jobs.values()):
            if job.running:
                job.stop()
                n += 1
        return n

    def remove(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.stop()
            self._jobs.pop(job_id, None)
            return True

    def list(self) -> List[Dict[str, Any]]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs]


mock_sender = MockSenderManager()
