"""
Mock Alibaba Cloud Log Service (SLS) cho input `log_service_alibaba` của CyM-Log-Shipper.

Shipper dùng consumer group của aliyun-log-go-sdk, gọi REST tới http://<project>.<endpoint>/...:
  GET  /logstores/{ls}/consumergroups                         ListConsumerGroup   -> JSON
  POST /logstores/{ls}/consumergroups                         CreateConsumerGroup
  PUT  /logstores/{ls}/consumergroups/{cg}                    UpdateConsumerGroup
  POST /logstores/{ls}/consumergroups/{cg}?type=heartbeat     HeartBeat           -> [shard_id...] giao cho consumer
  POST /logstores/{ls}/consumergroups/{cg}?type=checkpoint    UpdateCheckpoint
  GET  /logstores/{ls}/consumergroups/{cg}                    GetCheckpoint       -> [{shard, checkpoint...}]
  GET  /logstores/{ls}/shards                                 ListShards
  GET  /logstores/{ls}/shards/{id}?type=cursor&from=begin|end|<unix> GetCursor    -> {"cursor": ...}
  GET  /logstores/{ls}/shards/{id}?type=logs&cursor=&count=   PullLogs  -> LogGroupList protobuf nén LZ4
                                                              (header x-log-cursor / x-log-bodyrawsize / x-log-compresstype)

Shipper tới được mock bằng 1 trong 2 cách (không cần DNS):
  - endpoint: "127.0.0.1:8081"  (SDK thấy endpoint là IP -> tự dùng chính IP đó làm HTTP proxy)
  - endpoint thật (cn-hangzhou.log.aliyuncs.com) + proxy_url: "http://<mock>:8081"

Không kiểm tra chữ ký (access_id / access_key nào cũng được). Lỗi 401/403/500... giả lập bằng rule thường đặt trước.
"""
import base64
import json
import threading
import time
import uuid
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from .stream_common import RateStream, load_templates, record_vars, render_record

DEFAULT_TEMPLATES = [
    {
        "eventId": "{{UUID}}",
        "eventName": "{{CHOICE:ConsoleSignin|CreateInstance|DeleteBucket|PutObject|AttachPolicyToUser|StopInstance}}",
        "eventSource": "{{CHOICE:ecs.aliyuncs.com|oss.aliyuncs.com|ram.aliyuncs.com|signin.aliyun.com}}",
        "eventTime": "{{EVENT_TIME_ISO}}",
        "acsRegion": "cn-hangzhou",
        "sourceIpAddress": "{{RANDOM_INT:1:223}}.{{RANDOM_INT:0:255}}.{{RANDOM_INT:0:255}}.{{RANDOM_INT:1:254}}",
        "userIdentity.userName": "{{CHOICE:admin|dev_ops|auditor|sales01|ram_user_ci}}",
        "userIdentity.type": "{{CHOICE:ram-user|root-account|assumed-role}}",
        "errorCode": "{{CHOICE:|||NoPermission|InvalidAccessKeyId}}",
        "seq": "{{SEQ}}",
        "shard": "{{PARTITION}}",
    }
]


# ------------------------------------------------------------------ protobuf (LogGroupList) + LZ4
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field_bytes(field_no: int, data: bytes) -> bytes:
    return _varint((field_no << 3) | 2) + _varint(len(data)) + data


def _encode_log(log_time: int, contents: Dict[str, Any]) -> bytes:
    out = _varint((1 << 3) | 0) + _varint(int(log_time) & 0xFFFFFFFF)   # Time (uint32)
    for k, v in contents.items():
        if v is None:
            v = ""
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        content = _field_bytes(1, str(k).encode("utf-8")) + _field_bytes(2, v.encode("utf-8"))
        out += _field_bytes(2, content)                                 # Contents (LogContent)
    return out


def encode_log_group_list(groups: List[Dict[str, Any]]) -> bytes:
    """groups: [{"logs": [(time, {k: v})], "topic": str, "source": str, "category": str, "tags": {k: v}}]"""
    out = bytearray()
    for g in groups:
        gb = bytearray()
        for log_time, contents in g["logs"]:
            gb += _field_bytes(1, _encode_log(log_time, contents))       # Logs
        if g.get("category"):
            gb += _field_bytes(2, g["category"].encode("utf-8"))
        if g.get("topic") is not None:
            gb += _field_bytes(3, str(g["topic"]).encode("utf-8"))
        if g.get("source") is not None:
            gb += _field_bytes(4, str(g["source"]).encode("utf-8"))
        for tk, tv in (g.get("tags") or {}).items():                    # LogTags
            gb += _field_bytes(6, _field_bytes(1, str(tk).encode()) + _field_bytes(2, str(tv).encode()))
        out += _field_bytes(1, bytes(gb))                                # LogGroups
    return bytes(out)


def lz4_block_literals(data: bytes) -> bytes:
    """Khối LZ4 hợp lệ chỉ gồm 1 sequence literal (không nén) - đủ cho lz4.UncompressBlock phía Go."""
    n = len(data)
    if n < 15:
        return bytes([n << 4]) + data
    out = bytearray([0xF0])
    rest = n - 15
    while rest >= 255:
        out.append(255)
        rest -= 255
    out.append(rest)
    return bytes(out) + data


# ------------------------------------------------------------------ trạng thái logstore / consumer group
class _Logstore:
    def __init__(self, conf: Dict[str, Any]):
        self.shard_count = max(1, int(conf.get("shards", 2)))
        self.group_size = max(1, int(conf.get("log_group_size", 10)))
        self.topic = conf.get("topic", "actiontrail_audit_event")
        self.source = conf.get("source", "10.0.0.1")
        self.category = conf.get("category", "")
        self.tags = conf.get("tags", {"__hostname__": "mock-sls-producer"})
        self.templates = load_templates(conf, DEFAULT_TEMPLATES)
        rate = float(conf.get("rate_per_shard", 2))
        backlog = float(conf.get("backlog_seconds", 300))
        max_records = conf.get("max_records_per_shard")
        start = time.time()
        self.streams = [RateStream(rate, backlog, max_records, start_time=start) for _ in range(self.shard_count)]
        self.consumer_groups: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()


_stores: Dict[Tuple[str, str], _Logstore] = {}
_stores_lock = threading.Lock()


def _store(project: str, logstore: str, conf: Dict[str, Any]) -> _Logstore:
    key = (project, logstore)
    with _stores_lock:
        if key not in _stores:
            _stores[key] = _Logstore(conf)
            print(f"[SLS] Tạo logstore mock {project}/{logstore}: {_stores[key].shard_count} shard")
        return _stores[key]


def reset_all():
    with _stores_lock:
        _stores.clear()


def inject(project: str, logstore: str, count: int, conf: Dict[str, Any]) -> int:
    """Bơm thêm `count` bản ghi vào mỗi shard (Admin API)."""
    st = _store(project, logstore, conf)
    for s in st.streams:
        s.extra += max(0, int(count))
    return st.shard_count * max(0, int(count))


def snapshot() -> List[Dict[str, Any]]:
    out = []
    with _stores_lock:
        items = list(_stores.items())
    for (project, logstore), st in items:
        with st.lock:
            cgs = {name: {"checkpoints": dict(cg["checkpoints"]),
                          "consumers": {c: round(time.time() - t, 1) for c, t in cg["consumers"].items()}}
                   for name, cg in st.consumer_groups.items()}
        out.append({"project": project, "logstore": logstore, "shards": st.shard_count,
                    "available_per_shard": [s.available() for s in st.streams], "consumer_groups": cgs})
    return out


# ------------------------------------------------------------------ cursor
def _encode_cursor(offset: int) -> str:
    return base64.b64encode(f"mock-sls:{offset}".encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        raw = base64.b64decode(cursor.encode(), validate=False).decode()
        return max(0, int(raw.split(":", 1)[1]))
    except Exception:
        return -1


# ------------------------------------------------------------------ HTTP
def _json(status: int, data: Any, extra: Dict[str, str] = None) -> Tuple[int, Dict[str, str], bytes]:
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Content-Length": str(len(body)),
            "x-log-requestid": uuid.uuid4().hex.upper()[:24]}
    hdrs.update(extra or {})
    return status, hdrs, body


def _error(status: int, code: str, message: str):
    return _json(status, {"errorCode": code, "errorMessage": message})


def _first(params: Dict[str, Any], key: str, default: str = "") -> str:
    v = params.get(key, default)
    return v[0] if isinstance(v, list) else v


def _project_from_host(host: str, conf: Dict[str, Any]) -> str:
    h = host.split(":")[0]
    if conf.get("project"):
        return conf["project"]
    # http://<project>.<endpoint>: endpoint là IP -> project.127.0.0.1, endpoint là domain -> project.cn-hangzhou...
    return h.split(".")[0] if "." in h else (h or "mock-project")


def process(conf: Dict[str, Any], method: str, path: str, host: str, params: Dict[str, Any],
            headers: Dict[str, str], body: str) -> Tuple[int, Dict[str, str], bytes]:
    path = urlparse(path).path
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2 or parts[0] != "logstores":
        return _error(404, "ProjectNotExist", f"Unsupported SLS path: {path}")
    project = _project_from_host(host, conf)
    logstore = parts[1]
    st = _store(project, logstore, conf)

    # /logstores/{ls}/consumergroups[/{cg}]
    if len(parts) >= 3 and parts[2] == "consumergroups":
        if len(parts) == 3:
            if method == "GET":
                with st.lock:
                    return _json(200, [{"name": n, "timeout": cg["timeout"], "order": cg["order"]}
                                       for n, cg in st.consumer_groups.items()])
            if method == "POST":
                data = _load(body)
                name = data.get("consumerGroup") or data.get("name")
                with st.lock:
                    if name in st.consumer_groups:
                        return _error(400, "ConsumerGroupAlreadyExist", f"consumer group {name} already exist")
                    st.consumer_groups[name] = _new_cg(data)
                print(f"[SLS] Tạo consumer group {project}/{logstore}/{name}")
                return _json(200, {})
        cg_name = parts[3]
        with st.lock:
            cg = st.consumer_groups.get(cg_name)
            if cg is None:
                if method == "DELETE":
                    return _error(404, "ConsumerGroupNotExist", f"consumer group {cg_name} does not exist")
                # Mock giữ trạng thái trong RAM: restart mock làm mất consumer group trong khi shipper
                # (consumer library chỉ tạo group lúc khởi động) vẫn heartbeat -> tự tạo lại thay vì 404 mãi.
                st.consumer_groups[cg_name] = cg = _new_cg(_load(body) if method == "PUT" else {})
                print(f"[SLS] Tự tạo lại consumer group {project}/{logstore}/{cg_name} (mock vừa restart?)")
            req_type = _first(params, "type")
            consumer = _first(params, "consumer")
            if method == "PUT":
                d = _load(body)
                cg["timeout"] = int(d.get("timeout", cg["timeout"]))
                cg["order"] = bool(d.get("order", cg["order"]))
                return _json(200, {})
            if method == "POST" and req_type == "heartbeat":
                return _json(200, _heartbeat(st, cg, consumer))
            if method == "POST" and req_type == "checkpoint":
                d = _load(body)
                shard = int(d.get("shard", 0))
                cg["checkpoints"][shard] = {"checkpoint": d.get("checkpoint", ""), "consumer": consumer,
                                            "updateTime": int(time.time() * 1_000_000)}
                return _json(200, {})
            if method == "GET":
                return _json(200, [{"shard": sid, "checkpoint": cp["checkpoint"], "updateTime": cp["updateTime"],
                                    "consumer": cp["consumer"]} for sid, cp in sorted(cg["checkpoints"].items())])
            if method == "DELETE":
                st.consumer_groups.pop(cg_name, None)
                return _json(200, {})
        return _error(400, "ParameterInvalid", f"Unsupported consumer group op {method} type={req_type}")

    # /logstores/{ls}/shards[/{id}]
    if len(parts) >= 3 and parts[2] == "shards":
        if len(parts) == 3:
            now = int(time.time())
            return _json(200, [{"shardID": i, "status": "readwrite", "inclusiveBeginKey": "%032x" % (i * 2**127 // st.shard_count),
                                "exclusiveEndKey": "%032x" % ((i + 1) * 2**127 // st.shard_count), "createTime": now - 86400}
                               for i in range(st.shard_count)])
        try:
            shard = int(parts[3])
        except ValueError:
            return _error(400, "ParameterInvalid", "invalid shard id")
        if shard < 0 or shard >= st.shard_count:
            return _error(400, "ShardNotExist", f"shard {shard} does not exist")
        stream = st.streams[shard]
        req_type = _first(params, "type")
        if req_type == "cursor":
            frm = _first(params, "from", "end")
            if frm == "begin":
                off = 0
            elif frm == "end":
                off = stream.available()
            else:
                try:
                    off = stream.offset_at(float(frm))
                except ValueError:
                    return _error(400, "ParameterInvalid", f"invalid from: {frm}")
            return _json(200, {"cursor": _encode_cursor(off)})
        if req_type == "logs":
            return _pull(st, shard, _first(params, "cursor"), int(_first(params, "count", "1000") or 1000))
        return _error(400, "ParameterInvalid", f"unsupported shard request type={req_type}")

    return _error(404, "ParameterInvalid", f"Unsupported SLS path: {path}")


def _load(body: str) -> Dict[str, Any]:
    try:
        d = json.loads(body) if body else {}
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _new_cg(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"timeout": int(data.get("timeout", 60)), "order": bool(data.get("order", False)),
            "checkpoints": {}, "consumers": {}}


def _heartbeat(st: _Logstore, cg: Dict[str, Any], consumer: str) -> List[int]:
    """Chia shard đều cho các consumer còn sống (heartbeat trong `timeout` giây)."""
    now = time.time()
    cg["consumers"][consumer] = now
    alive = sorted(c for c, t in cg["consumers"].items() if now - t <= cg["timeout"])
    for c in list(cg["consumers"]):
        if c not in alive:
            cg["consumers"].pop(c, None)
    idx = alive.index(consumer)
    return [s for s in range(st.shard_count) if s % len(alive) == idx]


def _pull(st: _Logstore, shard: int, cursor: str, count: int):
    offset = _decode_cursor(cursor)
    if offset < 0:
        return _error(400, "InvalidCursor", f"cursor {cursor} is invalid")
    stream = st.streams[shard]
    end = min(stream.available(), offset + max(1, count) * st.group_size)
    groups = []
    pos = offset
    while pos < end:
        n = min(st.group_size, end - pos)
        logs = []
        for seq in range(pos, pos + n):
            t = stream.event_time(seq)
            tpl = st.templates[seq % len(st.templates)]
            rec = render_record(tpl, record_vars(seq, t, shard))
            logs.append((int(t), rec if isinstance(rec, dict) else {"content": str(rec)}))
        groups.append({"logs": logs, "topic": st.topic, "source": st.source, "category": st.category, "tags": st.tags})
        pos += n
    raw = encode_log_group_list(groups) if groups else b""
    payload = lz4_block_literals(raw) if raw else b""
    hdrs = {"Content-Type": "application/x-protobuf", "Content-Length": str(len(payload)),
            "x-log-compresstype": "lz4", "x-log-bodyrawsize": str(len(raw)),
            "x-log-cursor": _encode_cursor(end), "x-log-count": str(len(groups)),
            "x-log-requestid": uuid.uuid4().hex.upper()[:24]}
    return 200, hdrs, payload
