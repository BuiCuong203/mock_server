import re
import time
import uuid
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

_COUNTER = 0

def get_next_counter() -> int:
    global _COUNTER
    _COUNTER += 1
    return _COUNTER


class TemplateEngine:
    """
    Hỗ trợ thay thế các placeholder động trong response body (JSON, XML, Plain text):
    - {{NOW_ISO}} -> 2026-09-30T10:15:00Z
    - {{NOW_UTC}} -> Wed, 30 Sep 2026 10:15:00 GMT
    - {{NOW_CLF}} -> 30/Sep/2026:10:15:00 +0000 (access log nginx / apache)
    - {{TIMESTAMP}} / {{NOW_TIMESTAMP}} -> 1790604900
    - {{TIMESTAMP_MS}} / {{NOW_MS}} -> 1790604900123
    - {{PAST_ISO:60}} -> 60 giây trước định dạng ISO
    - {{PAST_MS:60}} -> 60 giây trước định dạng millisecond
    - {{FUTURE_ISO:3600}} -> 1 giờ sau
    - {{UUID}} -> 12345678-1234-5678-1234-567812345678
    - {{COUNTER}} -> số tăng dần 1, 2, 3...
    - {{RANDOM_INT:10:99}} -> số nguyên ngẫu nhiên
    - {{CHOICE:a|b|c}} -> chọn ngẫu nhiên 1 giá trị trong danh sách
    - {{REQ_PARAM:key}} -> giá trị query param từ request
    - {{REQ_HEADER:key}} -> giá trị header từ request
    - {{MD5:...}} -> mã hóa MD5
    """

    @classmethod
    def render_string(cls, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        if not text or not isinstance(text, str):
            return text

        ctx = context or {}
        req_params = ctx.get("params", {})
        req_headers = ctx.get("headers", {})

        now = datetime.now(timezone.utc)
        now_ts = int(time.time())
        now_ms = int(time.time() * 1000)

        # Basic replacements
        text = text.replace("{{NOW_ISO}}", now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        text = text.replace("{{NOW_UTC}}", now.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        # Định dạng thời gian của access log nginx / apache (Common Log Format): 17/Oct/2026:09:45:21 +0000
        text = text.replace("{{NOW_CLF}}", now.strftime("%d/%b/%Y:%H:%M:%S +0000"))
        text = text.replace("{{NOW_TIMESTAMP}}", str(now_ts))
        text = text.replace("{{TIMESTAMP}}", str(now_ts))
        text = text.replace("{{NOW_MS}}", str(now_ms))
        text = text.replace("{{TIMESTAMP_MS}}", str(now_ms))
        text = text.replace("{{UUID}}", str(uuid.uuid4()))

        # {{COUNTER}}
        while "{{COUNTER}}" in text:
            text = text.replace("{{COUNTER}}", str(get_next_counter()), 1)

        # {{PAST_ISO:sec}}
        for m in re.finditer(r"\{\{PAST_ISO:(\d+)\}\}", text):
            sec = int(m.group(1))
            past = now - timedelta(seconds=sec)
            text = text.replace(m.group(0), past.strftime("%Y-%m-%dT%H:%M:%SZ"))

        # {{FUTURE_ISO:sec}}
        for m in re.finditer(r"\{\{FUTURE_ISO:(\d+)\}\}", text):
            sec = int(m.group(1))
            fut = now + timedelta(seconds=sec)
            text = text.replace(m.group(0), fut.strftime("%Y-%m-%dT%H:%M:%SZ"))

        # {{PAST_MS:sec}}
        for m in re.finditer(r"\{\{PAST_MS:(\d+)\}\}", text):
            sec = int(m.group(1))
            past_ms = now_ms - (sec * 1000)
            text = text.replace(m.group(0), str(past_ms))

        # {{RANDOM_INT:min:max}}
        for m in re.finditer(r"\{\{RANDOM_INT:(\d+):(\d+)\}\}", text):
            low, high = int(m.group(1)), int(m.group(2))
            val = random.randint(low, high)
            text = text.replace(m.group(0), str(val), 1)

        # {{CHOICE:a|b|c}} -> chọn ngẫu nhiên 1 giá trị
        for m in re.finditer(r"\{\{CHOICE:([^{}]*)\}\}", text):
            text = text.replace(m.group(0), random.choice(m.group(1).split("|")), 1)

        # {{REQ_PARAM:name}}
        for m in re.finditer(r"\{\{REQ_PARAM:([\w\-\_]+)\}\}", text):
            param_key = m.group(1)
            param_val = req_params.get(param_key, [""])[0] if isinstance(req_params.get(param_key), list) else req_params.get(param_key, "")
            text = text.replace(m.group(0), str(param_val))

        # {{REQ_HEADER:name}}
        for m in re.finditer(r"\{\{REQ_HEADER:([\w\-\_]+)\}\}", text):
            hdr_key = m.group(1)
            # Case insensitive header lookup
            hdr_val = ""
            for k, v in req_headers.items():
                if k.lower() == hdr_key.lower():
                    hdr_val = v
                    break
            text = text.replace(m.group(0), str(hdr_val))

        # {{MD5:...}}
        for m in re.finditer(r"\{\{MD5:(.*?)\}\}", text):
            content_to_hash = m.group(1)
            hashed = hashlib.md5(content_to_hash.encode("utf-8")).hexdigest()
            text = text.replace(m.group(0), hashed)

        # Tự động tính toán MD5OfBody chuẩn xác cho AWS SQS ReceiveMessage
        if "<Body>" in text and "<MD5OfBody>" in text:
            m_body = re.search(r"<Body>(.*?)</Body>", text, re.DOTALL)
            if m_body:
                body_content = m_body.group(1)
                real_md5 = hashlib.md5(body_content.encode("utf-8")).hexdigest()
                text = re.sub(r"<MD5OfBody>.*?</MD5OfBody>", f"<MD5OfBody>{real_md5}</MD5OfBody>", text)

        return text

    @classmethod
    def render(cls, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Đệ quy render template cho string, dict, list"""
        if isinstance(data, str):
            rendered_str = cls.render_string(data, context)
            # Nếu nguyên chuỗi gốc là placeholder số nguyên thì trả về kiểu int thay vì string
            clean_token = data.strip()
            if clean_token.startswith("{{") and clean_token.endswith("}}") and (
                "MS" in clean_token or "TIMESTAMP" in clean_token or "RANDOM_INT" in clean_token or "COUNTER" in clean_token
            ):
                if rendered_str.isdigit():
                    return int(rendered_str)
            return rendered_str
        elif isinstance(data, list):
            return [cls.render(item, context) for item in data]
        elif isinstance(data, dict):
            return {cls.render(k, context): cls.render(v, context) for k, v in data.items()}
        return data
