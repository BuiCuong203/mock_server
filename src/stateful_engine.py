import os
import json
import re
import time
import uuid
import hashlib
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, List, Optional
from urllib.parse import parse_qs, quote, urlencode
from xml.sax.saxutils import escape as xml_escape


def _parse_ts(value):
    """Parse thời gian ISO 8601 / RFC3339 (có 'Z' hoặc offset +07:00, hoặc không múi giờ = UTC) thành datetime UTC-aware."""
    try:
        s = str(value).strip().replace(" ", "T")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _first(params: Dict[str, Any], key: str, default=None):
    if key not in params:
        return default
    v = params[key]
    return v[0] if isinstance(v, list) else v


def _scheme(host: str, conf: Dict[str, Any]) -> str:
    """Scheme cho link trang sau: cấu hình next_link_scheme, nếu không thì đoán theo Host.
    Gọi thẳng mock (localhost:8881) -> http; đi qua HTTPS proxy (graph.microsoft.com, không port) -> https."""
    if conf.get("next_link_scheme"):
        return conf["next_link_scheme"]
    if ":" in host and not host.endswith(":443"):
        return "http"
    return "https"


def _json_response(status: int, data: Any, content_type: str = "application/json") -> Tuple[int, Dict[str, str], bytes]:
    body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return status, {"Content-Type": content_type, "Content-Length": str(len(body_bytes))}, body_bytes


ODATA_TIME_FIELDS = ["createdDateTime", "activityDateTime", "alertCreationTime", "createdTime",
                     "creationTime", "lastUpdateTime", "eventTimestamp", "CreationTime"]
ODATA_COND_RE = re.compile(r"(\w+)\s+(gt|ge|lt|le|eq)\s+'?([0-9]{4}-[0-9]{2}-[0-9]{2}[0-9T:\.\-+Z]*)'?", re.IGNORECASE)


class StatefulEngine:
    _cache = {}
    _cache_mtime = {}
    _time_cache = {}
    _sqs_cursor = {}
    _sqs_lock = threading.Lock()

    @classmethod
    def load_dataset(cls, file_path: str):
        # Nạp file nếu chưa có trong RAM hoặc file đã bị sửa đổi
        current_mtime = os.path.getmtime(file_path)
        if file_path not in cls._cache or cls._cache_mtime.get(file_path) != current_mtime:
            with open(file_path, "r", encoding="utf-8") as f:
                cls._cache[file_path] = json.load(f)
                cls._cache_mtime[file_path] = current_mtime
                print(f"[StatefulEngine] Reloaded {file_path} with {len(cls._cache[file_path])} records")
        return cls._cache[file_path]

    @classmethod
    def record_epochs(cls, file_path: str, records: List[Dict[str, Any]], field: str) -> List[Optional[float]]:
        """Thời gian (epoch giây) của từng bản ghi theo field, được cache theo file + field + mtime."""
        key = (file_path, field, cls._cache_mtime.get(file_path))
        if key not in cls._time_cache:
            out = []
            for r in records:
                v = r.get(field)
                if isinstance(v, (int, float)):
                    out.append(v / 1000.0 if v > 1e11 else float(v))
                else:
                    dt = _parse_ts(v) if v else None
                    out.append(dt.timestamp() if dt else None)
            cls._time_cache[key] = out
        return cls._time_cache[key]

    @classmethod
    def process(cls, stateful_conf: Dict[str, Any], method: str, path: str, host: str, params: Dict[str, Any], headers: Dict[str, str], body: str) -> Tuple[int, Dict[str, str], bytes]:
        stateful_type = stateful_conf.get("type", "odata")
        # Alibaba SLS: luồng log tự sinh theo thời gian (consumer group, cursor, checkpoint) - xem src/sls_mock.py
        if stateful_type == "sls":
            from .sls_mock import process as sls_process
            return sls_process(stateful_conf, method, path, host, params, headers, body)
        # SQS không cần dataset; S3 synthetic tự sinh bản ghi theo phút -> không phụ thuộc file, không bao giờ hết data
        if stateful_type == "sqs_receive":
            return cls._sqs_receive(stateful_conf, body)
        if stateful_type == "s3_object" and stateful_conf.get("synthetic"):
            return cls._s3_object(stateful_conf, None, None, path, host)

        dataset_name = stateful_conf.get("dataset_file")
        if not dataset_name:
            return 500, {"Content-Type": "application/json"}, b'{"error": "Missing dataset_file in rule"}'

        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", dataset_name))
        if not os.path.exists(file_path):
            return 404, {"Content-Type": "application/json"}, b'{"error": "Dataset file not found"}'

        try:
            records = cls.load_dataset(file_path)
        except Exception as e:
            return 500, {"Content-Type": "application/json"}, f'{{"error": "Failed to parse JSON dataset: {str(e)}" }}'.encode("utf-8")

        # Determine pagination type
        stateful_type = stateful_conf.get("type", "odata")

        if stateful_type == "m365_content":
            return cls._m365_content(stateful_conf, file_path, records, path, host, params)
        if stateful_type == "m365_blob":
            return cls._m365_blob(stateful_conf, file_path, records, path)
        if stateful_type == "sqs_receive":
            return cls._sqs_receive(stateful_conf, body)
        if stateful_type == "s3_object":
            return cls._s3_object(stateful_conf, file_path, records, path, host)

        # Lọc thời gian cho REST API nếu có query param (since, from, start_time, created_after...)
        since_val = None
        for time_key in ["since", "from", "start_time", "created_after", "startTime"]:
            if time_key in params:
                since_val = params[time_key][0] if isinstance(params[time_key], list) else params[time_key]
                break

        # Tùy chọn chung:
        #   time_field : tên field thời gian của bản ghi
        #   realtime   : true -> ẩn bản ghi có thời gian > hiện tại (giả lập log phát sinh dần theo thời gian thực)
        #   events_key : tên field chứa mảng log trong response REST (mặc định "events")
        time_field = stateful_conf.get("time_field")
        realtime = bool(stateful_conf.get("realtime"))
        events_key = stateful_conf.get("events_key", "events")

        def record_time(r):
            if time_field:
                return r.get(time_field)
            return r.get("timestamp") or r.get("created_at") or r.get("time")

        if (since_val or realtime) and stateful_type in ("cursor", "limit_offset", "page_size", "next_link"):
            clean_since = str(since_val).strip().replace(" ", "T") if since_val else ""
            since_dt = _parse_ts(since_val) if since_val else None
            now_dt = datetime.now(timezone.utc) if realtime else None
            filtered_records = []
            for r in records:
                raw_ts = record_time(r)
                if not raw_ts:
                    filtered_records.append(r)
                    continue
                r_dt = _parse_ts(raw_ts)
                if r_dt is None:
                    # Không parse được: giữ cách so sánh chuỗi như trước
                    if not clean_since or str(raw_ts) >= clean_since:
                        filtered_records.append(r)
                    continue
                if since_val and since_dt is None and str(raw_ts) < clean_since:
                    continue
                if since_dt and r_dt < since_dt:
                    continue
                if now_dt and r_dt > now_dt:
                    continue
                filtered_records.append(r)
            records = filtered_records

        if stateful_type == "cursor":
            # Xử lý Generic REST API (Cursor-based)
            page_size = int(stateful_conf.get("page_size", 50))
            cursor_val = 0
            if "cursor" in params:
                try:
                    cursor_val = int(params["cursor"][0] if isinstance(params["cursor"], list) else params["cursor"])
                except ValueError:
                    cursor_val = 0

            # Phân trang
            paginated_records = records[cursor_val : cursor_val + page_size]
            response_data = {
                "status": "success",
                events_key: paginated_records
            }

            # Cấp next_cursor nếu còn
            if cursor_val + page_size < len(records):
                response_data["next_cursor"] = str(cursor_val + page_size)
            else:
                response_data["next_cursor"] = None

        elif stateful_type == "limit_offset":
            limit_val = int(stateful_conf.get("limit", 50))
            if "limit" in params:
                try:
                    limit_val = int(params["limit"][0] if isinstance(params["limit"], list) else params["limit"])
                except ValueError:
                    pass

            offset_val = 0
            if "offset" in params:
                try:
                    offset_val = int(params["offset"][0] if isinstance(params["offset"], list) else params["offset"])
                except ValueError:
                    pass

            paginated_records = records[offset_val : offset_val + limit_val]
            response_data = {
                "status": "success",
                "total": len(records),
                events_key: paginated_records
            }

        elif stateful_type == "page_size":
            size_val = int(stateful_conf.get("size", 50))
            if "size" in params:
                try:
                    size_val = int(params["size"][0] if isinstance(params["size"], list) else params["size"])
                except ValueError:
                    pass

            page_val = 1
            if "page" in params:
                try:
                    page_val = int(params["page"][0] if isinstance(params["page"], list) else params["page"])
                except ValueError:
                    pass

            start_idx = (page_val - 1) * size_val
            if start_idx < 0: start_idx = 0

            paginated_records = records[start_idx : start_idx + size_val]
            response_data = {
                "status": "success",
                "page": page_val,
                "total_pages": (len(records) + size_val - 1) // size_val,
                events_key: paginated_records
            }

        elif stateful_type == "next_link":
            page_size = int(stateful_conf.get("page_size", 50))
            start_idx = 0
            if "start" in params:
                try:
                    start_idx = int(params["start"][0] if isinstance(params["start"], list) else params["start"])
                except ValueError:
                    pass

            paginated_records = records[start_idx : start_idx + page_size]
            response_data = {
                "status": "success",
                events_key: paginated_records
            }

            # next_key: tên field chứa URL trang sau (mặc định "next_link")
            # last_page_value: giá trị của next_key ở trang cuối (mặc định null)
            next_key = stateful_conf.get("next_key", "next_link")
            if start_idx + page_size < len(records):
                base_path = path.split("?")[0]
                new_start = start_idx + page_size
                # Giữ nguyên các query param của request (vd since) để trang sau lọc cùng điều kiện
                query = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
                query["start"] = str(new_start)
                next_url = f"{_scheme(host, stateful_conf)}://{host}{base_path}?{urlencode(query)}"
                response_data[next_key] = next_url
            else:
                response_data[next_key] = stateful_conf.get("last_page_value")

        elif stateful_type == "cloudwatch":
            # Xử lý AWS CloudWatch FilterLogEvents / GetLogEvents
            req_body = {}
            if body:
                try:
                    req_body = json.loads(body)
                except Exception:
                    pass

            start_time_ms = req_body.get("startTime")
            end_time_ms = req_body.get("endTime")
            limit_val = int(req_body.get("limit", stateful_conf.get("limit", 100)))

            # nextToken sẽ đóng vai trò như index
            next_token = req_body.get("nextToken")
            start_idx = 0
            if next_token:
                try:
                    start_idx = int(next_token)
                except ValueError:
                    pass

            # Lọc theo thời gian [startTime, endTime] (ms, cả hai đầu)
            now_ms = time.time() * 1000 if realtime else None
            filtered_records = []
            for r in records:
                r_ts = r.get("timestamp")
                if not r_ts:
                    continue
                if start_time_ms and r_ts < start_time_ms:
                    continue
                if end_time_ms and r_ts > end_time_ms:
                    continue
                if now_ms and r_ts > now_ms:
                    continue
                filtered_records.append(r)

            # Phân trang
            paginated_records = filtered_records[start_idx : start_idx + limit_val]

            response_data = {
                "events": paginated_records
            }

            # Nếu còn dữ liệu, sinh nextToken
            if start_idx + limit_val < len(filtered_records):
                response_data["nextToken"] = str(start_idx + limit_val)

            # CloudWatch API yêu cầu Content-Type x-amz-json-1.1
            return _json_response(200, response_data, "application/x-amz-json-1.1")

        else:
            return cls._odata(stateful_conf, file_path, records, path, host, params)

        return _json_response(200, response_data)

    # ------------------------------------------------------------------
    # OData (Azure Graph signIns/directoryAudits, Defender alerts/incidents)
    # ------------------------------------------------------------------
    @classmethod
    def _odata(cls, conf, file_path, records, path, host, params):
        """Lọc theo $filter (gt/ge/lt/le trên field thời gian, so sánh theo thời gian thật, không theo chuỗi),
        phân trang $top/$skip, trả {"value": [...], "@odata.nextLink": ...}."""
        filter_str = _first(params, "$filter", "") or ""

        time_field = conf.get("time_field")
        if not time_field:
            sample = records[0] if records else {}
            time_field = next((f for f in ODATA_TIME_FIELDS if f in sample), "creationTime")
        epochs = cls.record_epochs(file_path, records, time_field)

        conds = []
        for field, op, value in ODATA_COND_RE.findall(filter_str):
            dt = _parse_ts(value)
            if dt is not None and (field == time_field or field in ODATA_TIME_FIELDS):
                conds.append((op.lower(), dt.timestamp()))

        now_s = time.time() if conf.get("realtime") else None
        selected = []
        for r, t in zip(records, epochs):
            if t is None:
                continue
            ok = True
            for op, v in conds:
                if (op == "gt" and not t > v) or (op == "ge" and not t >= v) or \
                   (op == "lt" and not t < v) or (op == "le" and not t <= v) or \
                   (op == "eq" and t != v):
                    ok = False
                    break
            if ok and now_s is not None and t > now_s:
                ok = False
            if ok:
                selected.append(r)

        try:
            top_val = int(_first(params, "$top", conf.get("page_size", 100)))
        except ValueError:
            top_val = 100
        try:
            skip_val = int(_first(params, "$skip", 0))
        except ValueError:
            skip_val = 0

        response_data = {"value": selected[skip_val: skip_val + top_val]}
        if skip_val + top_val < len(selected):
            query = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
            query["$top"] = str(top_val)
            query["$skip"] = str(skip_val + top_val)
            qs = urlencode(query, quote_via=quote, safe="$:'")
            response_data["@odata.nextLink"] = f"{_scheme(host, conf)}://{host}{path.split('?')[0]}?{qs}"
        return _json_response(200, response_data)

    # ------------------------------------------------------------------
    # Microsoft 365 Management Activity API (2 tầng)
    # ------------------------------------------------------------------
    @classmethod
    def _m365_filter(cls, conf, file_path, records, content_type, start_s, end_s):
        type_field = conf.get("content_type_field", "contentType")
        epochs = cls.record_epochs(file_path, records, conf.get("time_field", "CreationTime"))
        return [r for r, t in zip(records, epochs)
                if t is not None and start_s <= t < end_s and r.get(type_field) == content_type]

    @classmethod
    def _m365_content(cls, conf, file_path, records, path, host, params):
        """GET .../subscriptions/content?contentType=&startTime=&endTime= -> MẢNG content blob.
        Mỗi blob gom bản ghi của một khung blob_minutes phút; contentId mã hóa khung thời gian để tầng 2 tải đúng."""
        ct = _first(params, "contentType")
        st = _parse_ts(_first(params, "startTime")) if _first(params, "startTime") else None
        et = _parse_ts(_first(params, "endTime")) if _first(params, "endTime") else None
        if not ct or st is None or et is None:
            return _json_response(400, {"error": {"code": "AF20001", "message": "contentType, startTime and endTime are required"}})

        start_s, end_s = st.timestamp(), et.timestamp()
        if conf.get("realtime"):
            end_s = min(end_s, time.time())
        blob_s = int(conf.get("blob_minutes", 10)) * 60

        prefix = path.split("/activity/feed/")[0]
        base_uri = f"{_scheme(host, conf)}://{host}{prefix}/activity/feed/audit/"

        contents = []
        chunk = (int(start_s) // blob_s) * blob_s
        while chunk < end_s:
            w_start, w_end = max(chunk, start_s), min(chunk + blob_s, end_s)
            if w_start < w_end and cls._m365_filter(conf, file_path, records, ct, w_start, w_end):
                content_id = f"{ct}_{int(w_start)}_{int(w_end)}"
                created = datetime.fromtimestamp(w_end, tz=timezone.utc)
                contents.append({
                    "contentType": ct,
                    "contentId": content_id,
                    "contentUri": base_uri + content_id,
                    "contentCreated": created.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "contentExpiration": (created + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                })
            chunk += blob_s
        return _json_response(200, contents)

    @classmethod
    def _m365_blob(cls, conf, file_path, records, path):
        """GET .../activity/feed/audit/<contentType>_<start>_<end> -> MẢNG bản ghi audit trong khung đó."""
        content_id = path.rstrip("/").rsplit("/", 1)[-1]
        try:
            ct, s, e = content_id.rsplit("_", 2)
            start_s, end_s = int(s), int(e)
        except ValueError:
            return _json_response(404, {"error": {"code": "AF20051", "message": f"Content {content_id} not found"}})
        return _json_response(200, cls._m365_filter(conf, file_path, records, ct, start_s, end_s))

    # ------------------------------------------------------------------
    # AWS SQS ReceiveMessage + S3 GetObject
    # ------------------------------------------------------------------
    @classmethod
    def _object_key(cls, conf, window_start: int) -> str:
        dt = datetime.fromtimestamp(window_start, tz=timezone.utc)
        return f"{conf.get('key_prefix', 'AWSLogs/123456789012/CloudTrail/us-east-1/')}{dt:%Y/%m/%d/%H%M}.json"

    @classmethod
    def _sqs_receive(cls, conf, body):
        """Mỗi phút trôi qua sinh đúng 1 thông báo S3 ObjectCreated trỏ tới file log của phút đó (không trùng, không sót).
        Hàng đợi rỗng thì giữ request tới WaitTimeSeconds (long polling) như SQS thật."""
        form = parse_qs(body or "")
        try:
            wait_s = min(int(_first(form, "WaitTimeSeconds", 0)), 20)
        except ValueError:
            wait_s = 0
        try:
            max_n = max(1, min(int(_first(form, "MaxNumberOfMessages", 1)), 10))
        except ValueError:
            max_n = 1

        step = int(conf.get("object_minutes", 1)) * 60
        state_key = conf.get("dataset_file", "default")
        deadline = time.time() + wait_s
        windows = []
        while True:
            with cls._sqs_lock:
                now = time.time()
                ready_until = (int(now) // step) * step  # chỉ những phút đã kết thúc
                cursor = cls._sqs_cursor.get(state_key)
                if cursor is None:
                    cursor = ready_until - int(conf.get("backlog_minutes", 10)) * step
                n = min(max_n, max(0, (ready_until - cursor) // step))
                windows = [cursor + i * step for i in range(n)]
                cls._sqs_cursor[state_key] = cursor + n * step
            if windows or time.time() >= deadline:
                break
            time.sleep(min(1.0, max(0.0, deadline - time.time())))

        bucket = conf.get("bucket", "mock-s3-bucket")
        region = conf.get("region", "us-east-1")
        msgs = []
        for w in windows:
            key = cls._object_key(conf, w)
            event_time = datetime.fromtimestamp(w + step, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            msg_body = json.dumps({"Records": [{
                "eventVersion": "2.1", "eventSource": "aws:s3", "awsRegion": region,
                "eventTime": event_time, "eventName": "ObjectCreated:Put",
                "s3": {"bucket": {"name": bucket, "arn": f"arn:aws:s3:::{bucket}"},
                       "object": {"key": key, "size": 1024}}}]}, separators=(",", ":"))
            md5 = hashlib.md5(msg_body.encode("utf-8")).hexdigest()
            msgs.append(
                "    <Message>\n"
                f"      <MessageId>{uuid.uuid4()}</MessageId>\n"
                f"      <ReceiptHandle>{uuid.uuid4().hex}</ReceiptHandle>\n"
                f"      <MD5OfBody>{md5}</MD5OfBody>\n"
                f"      <Body>{xml_escape(msg_body)}</Body>\n"
                "      <Attribute><Name>ApproximateReceiveCount</Name><Value>1</Value></Attribute>\n"
                f"      <Attribute><Name>SentTimestamp</Name><Value>{(w + step) * 1000}</Value></Attribute>\n"
                "    </Message>\n")

        xml = ('<?xml version="1.0"?>\n<ReceiveMessageResponse xmlns="http://queue.amazonaws.com/doc/2012-11-05/">\n'
               f"  <ReceiveMessageResult>\n{''.join(msgs)}  </ReceiveMessageResult>\n"
               f"  <ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>\n"
               "</ReceiveMessageResponse>")
        body_bytes = xml.encode("utf-8")
        return 200, {"Content-Type": "text/xml", "Content-Length": str(len(body_bytes))}, body_bytes

    @classmethod
    def _s3_object(cls, conf, file_path, records, path, host):
        """GET object .../YYYY/MM/DD/HHMM.json -> file log CloudTrail {"Records": [...]} chứa bản ghi của đúng phút đó."""
        m = re.search(r"(\d{4})/(\d{2})/(\d{2})/(\d{2})(\d{2})\.json$", path)
        if not m:
            xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<Error><Code>NoSuchKey</Code>"
                   f"<Message>The specified key does not exist.</Message><Key>{xml_escape(path)}</Key></Error>")
            body_bytes = xml.encode("utf-8")
            return 404, {"Content-Type": "application/xml", "Content-Length": str(len(body_bytes))}, body_bytes

        y, mo, d, hh, mi = (int(x) for x in m.groups())
        start_s = datetime(y, mo, d, hh, mi, tzinfo=timezone.utc).timestamp()
        end_s = start_s + int(conf.get("object_minutes", 1)) * 60
        if conf.get("synthetic"):
            selected = cls._cloudtrail_synth(conf, int(start_s), int(end_s))
        else:
            epochs = cls.record_epochs(file_path, records, conf.get("time_field", "eventTime"))
            selected = [r for r, t in zip(records, epochs) if t is not None and start_s <= t < end_s]
        status, headers, body_bytes = _json_response(200, {"Records": selected})
        headers["ETag"] = f"\"{hashlib.md5(body_bytes).hexdigest()}\""
        return status, headers, body_bytes

    # ------------------------------------------------------------------
    # CloudTrail synthetic: sinh bản ghi theo cửa sổ thời gian, cố định theo seed = epoch đầu cửa sổ
    # (gọi lại cùng file -> cùng nội dung, cùng eventID như S3 thật)
    # ------------------------------------------------------------------
    _CT_USERS = ["sec_admin", "sales_manager", "sys_daemon", "dev_nguyen", "hr_tran", "finance_le", "guest_01",
                 "ops_pham", "audit_vo", "ci_runner"]
    _CT_EVENTS = [  # (eventSource, eventName, readOnly, trọng số)
        ("signin.amazonaws.com", "ConsoleLogin", False, 6), ("s3.amazonaws.com", "GetObject", True, 20),
        ("s3.amazonaws.com", "PutObject", False, 10), ("s3.amazonaws.com", "DeleteObject", False, 3),
        ("s3.amazonaws.com", "ListBuckets", True, 5), ("ec2.amazonaws.com", "DescribeInstances", True, 15),
        ("ec2.amazonaws.com", "RunInstances", False, 3), ("ec2.amazonaws.com", "TerminateInstances", False, 2),
        ("ec2.amazonaws.com", "AuthorizeSecurityGroupIngress", False, 2), ("iam.amazonaws.com", "CreateUser", False, 1),
        ("iam.amazonaws.com", "AttachUserPolicy", False, 1), ("iam.amazonaws.com", "CreateAccessKey", False, 1),
        ("sts.amazonaws.com", "AssumeRole", False, 10), ("kms.amazonaws.com", "Decrypt", True, 8),
        ("lambda.amazonaws.com", "Invoke", False, 6), ("cloudtrail.amazonaws.com", "StopLogging", False, 1),
        ("rds.amazonaws.com", "DescribeDBInstances", True, 4)]
    _CT_AGENTS = ["aws-cli/2.15.0 Python/3.11.6", "console.amazonaws.com", "Boto3/1.34.10 Python/3.10.12",
                  "aws-sdk-go-v2/1.24.0", "terraform/1.7.4"]

    @classmethod
    def _cloudtrail_synth(cls, conf, start_s: int, end_s: int) -> List[Dict[str, Any]]:
        import random
        n = max(1, int(conf.get("records_per_object", 50)))
        account = str(conf.get("account_id", "123456789012"))
        region = conf.get("region", "us-east-1")
        error_rate = float(conf.get("error_rate", 0.08))
        rnd = random.Random(start_s)
        weights = [e[3] for e in cls._CT_EVENTS]
        span = max(1, end_s - start_s)
        out = []
        for i in range(n):
            t = datetime.fromtimestamp(start_s + span * i / n, tz=timezone.utc)
            source, name, read_only, _ = rnd.choices(cls._CT_EVENTS, weights=weights)[0]
            user = rnd.choice(cls._CT_USERS)
            role = name == "AssumeRole" or rnd.random() < 0.2
            ip = f"{rnd.choice([10, 172, 118, 14, 203])}.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}"
            rec = {
                "eventVersion": "1.08",
                "userIdentity": ({"type": "AssumedRole",
                                  "principalId": f"AROA{rnd.getrandbits(48):012X}:{user}",
                                  "arn": f"arn:aws:sts::{account}:assumed-role/mock-log-reader/{user}",
                                  "accountId": account, "accessKeyId": f"ASIA{rnd.getrandbits(64):016X}"}
                                 if role else
                                 {"type": "IAMUser", "principalId": f"AIDA{rnd.getrandbits(64):016X}",
                                  "arn": f"arn:aws:iam::{account}:user/{user}", "accountId": account,
                                  "accessKeyId": f"AKIA{rnd.getrandbits(64):016X}", "userName": user}),
                "eventTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "eventSource": source, "eventName": name, "awsRegion": region,
                "sourceIPAddress": ip, "userAgent": rnd.choice(cls._CT_AGENTS),
                "requestParameters": None, "responseElements": None,
                "requestID": str(uuid.UUID(int=rnd.getrandbits(128), version=4)),
                "eventID": str(uuid.UUID(int=rnd.getrandbits(128), version=4)),
                "readOnly": read_only, "eventType": "AwsConsoleSignIn" if name == "ConsoleLogin" else "AwsApiCall",
                "managementEvent": source != "s3.amazonaws.com" or name == "ListBuckets",
                "recipientAccountId": account, "eventCategory": "Management",
            }
            if source == "s3.amazonaws.com" and name != "ListBuckets":
                rec["requestParameters"] = {"bucketName": rnd.choice(["prod-data", "finance-reports", "backup-logs"]),
                                            "key": f"{rnd.choice(['2026', 'archive', 'tmp'])}/file_{rnd.randint(1, 9999)}.csv"}
                rec["eventCategory"] = "Data"
            elif name == "ConsoleLogin":
                ok = rnd.random() > 0.2
                rec["responseElements"] = {"ConsoleLogin": "Success" if ok else "Failure"}
                rec["additionalEventData"] = {"MFAUsed": rnd.choice(["Yes", "No"]), "LoginTo": "https://console.aws.amazon.com/"}
                if not ok:
                    rec["errorMessage"] = "Failed authentication"
            elif name in ("RunInstances", "TerminateInstances", "DescribeInstances"):
                rec["requestParameters"] = {"instancesSet": {"items": [{"instanceId": f"i-{rnd.getrandbits(64):017x}"[:19]}]}}
            elif name == "AssumeRole":
                rec["requestParameters"] = {"roleArn": f"arn:aws:iam::{account}:role/mock-log-reader",
                                            "roleSessionName": user}
            if name != "ConsoleLogin" and rnd.random() < error_rate:
                rec["errorCode"] = rnd.choice(["AccessDenied", "UnauthorizedOperation", "ThrottlingException"])
                rec["errorMessage"] = f"User: arn:aws:iam::{account}:user/{user} is not authorized to perform: " \
                                      f"{source.split('.')[0]}:{name}"
            out.append(rec)
        return out
