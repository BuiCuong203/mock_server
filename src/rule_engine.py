import os
import re
import fnmatch
import json
import time
from typing import Dict, Any, Optional, Tuple, List
from .config import FIXTURES_DIR
from .template_engine import TemplateEngine


class MockRule:
    """
    Quy tắc Mock động xử lý cả Direct API và HTTPS Proxy:
    - Match: method, host, path, path_match (prefix/exact/contains/regex/glob), headers, params, body_contains, body_regex
    - Response: status, headers, body, body_type (json/xml/text/fixture), delay_ms, interval_sec, interval_response, sequence
    """
    def __init__(self, data: Dict[str, Any], source_file: Optional[str] = None):
        self.id = data.get("id", f"rule_{int(time.time()*1000)}")
        self.name = data.get("name", "Unnamed Rule")
        self.category = data.get("category", "generic") # rest_api, azure, defender, m365, cloudwatch, aws_s3sqs, custom
        self.enabled = data.get("enabled", True)
        self.mode = data.get("mode", "all") # direct, proxy, all
        self.match = data.get("match", {})
        self.response = data.get("response", {})
        self.source_file = source_file

        # Runtime state
        self.last_triggered_time = 0.0
        self.hit_count = 0
        self.sequence_index = 0

    def matches(self, method: str, path: str, host: str, headers: Dict[str, str], body: str, is_proxy: bool = False) -> bool:
        if not self.enabled:
            return False

        # 0. Match Mode (direct vs proxy)
        if self.mode == "proxy" and not is_proxy:
            # Nếu rule chỉ định proxy nhưng request gọi thẳng localhost (không qua proxy host bên ngoài)
            # Ngoại trừ trường hợp host khớp tường minh
            rule_host = self.match.get("host", "")
            if not rule_host or "localhost" in host:
                return False
        elif self.mode == "direct" and is_proxy:
            return False

        # 1. Match Method
        rule_method = self.match.get("method", "*").upper()
        if rule_method != "*" and rule_method != method.upper():
            return False

        # 2. Match Host (Hỗ trợ wildcard fnmatch: *.amazonaws.com, manage.office.com, ...)
        rule_host = self.match.get("host", "")
        if rule_host:
            # Tách port nếu host có port (vd: sqs.us-east-1.amazonaws.com:443)
            clean_host = host.split(":")[0].lower()
            clean_rule_host = rule_host.split(":")[0].lower()
            if not fnmatch.fnmatch(clean_host, clean_rule_host) and clean_rule_host not in clean_host:
                return False

        # 3. Match Path
        rule_path = self.match.get("path", "")
        path_match_type = self.match.get("path_match", "prefix")  # exact, prefix, contains, regex, glob

        if rule_path:
            if path_match_type == "exact" and path != rule_path:
                return False
            elif path_match_type == "prefix" and not path.startswith(rule_path):
                return False
            elif path_match_type == "contains" and rule_path not in path:
                return False
            elif path_match_type == "glob" and not fnmatch.fnmatch(path, rule_path):
                return False
            elif path_match_type == "regex":
                try:
                    if not re.search(rule_path, path):
                        return False
                except re.error:
                    return False

        # 4. Match Headers (tất cả header khai báo phải thỏa mãn)
        rule_headers = self.match.get("headers", {})
        for req_hdr_key, req_hdr_val in rule_headers.items():
            matched_hdr = False
            for h_key, h_val in headers.items():
                if h_key.lower() == req_hdr_key.lower():
                    if req_hdr_val == "*" or req_hdr_val.lower() in h_val.lower():
                        matched_hdr = True
                        break
                    try:
                        if re.search(req_hdr_val, h_val):
                            matched_hdr = True
                            break
                    except re.error:
                        pass
            if not matched_hdr:
                return False

        # 5. Match Body Contains / Regex
        body_contains = self.match.get("body_contains", "")
        if body_contains and body_contains not in body:
            return False

        body_regex = self.match.get("body_regex", "")
        if body_regex:
            try:
                if not re.search(body_regex, body):
                    return False
            except re.error:
                return False

        return True

    def build_response(
        self,
        method: str,
        path: str,
        host: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        body: str
    ) -> Tuple[int, Dict[str, str], bytes]:
        self.hit_count += 1
        now = time.time()

        # 1. Sequence Handling (nếu có chuỗi response luân phiên)
        sequence_list = self.response.get("sequence")
        if sequence_list and isinstance(sequence_list, list) and len(sequence_list) > 0:
            resp_conf = sequence_list[self.sequence_index % len(sequence_list)]
            self.sequence_index += 1
        else:
            resp_conf = self.response

        # 2. Interval Throttling / Long-Polling Simulation (vd: SQS 10s hoặc M365 Blobs 10s)
        interval_sec = resp_conf.get("interval_sec", self.response.get("interval_sec", 0.0))
        interval_response = resp_conf.get("interval_response", self.response.get("interval_response"))

        if interval_sec > 0:
            if (now - self.last_triggered_time) < interval_sec and interval_response:
                # Trả về interval response (ví dụ response rỗng)
                return self._render_response_spec(interval_response, method, path, host, params, headers, body)
            self.last_triggered_time = now

        # 3. Simulate Network Delay
        delay_ms = resp_conf.get("delay_ms", 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # 4. Simulate Network Failure: đóng kết nối, không trả response (status -1)
        if resp_conf.get("drop_connection"):
            return -1, {}, b""

        # 5. Stateful Response (Nếu có cấu hình)
        if "stateful" in resp_conf:
            from .stateful_engine import StatefulEngine
            return StatefulEngine.process(resp_conf["stateful"], method, path, host, params, headers, body)

        return self._render_response_spec(resp_conf, method, path, host, params, headers, body)

    def _render_response_spec(
        self,
        resp_conf: Dict[str, Any],
        method: str,
        path: str,
        host: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        body: str
    ) -> Tuple[int, Dict[str, str], bytes]:
        status = int(resp_conf.get("status", 200))
        resp_headers = dict(resp_conf.get("headers", {}))
        body_type = resp_conf.get("body_type", "json").lower()

        context = {
            "method": method,
            "path": path,
            "host": host,
            "params": params,
            "headers": headers,
            "body": body
        }

        # Nếu response chỉ định fixture file
        raw_body_data = resp_conf.get("body")
        fixture_path = resp_conf.get("fixture")
        if fixture_path:
            full_fix_path = os.path.join(FIXTURES_DIR, fixture_path)
            if os.path.exists(full_fix_path):
                with open(full_fix_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if fixture_path.endswith(".json"):
                        try:
                            raw_body_data = json.loads(content)
                        except json.JSONDecodeError:
                            raw_body_data = content
                    else:
                        raw_body_data = content

        # Render qua Template Engine
        rendered = TemplateEngine.render(raw_body_data, context)

        if body_type == "json" or isinstance(rendered, (dict, list)):
            if "Content-Type" not in resp_headers:
                resp_headers["Content-Type"] = "application/json"
            if isinstance(rendered, str):
                body_bytes = rendered.encode("utf-8")
            else:
                body_bytes = json.dumps(rendered, indent=2).encode("utf-8")
        elif body_type == "xml":
            if "Content-Type" not in resp_headers:
                resp_headers["Content-Type"] = "application/xml"
            body_str = str(rendered) if rendered is not None else ""
            body_bytes = body_str.encode("utf-8")
        else: # plain text
            if "Content-Type" not in resp_headers:
                resp_headers["Content-Type"] = "text/plain; charset=utf-8"
            body_str = str(rendered) if rendered is not None else ""
            body_bytes = body_str.encode("utf-8")

        resp_headers["Content-Length"] = str(len(body_bytes))
        return status, resp_headers, body_bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "enabled": self.enabled,
            "mode": self.mode,
            "match": self.match,
            "response": self.response,
            "source_file": self.source_file,
            "hit_count": self.hit_count
        }
