import time
import threading
from typing import List, Dict, Any, Optional
from .config import MAX_REQUEST_LOGS

class RequestLogger:
    def __init__(self, max_entries: int = MAX_REQUEST_LOGS):
        self.max_entries = max_entries
        self._logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._next_id = 1

    def log(
        self,
        method: str,
        path: str,
        host: str,
        client_ip: str,
        params: Dict[str, Any],
        req_headers: Dict[str, str],
        req_body: str,
        status: int,
        resp_headers: Dict[str, str],
        resp_body: str,
        matched_rule: Optional[str] = None,
        duration_ms: float = 0.0
    ) -> Dict[str, Any]:
        with self._lock:
            entry_id = self._next_id
            self._next_id += 1

            # Cắt ngắn body nếu quá dài để tránh chiếm bộ nhớ
            max_body_preview = 4096
            req_body_preview = (req_body[:max_body_preview] + "... [TRUNCATED]") if len(req_body) > max_body_preview else req_body
            resp_body_preview = (resp_body[:max_body_preview] + "... [TRUNCATED]") if len(resp_body) > max_body_preview else resp_body

            entry = {
                "id": entry_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "time_ms": int(time.time() * 1000),
                "client_ip": client_ip,
                "method": method.upper(),
                "path": path,
                "host": host,
                "params": params,
                "request_headers": req_headers,
                "request_body": req_body_preview,
                "status": status,
                "response_headers": resp_headers,
                "response_body": resp_body_preview,
                "matched_rule": matched_rule or "default_service",
                "duration_ms": round(duration_ms, 2)
            }

            self._logs.insert(0, entry)
            if len(self._logs) > self.max_entries:
                self._logs.pop()

            return entry

    def get_logs(self, limit: int = 100, search: Optional[str] = None, status_filter: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            results = self._logs
            if status_filter:
                results = [l for l in results if l.get("status") == status_filter]
            if search:
                s_lower = search.lower()
                results = [
                    l for l in results
                    if s_lower in l.get("path", "").lower()
                    or s_lower in l.get("host", "").lower()
                    or s_lower in l.get("matched_rule", "").lower()
                    or s_lower in l.get("method", "").lower()
                ]
            return results[:limit]

    def clear(self):
        with self._lock:
            self._logs.clear()


# Global request logger instance
request_logger = RequestLogger()
