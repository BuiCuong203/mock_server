#!/usr/bin/env python3
"""
Lightweight Mock MongoDB server (Wire Protocol OP_MSG & OP_QUERY)
Listening on 127.0.0.1:27017
Designed specifically for CyM-Log-Shipper (go.mongodb.org/mongo-driver)
"""

import sys
import time
import struct
import socket
import threading

def encode_cstring(s):
    return s.encode("utf-8") + b"\x00"

def encode_string(s):
    b = s.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(b)) + b

def encode_doc(d):
    body = b""
    for k, v in d.items():
        if isinstance(v, bool):
            body += b"\x08" + encode_cstring(k) + (b"\x01" if v else b"\x00")
        elif isinstance(v, int):
            if k in ("id", "cursorId", "last_query") or v > 2147483647 or v < -2147483648:
                body += b"\x12" + encode_cstring(k) + struct.pack("<q", v)
            else:
                body += b"\x10" + encode_cstring(k) + struct.pack("<i", v)
        elif isinstance(v, float):
            body += b"\x01" + encode_cstring(k) + struct.pack("<d", v)
        elif isinstance(v, str):
            body += b"\x02" + encode_cstring(k) + encode_string(v)
        elif isinstance(v, dict):
            body += b"\x03" + encode_cstring(k) + encode_doc(v)
        elif isinstance(v, list):
            arr_dict = {str(i): x for i, x in enumerate(v)}
            body += b"\x04" + encode_cstring(k) + encode_doc(arr_dict)
        elif v is None:
            body += b"\x0a" + encode_cstring(k)
    total_len = len(body) + 5
    return struct.pack("<i", total_len) + body + b"\x00"

def decode_doc(data, offset=0):
    if len(data) < offset + 4:
        return {}, offset
    total_len = struct.unpack_from("<i", data, offset)[0]
    pos = offset + 4
    end = offset + total_len - 1
    doc = {}
    while pos < end:
        elem_type = data[pos]
        pos += 1
        name_end = data.find(b"\x00", pos)
        if name_end == -1:
            break
        key = data[pos:name_end].decode("utf-8", errors="replace")
        pos = name_end + 1
        if elem_type == 1: # double
            val = struct.unpack_from("<d", data, pos)[0]
            pos += 8
        elif elem_type == 2: # string
            s_len = struct.unpack_from("<i", data, pos)[0]
            val = data[pos+4 : pos+4+s_len-1].decode("utf-8", errors="replace")
            pos += 4 + s_len
        elif elem_type == 3: # document
            val, pos = decode_doc(data, pos)
        elif elem_type == 4: # array
            arr_doc, pos = decode_doc(data, pos)
            val = [arr_doc[str(i)] for i in range(len(arr_doc))]
        elif elem_type == 8: # bool
            val = (data[pos] == 1)
            pos += 1
        elif elem_type == 10: # null
            val = None
        elif elem_type == 16: # int32
            val = struct.unpack_from("<i", data, pos)[0]
            pos += 4
        elif elem_type == 18: # int64
            val = struct.unpack_from("<q", data, pos)[0]
            pos += 8
        else:
            break
        doc[key] = val
    return doc, offset + total_len

# Database storage in memory
STORAGE = {
    "log_source": [
        {
            "_id": "cloudwatch_01",
            "protocol_properties": {
                "log_group_name": "cloudwatch_01",
                "log_group_arn": "arn:aws:logs:us-east-1:123456789012:log-group:cloudwatch_01:*"
            },
            "last_query": int(time.time() * 1000) - 60000,
            "value": {
                "last_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
            }
        },
        {
            "_id": "365_1",
            "value": {
                "last_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
            }
        }
    ]
}

def handle_command(cmd, doc):
    cmd_lower = cmd.lower()
    if cmd_lower in ("ismaster", "hello"):
        return {
            "ismaster": True,
            "maxBsonObjectSize": 16777216,
            "maxMessageSizeBytes": 48000000,
            "maxWriteBatchSize": 100000,
            "logicalSessionTimeoutMinutes": 30,
            "minWireVersion": 0,
            "maxWireVersion": 13,
            "readOnly": False,
            "ok": 1.0
        }
    elif cmd_lower == "buildinfo":
        return {
            "version": "5.0.0",
            "gitVersion": "mock",
            "modules": [],
            "allocator": "tcmalloc",
            "javascriptEngine": "mozjs",
            "sysInfo": "Linux",
            "versionArray": [5, 0, 0, 0],
            "bits": 64,
            "debug": False,
            "maxBsonObjectSize": 16777216,
            "ok": 1.0
        }
    elif cmd_lower == "find":
        col_name = doc.get("find", "log_source")
        docs = STORAGE.get(col_name, [])
        return {
            "cursor": {
                "id": 0,
                "ns": f"siem.{col_name}",
                "firstBatch": docs
            },
            "ok": 1.0
        }
    elif cmd_lower == "update":
        updates = doc.get("updates", [])
        now_ts = int(time.time())
        now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now_ts))
        for u in updates:
            u_doc = u.get("u", {})
            set_doc = u_doc.get("$set", {}) if isinstance(u_doc, dict) else {}
            lq = set_doc.get("last_query")
            if lq is not None:
                lq_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(lq))
                delta = now_ts - lq
                print(f"\n🎯 [MOCK MONGO UPDATE] Thoi gian thuc te (Now): {now_str} ({now_ts})")
                print(f"   Checkpoint ghi vao Mongo (last_query):     {lq_str} ({lq})")
                print(f"   👉 Chenh lech (Now - last_query):          {delta} giay\n")
        return {
            "n": len(updates),
            "nModified": len(updates),
            "ok": 1.0
        }
    elif cmd_lower == "insert":
        return {
            "n": 1,
            "ok": 1.0
        }
    else:
        return {"ok": 1.0}

def handle_client(sock, addr):
    req_id = 1000
    try:
        while True:
            header_bytes = sock.recv(16)
            if not header_bytes or len(header_bytes) < 16:
                break
            msg_len, client_req_id, resp_to, op_code = struct.unpack("<iiii", header_bytes)
            remaining_bytes = sock.recv(msg_len - 16)
            if len(remaining_bytes) < msg_len - 16:
                break

            req_id += 1
            if op_code == 2013: # OP_MSG
                flag_bits = struct.unpack_from("<I", remaining_bytes, 0)[0]
                section_kind = remaining_bytes[4]
                if section_kind == 0:
                    doc, _ = decode_doc(remaining_bytes, 5)
                    # Detect command
                    cmd = next(iter(doc.keys()), "unknown")
                    # Special check: command might be hello, isMaster, find, etc.
                    for k in ("isMaster", "ismaster", "hello", "buildInfo", "buildinfo", "find", "update", "insert", "saslStart", "saslContinue"):
                        if k in doc:
                            cmd = k
                            break
                    reply_doc = handle_command(cmd, doc)
                    enc_reply = encode_doc(reply_doc)
                    
                    # Construct OP_MSG response
                    msg_body = b"\x00\x00\x00\x00" + b"\x00" + enc_reply # flagBits + section 0 + doc
                    resp_header = struct.pack("<iiii", 16 + len(msg_body), req_id, client_req_id, 2013)
                    sock.sendall(resp_header + msg_body)

            elif op_code == 2004: # OP_QUERY
                flags, = struct.unpack_from("<i", remaining_bytes, 0)
                name_end = remaining_bytes.find(b"\x00", 4)
                full_col = remaining_bytes[4:name_end].decode("utf-8", errors="replace")
                pos = name_end + 1 + 8 # skip numberToSkip, numberToReturn
                doc, _ = decode_doc(remaining_bytes, pos)
                cmd = full_col.split(".")[-1]
                if cmd.startswith("$cmd"):
                    cmd = next(iter(doc.keys()), "unknown")
                reply_doc = handle_command(cmd, doc)
                enc_reply = encode_doc(reply_doc)
                
                # Construct OP_REPLY response
                # responseFlags(4) + cursorID(8) + startingFrom(4) + numberReturned(4) + docs
                reply_body = struct.pack("<iqii", 0, 0, 0, 1) + enc_reply
                resp_header = struct.pack("<iiii", 16 + len(reply_body), req_id, client_req_id, 1)
                sock.sendall(resp_header + reply_body)
    except Exception as e:
        pass
    finally:
        sock.close()

def run_server(port=27017):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(10)
    print(f"[*] Mock MongoDB Server listening on 0.0.0.0:{port}...")
    sys.stdout.flush()
    while True:
        try:
            sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(sock, addr), daemon=True)
            t.start()
        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 27017
    run_server(port)
