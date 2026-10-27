"""
Codec AMQP 1.0 tối giản (đủ cho mock Azure Event Hubs nói chuyện với go-amqp / azure-event-hubs-go).

Kiểu dữ liệu khi MÃ HÓA (Python -> AMQP):
  None -> null, bool -> boolean, str -> string, bytes -> binary, int -> long, float -> double,
  dict -> map, list -> list, Sym("x") -> symbol, UByte/UShort/UInt/ULong/Int/Long -> số đúng kiểu,
  Timestamp(ms) -> timestamp, Array([...], "sym"|"str"|...) -> array, Described(descriptor, value).
Khi GIẢI MÃ: số nguyên -> int, symbol -> Sym, timestamp -> Timestamp, described -> Described, array -> list.
"""
import struct
from typing import Any, List, Tuple


class Sym(str):
    """AMQP symbol."""


class UByte(int): pass
class UShort(int): pass
class UInt(int): pass
class ULong(int): pass
class Int(int): pass
class Long(int): pass
class Timestamp(int):
    """Epoch mili giây."""


class Described:
    __slots__ = ("descriptor", "value")

    def __init__(self, descriptor, value):
        self.descriptor = descriptor
        self.value = value

    def __repr__(self):
        return f"Described({self.descriptor!r}, {self.value!r})"


class Array:
    """Mảng AMQP cùng kiểu phần tử: kind = sym | str | uint | ulong | long | int."""
    __slots__ = ("items", "kind")

    def __init__(self, items, kind: str = "sym"):
        self.items = list(items)
        self.kind = kind


# ------------------------------------------------------------------ encode
def encode(v: Any) -> bytes:
    if v is None:
        return b"\x40"
    if isinstance(v, bool):
        return b"\x41" if v else b"\x42"
    if isinstance(v, Described):
        desc = v.descriptor
        if isinstance(desc, int) and not isinstance(desc, ULong):
            desc = ULong(desc)            # descriptor số luôn là ulong
        return b"\x00" + encode(desc) + encode(v.value)
    if isinstance(v, Sym):
        b = v.encode("ascii", "replace")
        return (b"\xa3" + bytes([len(b)]) + b) if len(b) < 256 else (b"\xb3" + struct.pack(">I", len(b)) + b)
    if isinstance(v, str):
        b = v.encode("utf-8")
        return (b"\xa1" + bytes([len(b)]) + b) if len(b) < 256 else (b"\xb1" + struct.pack(">I", len(b)) + b)
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        return (b"\xa0" + bytes([len(b)]) + b) if len(b) < 256 else (b"\xb0" + struct.pack(">I", len(b)) + b)
    if isinstance(v, UByte):
        return b"\x50" + struct.pack(">B", v)
    if isinstance(v, UShort):
        return b"\x60" + struct.pack(">H", v)
    if isinstance(v, UInt):
        if v == 0:
            return b"\x43"
        return (b"\x52" + bytes([v])) if v < 256 else (b"\x70" + struct.pack(">I", v))
    if isinstance(v, ULong):
        if v == 0:
            return b"\x44"
        return (b"\x53" + bytes([v])) if v < 256 else (b"\x80" + struct.pack(">Q", v))
    if isinstance(v, Int):
        return (b"\x54" + struct.pack(">b", v)) if -128 <= v < 128 else (b"\x71" + struct.pack(">i", v))
    if isinstance(v, Timestamp):
        return b"\x83" + struct.pack(">q", v)
    if isinstance(v, int):        # Long hoặc int thường
        return (b"\x55" + struct.pack(">b", v)) if -128 <= v < 128 else (b"\x81" + struct.pack(">q", v))
    if isinstance(v, float):
        return b"\x82" + struct.pack(">d", v)
    if isinstance(v, Array):
        return _encode_array(v)
    if isinstance(v, dict):
        body = b"".join(encode(k) + encode(val) for k, val in v.items())
        return b"\xd1" + struct.pack(">II", len(body) + 4, len(v) * 2) + body
    if isinstance(v, (list, tuple)):
        if not v:
            return b"\x45"
        body = b"".join(encode(x) for x in v)
        return b"\xd0" + struct.pack(">II", len(body) + 4, len(v)) + body
    raise TypeError(f"Không mã hóa được kiểu {type(v)}")


_ARRAY_CTORS = {
    "sym": (b"\xb3", lambda x: struct.pack(">I", len(x.encode())) + x.encode()),
    "str": (b"\xb1", lambda x: struct.pack(">I", len(x.encode("utf-8"))) + x.encode("utf-8")),
    "uint": (b"\x70", lambda x: struct.pack(">I", x)),
    "ulong": (b"\x80", lambda x: struct.pack(">Q", x)),
    "long": (b"\x81", lambda x: struct.pack(">q", x)),
    "int": (b"\x71", lambda x: struct.pack(">i", x)),
}


def _encode_array(a: Array) -> bytes:
    ctor, enc = _ARRAY_CTORS[a.kind]
    body = ctor + b"".join(enc(x) for x in a.items)
    return b"\xf0" + struct.pack(">II", len(body) + 4, len(a.items)) + body


# ------------------------------------------------------------------ decode
class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0):
        self.buf = buf
        self.pos = pos

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise ValueError("AMQP: hết dữ liệu khi giải mã")
        b = self.buf[self.pos:self.pos + n]
        self.pos += n
        return b

    def u8(self) -> int:
        return self.take(1)[0]


def decode(buf: bytes, pos: int = 0) -> Tuple[Any, int]:
    r = _Reader(buf, pos)
    v = _decode_value(r)
    return v, r.pos


def decode_all(buf: bytes) -> List[Any]:
    out, pos = [], 0
    while pos < len(buf):
        v, pos = decode(buf, pos)
        out.append(v)
    return out


def _decode_value(r: _Reader, code: int = None) -> Any:
    if code is None:
        code = r.u8()
    if code == 0x00:
        desc = _decode_value(r)
        return Described(desc, _decode_value(r))
    return _decode_body(r, code)


def _decode_body(r: _Reader, code: int) -> Any:
    if code == 0x40:
        return None
    if code == 0x41:
        return True
    if code == 0x42:
        return False
    if code == 0x56:
        return r.u8() != 0
    if code in (0x43, 0x44):
        return 0
    if code in (0x50, 0x52, 0x53):
        return r.u8()
    if code == 0x51:
        return struct.unpack(">b", r.take(1))[0]
    if code in (0x54, 0x55):
        return struct.unpack(">b", r.take(1))[0]
    if code == 0x60:
        return struct.unpack(">H", r.take(2))[0]
    if code == 0x61:
        return struct.unpack(">h", r.take(2))[0]
    if code == 0x70:
        return struct.unpack(">I", r.take(4))[0]
    if code == 0x71:
        return struct.unpack(">i", r.take(4))[0]
    if code == 0x72:
        return struct.unpack(">f", r.take(4))[0]
    if code == 0x73:                               # char (utf32)
        return chr(struct.unpack(">I", r.take(4))[0])
    if code == 0x80:
        return struct.unpack(">Q", r.take(8))[0]
    if code == 0x81:
        return struct.unpack(">q", r.take(8))[0]
    if code == 0x82:
        return struct.unpack(">d", r.take(8))[0]
    if code == 0x83:
        return Timestamp(struct.unpack(">q", r.take(8))[0])
    if code == 0x98:
        return r.take(16)
    if code == 0xa0:
        return r.take(r.u8())
    if code == 0xb0:
        return r.take(struct.unpack(">I", r.take(4))[0])
    if code == 0xa1:
        return r.take(r.u8()).decode("utf-8", "replace")
    if code == 0xb1:
        return r.take(struct.unpack(">I", r.take(4))[0]).decode("utf-8", "replace")
    if code == 0xa3:
        return Sym(r.take(r.u8()).decode("ascii", "replace"))
    if code == 0xb3:
        return Sym(r.take(struct.unpack(">I", r.take(4))[0]).decode("ascii", "replace"))
    if code == 0x45:
        return []
    if code in (0xc0, 0xd0, 0xc1, 0xd1):
        if code in (0xc0, 0xc1):
            r.u8()
            count = r.u8()
        else:
            r.take(4)
            count = struct.unpack(">I", r.take(4))[0]
        items = [_decode_value(r) for _ in range(count)]
        if code in (0xc1, 0xd1):
            return {_hashable(items[i]): items[i + 1] for i in range(0, len(items), 2)}
        return items
    if code in (0xe0, 0xf0):
        if code == 0xe0:
            r.u8()
            count = r.u8()
        else:
            r.take(4)
            count = struct.unpack(">I", r.take(4))[0]
        elem = r.u8()
        desc = None
        if elem == 0x00:
            desc = _decode_value(r)
            elem = r.u8()
        items = [_decode_body(r, elem) for _ in range(count)]
        return [Described(desc, x) for x in items] if desc is not None else items
    raise ValueError(f"AMQP: type code không hỗ trợ 0x{code:02x}")


def _hashable(k: Any) -> Any:
    if isinstance(k, Described):
        return (k.descriptor, _hashable(k.value))
    if isinstance(k, list):
        return tuple(k)
    return k


# ------------------------------------------------------------------ frame
FRAME_AMQP = 0
FRAME_SASL = 1


def encode_frame(channel: int, performative: Any, payload: bytes = b"", frame_type: int = FRAME_AMQP) -> bytes:
    body = (encode(performative) if performative is not None else b"") + payload
    return struct.pack(">IBBH", 8 + len(body), 2, frame_type, channel) + body


def field(fields: List[Any], idx: int, default=None):
    """Lấy phần tử thứ idx của list performative (thiếu -> default)."""
    if idx < len(fields) and fields[idx] is not None:
        return fields[idx]
    return default


def descriptor_code(d: Described) -> Any:
    """Descriptor dạng số (0x10...) hoặc symbol ("amqp:open:list") -> số nếu biết."""
    return _SYMBOLIC.get(d.descriptor, d.descriptor) if isinstance(d.descriptor, str) else d.descriptor


_SYMBOLIC = {
    "amqp:open:list": 0x10, "amqp:begin:list": 0x11, "amqp:attach:list": 0x12, "amqp:flow:list": 0x13,
    "amqp:transfer:list": 0x14, "amqp:disposition:list": 0x15, "amqp:detach:list": 0x16, "amqp:end:list": 0x17,
    "amqp:close:list": 0x18, "amqp:sasl-init:list": 0x41, "amqp:sasl-response:list": 0x43,
    "amqp:source:list": 0x28, "amqp:target:list": 0x29,
    "amqp:properties:list": 0x73, "amqp:application-properties:map": 0x74, "amqp:data:binary": 0x75,
    "amqp:amqp-value:*": 0x77, "amqp:header:list": 0x70, "amqp:message-annotations:map": 0x72,
}


# ------------------------------------------------------------------ message
def encode_message(*, annotations: dict = None, properties: dict = None, app_props: dict = None,
                   data: bytes = None, value: Any = None, has_value: bool = False) -> bytes:
    out = b""
    if annotations:
        out += encode(Described(ULong(0x72), annotations))
    if properties:
        order = ["message-id", "user-id", "to", "subject", "reply-to", "correlation-id", "content-type",
                 "content-encoding", "absolute-expiry-time", "creation-time", "group-id", "group-sequence",
                 "reply-to-group-id"]
        lst = [properties.get(k) for k in order]
        while lst and lst[-1] is None:
            lst.pop()
        out += encode(Described(ULong(0x73), lst))
    if app_props:
        out += encode(Described(ULong(0x74), app_props))
    if data is not None:
        out += encode(Described(ULong(0x75), bytes(data)))
    if has_value or value is not None:
        out += encode(Described(ULong(0x77), value))
    return out


def decode_message(payload: bytes) -> dict:
    msg = {"properties": {}, "app_props": {}, "annotations": {}, "data": [], "value": None}
    for sec in decode_all(payload):
        if not isinstance(sec, Described):
            continue
        code = descriptor_code(sec)
        if code == 0x73 and isinstance(sec.value, list):
            names = ["message-id", "user-id", "to", "subject", "reply-to", "correlation-id"]
            for i, n in enumerate(names):
                msg["properties"][n] = field(sec.value, i)
        elif code == 0x74 and isinstance(sec.value, dict):
            msg["app_props"] = dict(sec.value)
        elif code == 0x72 and isinstance(sec.value, dict):
            msg["annotations"] = dict(sec.value)
        elif code == 0x75:
            msg["data"].append(sec.value)
        elif code == 0x77:
            msg["value"] = sec.value
    return msg
