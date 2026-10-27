"""
Tiện ích chung cho các nguồn log dạng "luồng" (SLS Alibaba, Azure Event Hubs, GCP Pub/Sub, HTTP push):
sinh bản ghi từ template + biến riêng của từng bản ghi.

Biến riêng (ngoài placeholder của TemplateEngine như {{UUID}}, {{RANDOM_INT:1:9}}, {{CHOICE:a|b}}):
  {{SEQ}}             số thứ tự bản ghi trong luồng (0, 1, 2...) - ổn định, dùng để kiểm tra mất / trùng log
  {{EVENT_TIME_ISO}}  thời điểm phát sinh bản ghi (ISO 8601 UTC, có mili giây)
  {{EVENT_TIME}}      ... dạng epoch giây,   {{EVENT_TIME_MS}} ... dạng epoch mili giây
  {{PARTITION}}       shard / partition chứa bản ghi
"""
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import BASE_DIR
from .template_engine import TemplateEngine


def record_vars(seq: int, event_time: float, partition: Any = 0) -> Dict[str, str]:
    dt = datetime.fromtimestamp(event_time, timezone.utc)
    return {
        "SEQ": str(seq),
        "EVENT_TIME_ISO": dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z",
        "EVENT_TIME": str(int(event_time)),
        "EVENT_TIME_MS": str(int(event_time * 1000)),
        "PARTITION": str(partition),
    }


def _substitute(data: Any, variables: Dict[str, str]) -> Any:
    if isinstance(data, str):
        for k, v in variables.items():
            data = data.replace("{{" + k + "}}", v)
        return data
    if isinstance(data, list):
        return [_substitute(x, variables) for x in data]
    if isinstance(data, dict):
        return {_substitute(k, variables): _substitute(v, variables) for k, v in data.items()}
    return data


def render_record(template: Any, variables: Dict[str, str]) -> Any:
    """Thay biến riêng của bản ghi rồi render placeholder chung của TemplateEngine."""
    rendered = TemplateEngine.render(_substitute(template, variables))
    # Chuỗi thuần số sinh từ {{SEQ}} / {{EVENT_TIME*}} -> giữ dạng số cho JSON
    if isinstance(rendered, dict):
        for k, v in list(rendered.items()):
            if isinstance(template, dict) and isinstance(template.get(k), str):
                raw = template[k].strip()
                if raw in ("{{SEQ}}", "{{EVENT_TIME}}", "{{EVENT_TIME_MS}}") and isinstance(v, str) and v.isdigit():
                    rendered[k] = int(v)
    return rendered


def load_templates(conf: Dict[str, Any], default: List[Any]) -> List[Any]:
    """Template bản ghi: 'templates' (danh sách) / 'template' (1 bản ghi) / 'dataset_file' (JSON list trong datasets/)."""
    if conf.get("templates"):
        return list(conf["templates"])
    if conf.get("template"):
        return [conf["template"]]
    name = conf.get("dataset_file")
    if name:
        path = os.path.join(BASE_DIR, "datasets", name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except (OSError, ValueError) as e:
            print(f"[stream] Không đọc được dataset {path}: {e}")
    return list(default)


class RateStream:
    """
    Luồng bản ghi tăng đều theo thời gian: tại thời điểm t có floor((t - t0) * rate) bản ghi.
    backlog_seconds > 0: coi như luồng đã chạy từ trước lúc khởi động (cursor "begin" có sẵn dữ liệu cũ).
    Bản ghi thứ n luôn có cùng thời điểm phát sinh -> đọc lại từ checkpoint cho ra cùng SEQ / thời gian.
    """

    def __init__(self, rate: float, backlog_seconds: float = 0.0, max_records: Optional[int] = None,
                 start_time: Optional[float] = None):
        self.rate = max(float(rate), 0.0)
        self.t0 = (start_time if start_time is not None else time.time()) - max(float(backlog_seconds), 0.0)
        self.max_records = max_records
        self.extra = 0          # bản ghi bơm thêm thủ công (Admin API)

    def available(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        n = int(max(now - self.t0, 0.0) * self.rate) if self.rate > 0 else 0
        if self.max_records is not None:
            n = min(n, self.max_records)
        return n + self.extra

    def event_time(self, seq: int) -> float:
        if self.rate <= 0:
            return time.time()
        return min(self.t0 + seq / self.rate, time.time())

    def offset_at(self, ts: float) -> int:
        """Bản ghi đầu tiên phát sinh tại / sau thời điểm ts (dùng cho cursor theo thời gian)."""
        if self.rate <= 0:
            return self.available()
        return max(0, min(self.available(), int((ts - self.t0) * self.rate)))
