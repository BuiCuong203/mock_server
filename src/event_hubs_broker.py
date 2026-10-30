"""
Mock Azure Event Hubs Broker over WebSocket / AMQP 1.0 cho input `azure_event_hubs` của CyM-Log-Shipper.

Shipper (Event Processor Host / azure-event-hubs-go v3) kết nối qua HTTPS CONNECT proxy tới:
  wss://<namespace>.servicebus.windows.net/$servicebus/websocket (subprotocol amqp)
và dùng Azure Blob Storage (*.blob.core.windows.net) để checkpoint / lease partitions.

Broker AMQP 1.0 hỗ trợ:
  1. Handshake WebSocket (Sec-WebSocket-Protocol: amqp)
  2. SASL (ANONYMOUS, PLAIN, MSSBCBS) -> sasl-outcome 0 (OK)
  3. AMQP Open + Begin session
  4. Phiên CBS ($cbs): tiếp nhận put-token, trả về status-code 200 OK
  5. Phiên $management: trả về partition info (com.microsoft:eventhub, com.microsoft:partition)
  6. Partition Receiver streaming: gắn luồng RateStream cho từng partition, sinh log theo template
     {"records": [...]} bọc trong AMQP message annotations (x-opt-offset, x-opt-sequence-number...).
"""
import base64
import json
import os
import re
import socket
import struct
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import amqp_codec as codec
from .amqp_codec import Described, Int, Long, Sym, UByte, UInt, ULong, UShort, Timestamp
from .config import BASE_DIR
from .stream_common import RateStream, load_templates, record_vars, render_record

DEFAULT_TEMPLATES = [
    {
        "time": "{{EVENT_TIME_ISO}}",
        "resourceId": "/SUBSCRIPTIONS/00000000-0000-0000-0000-000000000000/RESOURCEGROUPS/RG-SIEM/PROVIDERS/MICROSOFT.KEYVAULT/VAULTS/KV-MOCK",
        "operationName": "{{CHOICE:VaultGet|SecretGet|SecretSet|KeyDelete|Authentication}}",
        "category": "{{CHOICE:AuditEvent|SignInLogs|AzureActivity}}",
        "resultType": "{{CHOICE:Success|Success|Success|Failure}}",
        "callerIpAddress": "{{RANDOM_INT:1:223}}.{{RANDOM_INT:0:255}}.{{RANDOM_INT:0:255}}.{{RANDOM_INT:1:254}}",
        "identity": {"claim": {"upn": "{{CHOICE:admin@contoso.com|devops@contoso.com|svc-backup@contoso.com}}"}},
        "correlationId": "{{UUID}}",
        "seq": "{{SEQ}}",
        "partition": "{{PARTITION}}",
    }
]

# ------------------------------------------------------------------ Quản lý cấu hình & streams
_config_lock = threading.RLock()
_hub_configs: Dict[str, Any] = {}
_hub_streams: Dict[Tuple[str, str], RateStream] = {}  # (hub, partition) -> RateStream
_active_sessions: List[Any] = []


def _load_hub_config(hub_name: str) -> Dict[str, Any]:
    global _hub_configs
    config_path = os.path.join(BASE_DIR, "streams", "azure_event_hubs.json")
    if not _hub_configs:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _hub_configs = json.load(f)
        except Exception as e:
            print(f"[EVENT_HUBS] Không đọc được {config_path}: {e}, dùng default")
            _hub_configs = {}

    default_conf = _hub_configs.get("default", {})
    specific = _hub_configs.get("hubs", {}).get(hub_name, {})
    conf = dict(default_conf)
    conf.update(specific)
    if "partition_count" not in conf:
        conf["partition_count"] = 2
    if "rate_per_partition" not in conf:
        conf["rate_per_partition"] = 1
    if "backlog_seconds" not in conf:
        conf["backlog_seconds"] = 120
    if "records_per_event" not in conf:
        conf["records_per_event"] = 2
    if "templates" not in conf:
        conf["templates"] = DEFAULT_TEMPLATES
    return conf


def get_stream(hub_name: str, partition_id: str) -> Tuple[RateStream, Dict[str, Any]]:
    key = (hub_name, str(partition_id))
    with _config_lock:
        conf = _load_hub_config(hub_name)
        if key not in _hub_streams:
            rate = float(conf.get("rate_per_partition", 1))
            backlog = float(conf.get("backlog_seconds", 120))
            _hub_streams[key] = RateStream(rate, backlog_seconds=backlog)
            print(f"[EVENT_HUBS] Khởi tạo RateStream cho {hub_name}/p{partition_id} (rate={rate}/s, backlog={backlog}s)")
        return _hub_streams[key], conf


def inject(hub_name: str, count: int) -> int:
    with _config_lock:
        conf = _load_hub_config(hub_name)
        p_count = int(conf.get("partition_count", 2))
        total = 0
        for p in range(p_count):
            st, _ = get_stream(hub_name, str(p))
            st.extra += max(0, int(count))
            total += max(0, int(count))
        return total


def snapshot() -> Dict[str, Any]:
    with _config_lock:
        out = {}
        for (h, p), st in _hub_streams.items():
            if h not in out:
                out[h] = {"partitions": {}}
            out[h]["partitions"][p] = {
                "available": st.available(),
                "rate": st.rate,
                "extra": st.extra,
            }
        out["connected_sessions"] = len(_active_sessions)
        return out


def reset():
    with _config_lock:
        _hub_streams.clear()


# ------------------------------------------------------------------ WebSocket Helper
def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("Socket closed")
        buf.extend(chunk)
    return bytes(buf)


def read_ws_frame(sock: socket.socket) -> Tuple[int, bytes]:
    """Đọc 1 frame WebSocket (FIN, unmasked payload)."""
    h = _recv_exact(sock, 2)
    opcode = h[0] & 0x0F
    masked = (h[1] & 0x80) != 0
    payload_len = h[1] & 0x7F
    if payload_len == 126:
        payload_len = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif payload_len == 127:
        payload_len = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if masked else None
    payload = bytearray(_recv_exact(sock, payload_len))
    if mask:
        for i in range(len(payload)):
            payload[i] ^= mask[i % 4]
    return opcode, bytes(payload)


def send_ws_frame(sock: socket.socket, data: bytes, opcode: int = 2):
    """Gửi 1 frame WebSocket không mask từ server."""
    length = len(data)
    hdr = bytearray([0x80 | (opcode & 0x0F)])
    if length < 126:
        hdr.append(length)
    elif length <= 0xFFFF:
        hdr.append(126)
        hdr.extend(struct.pack(">H", length))
    else:
        hdr.append(127)
        hdr.extend(struct.pack(">Q", length))
    sock.sendall(bytes(hdr) + data)


# ------------------------------------------------------------------ AMQP Session over WebSocket
class _Link:
    def __init__(self, handle: int, name: str, role: bool, source_addr: str, target_addr: str, filter_map: Any = None):
        self.handle = handle
        self.name = name
        self.role = role  # vai trò phía server: True = server là receiver, False = server là sender
        self.source_addr = source_addr
        self.target_addr = target_addr
        self.filter_map = filter_map
        self.credit = 0
        self.delivery_count = 0
        # Dành cho partition streaming
        self.is_partition = False
        self.hub_name = ""
        self.consumer_group = "$Default"
        self.partition_id = "0"
        self.stream: Optional[RateStream] = None
        self.conf: Optional[Dict[str, Any]] = None
        self.current_seq = 0


class EventHubsSession:
    def __init__(self, sock: socket.socket, host: str):
        self.sock = sock
        self.host = host
        self.send_lock = threading.Lock()
        self.running = True

        # State machine AMQP
        self.sasl_done = False
        self.amqp_done = False
        self.next_incoming_id = 1
        self.next_outgoing_id = 1
        self.delivery_id_seq = 0

        # Links: handle -> _Link
        self.links: Dict[int, _Link] = {}
        self.cbs_rx_handle: Optional[int] = None
        self.mgmt_rx_handle: Optional[int] = None
        self.partition_links: List[_Link] = []

        # Buffer dữ liệu nhị phân AMQP từ các WS frames
        self.in_buf = bytearray()

    def send_raw_amqp(self, data: bytes):
        with self.send_lock:
            send_ws_frame(self.sock, data, opcode=2)

    def send_amqp_frame(self, channel: int, performative: Any, payload: bytes = b"", frame_type: int = codec.FRAME_AMQP):
        frame_bytes = codec.encode_frame(channel, performative, payload=payload, frame_type=frame_type)
        self.send_raw_amqp(frame_bytes)

    def run(self):
        with _config_lock:
            _active_sessions.append(self)
        try:
            self.sock.settimeout(60.0)
            # Khởi động thread stream partitions
            streamer_thread = threading.Thread(target=self._partition_streaming_loop, daemon=True)
            streamer_thread.start()

            while self.running:
                opcode, payload = read_ws_frame(self.sock)
                if opcode == 8:  # Close
                    self.send_raw_amqp(b"")  # Hoặc gửi close opcode 8
                    break
                if opcode == 9:  # Ping
                    with self.send_lock:
                        send_ws_frame(self.sock, payload, opcode=10)  # Pong
                    continue
                if opcode == 2 or opcode == 0:  # Binary (hoặc continuation)
                    self.in_buf.extend(payload)
                    self._process_amqp_buffer()
        except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
            pass
        except Exception as e:
            print(f"[EVENT_HUBS] Lỗi phiên AMQP: {e}")
        finally:
            self.running = False
            with _config_lock:
                if self in _active_sessions:
                    _active_sessions.remove(self)
            try:
                self.sock.close()
            except Exception:
                pass
            print(f"[EVENT_HUBS] Đã đóng kết nối từ {self.host}")

    def _process_amqp_buffer(self):
        while len(self.in_buf) >= 8:
            # 1. Kiểm tra protocol header
            if self.in_buf.startswith(b"AMQP"):
                proto_id = self.in_buf[4]
                header = bytes(self.in_buf[:8])
                self.in_buf = self.in_buf[8:]

                if proto_id == 3:  # SASL
                    # Đáp lại SASL header
                    self.send_raw_amqp(b"AMQP\x03\x01\x00\x00")
                    # Gửi sasl-mechanisms (descriptor 0x40)
                    mechs = Described(ULong(0x40), [[Sym("ANONYMOUS"), Sym("MSSBCBS"), Sym("PLAIN")]])
                    self.send_amqp_frame(channel=0, performative=mechs, frame_type=codec.FRAME_SASL)
                    continue

                if proto_id == 0:  # AMQP 1.0
                    self.send_raw_amqp(b"AMQP\x00\x01\x00\x00")
                    self.amqp_done = True
                    continue

            # 2. Xử lý Frame thông thường
            size = struct.unpack(">I", self.in_buf[:4])[0]
            if len(self.in_buf) < size:
                break  # Chờ thêm dữ liệu frame
            frame_data = bytes(self.in_buf[:size])
            self.in_buf = self.in_buf[size:]

            doff = frame_data[4]
            frame_type = frame_data[5]
            channel = struct.unpack(">H", frame_data[6:8])[0]
            body = frame_data[doff * 4:]

            if not body:
                continue

            perf, pos = codec.decode(body, 0)
            payload = body[pos:]
            self._handle_performative(channel, frame_type, perf, payload)

    def _handle_performative(self, channel: int, frame_type: int, perf: Any, payload: bytes):
        if not isinstance(perf, Described):
            return
        code = codec.descriptor_code(perf)
        val = perf.value if isinstance(perf.value, list) else []

        # ---------------- SASL Handshake ----------------
        if frame_type == codec.FRAME_SASL:
            if code == 0x41:  # sasl-init
                mech = codec.field(val, 0)
                # Chấp nhận mọi cơ chế SASL -> sasl-outcome (code 0: OK)
                outcome = Described(ULong(0x44), [UByte(0)])
                self.send_amqp_frame(channel=0, performative=outcome, frame_type=codec.FRAME_SASL)
                self.sasl_done = True
            return

        # ---------------- AMQP Performatives ----------------
        if code == 0x10:  # open
            client_container = codec.field(val, 0, "client")
            # Gửi open lại
            open_resp = Described(ULong(0x10), [
                "mock-event-hubs", self.host, UInt(65536), UShort(255), UInt(60000)
            ])
            self.send_amqp_frame(channel=channel, performative=open_resp)

        elif code == 0x11:  # begin
            # Gửi begin lại
            begin_resp = Described(ULong(0x11), [
                UShort(channel), UInt(1), UInt(5000), UInt(5000)
            ])
            self.send_amqp_frame(channel=channel, performative=begin_resp)

        elif code == 0x12:  # attach
            name = codec.field(val, 0, "")
            handle = int(codec.field(val, 1, 0))
            role = bool(codec.field(val, 2, False))  # client role (False = client sender, True = client receiver)
            source = codec.field(val, 5)
            target = codec.field(val, 6)

            src_addr = source.value[0] if (source and isinstance(source.value, list) and source.value) else ""
            tgt_addr = target.value[0] if (target and isinstance(target.value, list) and target.value) else ""

            server_role = not role
            link = _Link(handle, name, server_role, src_addr, tgt_addr)
            self.links[handle] = link

            # Phản hồi attach
            attach_resp = Described(ULong(0x12), [
                name, UInt(handle), server_role, UByte(0), UByte(0),
                source, target, None, False,
                UInt(0) if not server_role else None,
                ULong(65536)
            ])
            self.send_amqp_frame(channel=channel, performative=attach_resp)

            # Nếu client là SENDER (server là RECEIVER) -> gửi credit ngay để client gửi tin
            if not role:
                flow = Described(ULong(0x13), [
                    UInt(self.next_incoming_id), UInt(5000), UInt(self.next_outgoing_id), UInt(5000),
                    UInt(handle), UInt(0), UInt(100), UInt(0), False, False
                ])
                self.send_amqp_frame(channel=channel, performative=flow)

            # Nếu client là RECEIVER:
            if role:
                if src_addr == "$cbs":
                    self.cbs_rx_handle = handle
                elif src_addr == "$management":
                    self.mgmt_rx_handle = handle
                elif "Partitions/" in src_addr:
                    # Link nhận log partition (ví dụ: "insights-logs/ConsumerGroups/$Default/Partitions/0")
                    link.is_partition = True
                    parts = src_addr.strip("/").split("/")
                    link.hub_name = parts[0]
                    link.consumer_group = parts[2] if len(parts) >= 3 else "$Default"
                    link.partition_id = parts[-1]
                    link.stream, link.conf = get_stream(link.hub_name, link.partition_id)

                    # Đọc filter nếu có (x-opt-offset / x-opt-enqueuedtimeutc)
                    filter_map = source.value[7] if (source and len(source.value) > 7) else None
                    link.filter_map = filter_map
                    start_off = 0
                    if filter_map and isinstance(filter_map, dict):
                        for k, v in filter_map.items():
                            fstr = str(v)
                            m_off = re.search(r"x-opt-offset\s*>\s*'?(\d+)'?", fstr)
                            if m_off:
                                start_off = int(m_off.group(1)) + 1
                    link.current_seq = start_off
                    self.partition_links.append(link)
                    print(f"[EVENT_HUBS] Client mở Partition Receiver: {src_addr} (bắt đầu seq={start_off})")

        elif code == 0x13:  # flow
            handle = codec.field(val, 4)
            credit = codec.field(val, 6)
            if handle is not None and credit is not None:
                h = int(handle)
                if h in self.links:
                    self.links[h].credit += int(credit)

        elif code == 0x14:  # transfer
            handle = int(codec.field(val, 0, 0))
            delivery_id = codec.field(val, 1, 0)
            msg = codec.decode_message(payload)
            link = self.links.get(handle)
            tgt_addr = link.target_addr if link else ""

            # 1. Chấp nhận delivery
            disp = Described(ULong(0x15), [
                True, UInt(delivery_id), UInt(delivery_id), True, Described(ULong(0x24), [])
            ])
            self.send_amqp_frame(channel=channel, performative=disp)

            # 2. Xử lý CBS token
            if tgt_addr == "$cbs" or msg.get("app_props", {}).get("operation") == "put-token":
                req_msg_id = msg.get("properties", {}).get("message-id")
                reply_to = msg.get("properties", {}).get("reply-to")
                if self.cbs_rx_handle is not None:
                    resp_payload = codec.encode_message(
                        properties={"correlation-id": req_msg_id, "to": reply_to},
                        app_props={"status-code": Int(200), "status-description": "OK"}
                    )
                    self.delivery_id_seq += 1
                    transfer = Described(ULong(0x14), [
                        UInt(self.cbs_rx_handle), UInt(self.delivery_id_seq),
                        struct.pack(">I", self.delivery_id_seq), UInt(0), True
                    ])
                    self.send_amqp_frame(channel=channel, performative=transfer, payload=resp_payload)
                    print("[EVENT_HUBS] Xác thực CBS thành công: status=200 OK")

            # 3. Xử lý Management ($management)
            elif tgt_addr == "$management" or "operation" in msg.get("app_props", {}):
                op = msg["app_props"].get("operation")
                mtype = msg["app_props"].get("type")
                name = msg["app_props"].get("name", "insights-logs")
                req_msg_id = msg.get("properties", {}).get("message-id")
                conf = _load_hub_config(name)
                p_count = int(conf.get("partition_count", 2))
                p_ids = [str(i) for i in range(p_count)]

                if mtype == "com.microsoft:eventhub":
                    val_data = {
                        "name": name,
                        "partition_count": Int(p_count),
                        "partition_ids": p_ids,
                        "created_at": Timestamp(int(time.time() * 1000))
                    }
                else:  # com.microsoft:partition
                    p_id = str(msg["app_props"].get("partition", "0"))
                    val_data = {
                        "name": name,
                        "partition": p_id,
                        "begin_sequence_number": Long(0),
                        "last_enqueued_sequence_number": Long(100),
                        "last_enqueued_offset": "100",
                        "last_enqueued_time_utc": Timestamp(int(time.time() * 1000)),
                        "is_partition_empty": False
                    }

                if self.mgmt_rx_handle is not None:
                    resp_payload = codec.encode_message(
                        properties={"correlation-id": req_msg_id},
                        app_props={"status-code": Int(200), "status-description": "OK"},
                        value=val_data
                    )
                    self.delivery_id_seq += 1
                    transfer = Described(ULong(0x14), [
                        UInt(self.mgmt_rx_handle), UInt(self.delivery_id_seq),
                        struct.pack(">I", self.delivery_id_seq), UInt(0), True
                    ])
                    self.send_amqp_frame(channel=channel, performative=transfer, payload=resp_payload)
                    print(f"[EVENT_HUBS] Quản trị $management trả về metadata: {mtype} (hub={name}, partitions={p_ids})")

        elif code == 0x16:  # detach
            handle = codec.field(val, 0)
            if handle is not None:
                detach_resp = Described(ULong(0x16), [UInt(int(handle)), True])
                self.send_amqp_frame(channel=channel, performative=detach_resp)

        elif code == 0x18:  # close
            close_resp = Described(ULong(0x18), [])
            self.send_amqp_frame(channel=channel, performative=close_resp)
            self.running = False

    def _partition_streaming_loop(self):
        """Vòng lặp sinh và bắn event cho các partition receiver có credit."""
        while self.running:
            sent_any = False
            for link in list(self.partition_links):
                if not self.running:
                    break
                if not link.is_partition or link.credit <= 0 or not link.stream:
                    continue

                available = link.stream.available()
                if link.current_seq < available:
                    conf = link.conf or {}
                    records_per_event = int(conf.get("records_per_event", 2))
                    tpls = load_templates(conf, DEFAULT_TEMPLATES)

                    # Sinh một batch bản ghi
                    records = []
                    ev_time = link.stream.event_time(link.current_seq)
                    for r_idx in range(records_per_event):
                        seq_no = link.current_seq * records_per_event + r_idx
                        tpl = tpls[seq_no % len(tpls)]
                        v = record_vars(seq_no, ev_time, partition=link.partition_id)
                        records.append(render_record(tpl, v))

                    # Event payload theo định dạng Event Hubs: {"records": [...]}
                    body_bytes = json.dumps({"records": records}, ensure_ascii=False).encode("utf-8")
                    annotations = {
                        Sym("x-opt-sequence-number"): Long(link.current_seq),
                        Sym("x-opt-offset"): str(link.current_seq),
                        Sym("x-opt-enqueued-time"): Timestamp(int(ev_time * 1000)),
                        Sym("x-opt-partition-key"): str(link.partition_id),
                    }
                    msg_payload = codec.encode_message(
                        annotations=annotations,
                        properties={"message-id": str(uuid.uuid4())},
                        data=body_bytes
                    )

                    self.delivery_id_seq += 1
                    transfer = Described(ULong(0x14), [
                        UInt(link.handle), UInt(self.delivery_id_seq),
                        struct.pack(">I", self.delivery_id_seq), UInt(0), False
                    ])
                    self.send_amqp_frame(channel=0, performative=transfer, payload=msg_payload)
                    link.credit -= 1
                    link.current_seq += 1
                    sent_any = True
                    print(f"[EVENT_HUBS] Bắn event seq={link.current_seq - 1} vào {link.hub_name}/p{link.partition_id} ({len(records)} log records)")

            if not sent_any:
                time.sleep(0.1)


def handle_websocket(sock: socket.socket, host: str):
    """Điểm tiếp nhận kết nối WebSocket từ proxy_handler."""
    session = EventHubsSession(sock, host)
    session.run()
