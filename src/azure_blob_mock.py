"""
Mock Azure Blob Storage (lưu trong RAM) cho storage leaser / checkpointer của Event Processor Host
(input azure_event_hubs). Shipper gọi https://<storage_account>.blob.core.windows.net/... qua proxy_url
-> mock bóc TLS (CONNECT) rồi xử lý tại đây. Không kiểm tra chữ ký SharedKey.

Hỗ trợ:
  HEAD/GET  /{container}?restype=container              thuộc tính container (404 ContainerNotFound)
  PUT       /{container}?restype=container              tạo container (409 ContainerAlreadyExists)
  DELETE    /{container}?restype=container
  GET       /{container}?restype=container&comp=list    liệt kê blob (XML)
  PUT       /{container}/{blob}                         upload BlockBlob (If-None-Match: *, x-ms-lease-id)
  GET/HEAD  /{container}/{blob}                         tải / thuộc tính (x-ms-lease-state...)
  PUT       /{container}/{blob}?comp=lease              acquire | renew | release | change | break
  DELETE    /{container}/{blob}
"""
import hashlib
import threading
import time
import uuid
from email.utils import formatdate
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse
from xml.sax.saxutils import escape

_lock = threading.Lock()
# (account, container) -> {"created": ts, "etag": str, "blobs": {name: blob}}
_containers: Dict[Tuple[str, str], Dict[str, Any]] = {}


def _http_date(ts: float) -> str:
    return formatdate(ts, usegmt=True)


def _etag() -> str:
    return '"0x' + uuid.uuid4().hex[:15].upper() + '"'


def _base_headers() -> Dict[str, str]:
    return {"x-ms-request-id": str(uuid.uuid4()), "x-ms-version": "2018-03-28", "Date": _http_date(time.time()),
            "Server": "Windows-Azure-Blob/1.0 Microsoft-HTTPAPI/2.0 (cym-mock)"}


def _resp(status: int, headers: Dict[str, str] = None, body: bytes = b"") -> Tuple[int, Dict[str, str], bytes]:
    h = _base_headers()
    h.update(headers or {})
    h["Content-Length"] = str(len(body))
    return status, h, body


def _error(status: int, code: str, message: str):
    body = (f'<?xml version="1.0" encoding="utf-8"?><Error><Code>{code}</Code>'
            f"<Message>{escape(message)}\nRequestId:{uuid.uuid4()}\nTime:{time.strftime('%Y-%m-%dT%H:%M:%S.0000000Z', time.gmtime())}</Message></Error>").encode()
    return _resp(status, {"x-ms-error-code": code, "Content-Type": "application/xml"}, body)


def _lease_state(blob: Dict[str, Any]) -> str:
    """Cập nhật trạng thái lease theo thời gian: leased -> expired, breaking -> broken."""
    lease = blob["lease"]
    now = time.time()
    if lease["state"] == "leased" and lease["expires"] is not None and now >= lease["expires"]:
        lease["state"] = "expired"
    if lease["state"] == "breaking" and now >= lease["break_at"]:
        lease["state"] = "broken"
    return lease["state"]


def _blob_headers(blob: Dict[str, Any]) -> Dict[str, str]:
    state = _lease_state(blob)
    h = {"ETag": blob["etag"], "Last-Modified": _http_date(blob["modified"]), "x-ms-blob-type": "BlockBlob",
         "Content-Type": blob.get("content_type") or "application/octet-stream",
         "Content-MD5": blob["md5"], "x-ms-creation-time": _http_date(blob["created"]),
         "x-ms-lease-state": state, "x-ms-lease-status": "locked" if state == "leased" else "unlocked",
         "Accept-Ranges": "bytes", "x-ms-server-encrypted": "true"}
    if state == "leased":
        h["x-ms-lease-duration"] = "infinite" if blob["lease"]["expires"] is None else "fixed"
    for k, v in blob["metadata"].items():
        h["x-ms-meta-" + k] = v
    return h


def _hdr(headers: Dict[str, str], name: str) -> Optional[str]:
    name = name.lower()
    for k, v in headers.items():
        if k.lower() == name:
            return v
    return None


def handle(method: str, raw_path: str, host: str, params: Dict[str, Any], headers: Dict[str, str],
           body: bytes) -> Tuple[int, Dict[str, str], bytes]:
    account = host.split(":")[0].split(".")[0]
    path = unquote(urlparse(raw_path).path)
    parts = path.lstrip("/").split("/", 1)
    container = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ""
    q = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
    if not container:
        return _error(400, "InvalidUri", "Thiếu tên container")
    key = (account, container)
    with _lock:
        if not blob_name:
            return _container_op(method, key, q)
        return _blob_op(method, key, blob_name, q, headers, body)


def _container_op(method: str, key, q):
    c = _containers.get(key)
    if q.get("restype") != "container":
        return _error(400, "InvalidQueryParameterValue", "restype=container là bắt buộc")
    if q.get("comp") == "list" and method == "GET":
        if c is None:
            return _error(404, "ContainerNotFound", "The specified container does not exist.")
        items = "".join(
            f"<Blob><Name>{escape(n)}</Name><Properties><Last-Modified>{_http_date(b['modified'])}</Last-Modified>"
            f"<Etag>{b['etag']}</Etag><Content-Length>{len(b['data'])}</Content-Length><BlobType>BlockBlob</BlobType>"
            f"<LeaseStatus>{'locked' if _lease_state(b) == 'leased' else 'unlocked'}</LeaseStatus>"
            f"<LeaseState>{_lease_state(b)}</LeaseState></Properties></Blob>"
            for n, b in sorted(c["blobs"].items()))
        xml = (f'<?xml version="1.0" encoding="utf-8"?><EnumerationResults ContainerName="{escape(key[1])}">'
               f"<Blobs>{items}</Blobs><NextMarker /></EnumerationResults>").encode()
        return _resp(200, {"Content-Type": "application/xml"}, xml)
    if method in ("GET", "HEAD"):
        if c is None:
            return _error(404, "ContainerNotFound", "The specified container does not exist.")
        return _resp(200, {"ETag": c["etag"], "Last-Modified": _http_date(c["created"]),
                           "x-ms-lease-state": "available", "x-ms-lease-status": "unlocked",
                           "x-ms-has-immutability-policy": "false", "x-ms-has-legal-hold": "false"})
    if method == "PUT":
        if c is not None:
            return _error(409, "ContainerAlreadyExists", "The specified container already exists.")
        now = time.time()
        _containers[key] = {"created": now, "etag": _etag(), "blobs": {}}
        print(f"[AZURE BLOB] Tạo container {key[0]}/{key[1]}")
        return _resp(201, {"ETag": _containers[key]["etag"], "Last-Modified": _http_date(now)})
    if method == "DELETE":
        if c is None:
            return _error(404, "ContainerNotFound", "The specified container does not exist.")
        _containers.pop(key, None)
        return _resp(202)
    return _error(405, "UnsupportedHttpVerb", f"{method} không hỗ trợ cho container")


def _check_lease_for_write(blob: Optional[Dict[str, Any]], headers: Dict[str, str]):
    lease_id = _hdr(headers, "x-ms-lease-id")
    if blob is None:
        if lease_id:
            return _error(412, "LeaseNotPresentWithBlobOperation", "There is currently no lease on the blob.")
        return None
    state = _lease_state(blob)
    if state == "leased" or state == "breaking":
        if not lease_id:
            return _error(412, "LeaseIdMissing", "There is currently a lease on the blob and no lease ID was specified in the request.")
        if lease_id != blob["lease"]["id"]:
            return _error(412, "LeaseIdMismatchWithBlobOperation", "The lease ID specified did not match the lease ID for the blob.")
    elif lease_id:
        return _error(412, "LeaseNotPresentWithBlobOperation", "There is currently no lease on the blob.")
    return None


def _check_conditions(blob: Optional[Dict[str, Any]], headers: Dict[str, str]):
    inm = _hdr(headers, "If-None-Match")
    if inm == "*" and blob is not None:
        return _error(409, "BlobAlreadyExists", "The specified blob already exists.")
    if inm and inm != "*" and blob is not None and inm == blob["etag"]:
        return _error(412, "ConditionNotMet", "The condition specified using HTTP conditional header(s) is not met.")
    im = _hdr(headers, "If-Match")
    if im and im != "*" and (blob is None or im != blob["etag"]):
        return _error(412, "ConditionNotMet", "The condition specified using HTTP conditional header(s) is not met.")
    return None


def _blob_op(method: str, key, name: str, q, headers: Dict[str, str], body: bytes):
    c = _containers.get(key)
    if c is None:
        return _error(404, "ContainerNotFound", "The specified container does not exist.")
    blob = c["blobs"].get(name)

    if q.get("comp") == "lease" and method == "PUT":
        return _lease_op(blob, headers)

    if method == "PUT" and not q.get("comp"):
        err = _check_conditions(blob, headers) or _check_lease_for_write(blob, headers)
        if err:
            return err
        now = time.time()
        md5 = hashlib.md5(body).digest()
        import base64
        new = {"data": bytes(body), "etag": _etag(), "modified": now, "created": blob["created"] if blob else now,
               "md5": base64.b64encode(md5).decode(), "content_type": _hdr(headers, "x-ms-blob-content-type"),
               "metadata": {k[len("x-ms-meta-"):]: v for k, v in headers.items() if k.lower().startswith("x-ms-meta-")},
               "lease": blob["lease"] if blob else {"state": "available", "id": None, "expires": None, "break_at": 0}}
        c["blobs"][name] = new
        return _resp(201, {"ETag": new["etag"], "Last-Modified": _http_date(now), "Content-MD5": new["md5"],
                           "x-ms-request-server-encrypted": "true"})

    if method in ("GET", "HEAD") and not q.get("comp"):
        if blob is None:
            return _error(404, "BlobNotFound", "The specified blob does not exist.")
        h = _blob_headers(blob)
        return _resp(200, h, blob["data"])

    if method == "DELETE":
        if blob is None:
            return _error(404, "BlobNotFound", "The specified blob does not exist.")
        err = _check_lease_for_write(blob, headers)
        if err:
            return err
        c["blobs"].pop(name, None)
        return _resp(202)

    return _error(400, "UnsupportedQueryParameter", f"{method} comp={q.get('comp')} không hỗ trợ")


def _lease_op(blob: Optional[Dict[str, Any]], headers: Dict[str, str]):
    if blob is None:
        return _error(404, "BlobNotFound", "The specified blob does not exist.")
    action = (_hdr(headers, "x-ms-lease-action") or "").lower()
    lease = blob["lease"]
    state = _lease_state(blob)
    lease_id = _hdr(headers, "x-ms-lease-id")
    now = time.time()

    def duration_expiry():
        d = int(_hdr(headers, "x-ms-lease-duration") or -1)
        if d != -1 and not 15 <= d <= 60:
            return "bad"
        return None if d == -1 else now + d

    if action == "acquire":
        proposed = _hdr(headers, "x-ms-proposed-lease-id") or str(uuid.uuid4())
        if state in ("leased", "breaking") and lease["id"] != proposed:
            return _error(409, "LeaseAlreadyPresent", "There is already a lease present.")
        exp = duration_expiry()
        if exp == "bad":
            return _error(400, "InvalidHeaderValue", "x-ms-lease-duration phải là -1 hoặc 15..60")
        lease.update(state="leased", id=proposed, expires=exp)
        lease["duration"] = _hdr(headers, "x-ms-lease-duration")
        return _resp(201, {"x-ms-lease-id": proposed, "ETag": blob["etag"], "Last-Modified": _http_date(blob["modified"])})
    if action == "renew":
        if lease["id"] != lease_id or state not in ("leased", "expired"):
            return _error(409, "LeaseIdMismatchWithLeaseOperation", "The lease ID specified did not match the lease ID for the blob.")
        dur = lease.get("duration")
        lease.update(state="leased", expires=None if dur in (None, "-1") else now + int(dur))
        return _resp(200, {"x-ms-lease-id": lease_id, "ETag": blob["etag"], "Last-Modified": _http_date(blob["modified"])})
    if action == "change":
        proposed = _hdr(headers, "x-ms-proposed-lease-id")
        if state != "leased":
            return _error(409, "LeaseNotPresentWithLeaseOperation", "There is currently no lease on the blob.")
        if lease_id not in (lease["id"], proposed):
            return _error(409, "LeaseIdMismatchWithLeaseOperation", "The lease ID specified did not match the lease ID for the blob.")
        lease["id"] = proposed
        return _resp(200, {"x-ms-lease-id": proposed, "ETag": blob["etag"], "Last-Modified": _http_date(blob["modified"])})
    if action == "release":
        if lease["id"] != lease_id:
            return _error(409, "LeaseIdMismatchWithLeaseOperation", "The lease ID specified did not match the lease ID for the blob.")
        lease.update(state="available", id=None, expires=None)
        return _resp(200, {"ETag": blob["etag"], "Last-Modified": _http_date(blob["modified"])})
    if action == "break":
        if state not in ("leased", "breaking"):
            return _error(409, "LeaseNotPresentWithLeaseOperation", "There is currently no lease on the blob.")
        period = int(_hdr(headers, "x-ms-lease-break-period") or 0)
        lease.update(state="breaking" if period else "broken", break_at=now + period)
        return _resp(202, {"x-ms-lease-time": str(period), "ETag": blob["etag"]})
    return _error(400, "InvalidHeaderValue", f"x-ms-lease-action không hợp lệ: {action}")


def snapshot():
    with _lock:
        out = []
        for (account, container), c in _containers.items():
            out.append({"account": account, "container": container,
                        "blobs": {n: {"lease_state": _lease_state(b), "size": len(b["data"]),
                                      "content": b["data"][:300].decode("utf-8", "replace")}
                                  for n, b in c["blobs"].items()}})
        return out


def reset():
    with _lock:
        _containers.clear()
