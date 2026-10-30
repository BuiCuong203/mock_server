import json
import time
from typing import Dict, Any, Tuple
from .scenario_manager import scenario_manager
from .request_logger import request_logger
from .mock_sender import mock_sender, SenderError, DEFAULT_MESSAGES, DEFAULT_FORM, DEFAULT_FORMS, LOG_LEVELS, FACILITIES, SEVERITIES

_SERVER_START_TIME = time.time()


class AdminApi:
    @classmethod
    def handle_request(
        cls,
        method: str,
        path: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        body_str: str
    ) -> Tuple[int, Dict[str, str], bytes]:
        m = method.upper()

        # Helper response
        def json_response(status_code: int, data: Any):
            b = json.dumps(data, indent=2).encode("utf-8")
            return status_code, {
                "Content-Type": "application/json",
                "Content-Length": str(len(b)),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }, b

        # OPTIONS preflight
        if m == "OPTIONS":
            return 204, {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Length": "0"
            }, b""

        # 1. GET /mock/admin/api/status
        if path == "/mock/admin/api/status" and m == "GET":
            uptime_sec = int(time.time() - _SERVER_START_TIME)
            scenarios = scenario_manager.get_available_scenarios()
            active_rules = scenario_manager.get_all_active_rules()
            logs = request_logger.get_logs(limit=1)
            return json_response(200, {
                "status": "online",
                "uptime_seconds": uptime_sec,
                "active_scenario": scenario_manager.active_scenario_name,
                "available_scenarios_count": len(scenarios),
                "active_rules_count": len(active_rules),
                "total_logged_requests": len(request_logger._logs)
            })

        # 2. GET /mock/admin/api/logs
        if path == "/mock/admin/api/logs" and m == "GET":
            limit = int(params.get("limit", ["100"])[0]) if isinstance(params.get("limit"), list) else int(params.get("limit", 100))
            search = params.get("search", [""])[0] if isinstance(params.get("search"), list) else params.get("search", "")
            status_val = params.get("status", [""])[0] if isinstance(params.get("status"), list) else params.get("status", "")
            status_int = int(status_val) if status_val and status_val.isdigit() else None
            logs = request_logger.get_logs(limit=limit, search=search, status_filter=status_int)
            return json_response(200, {
                "total": len(logs),
                "logs": logs
            })

        # 3. POST /mock/admin/api/logs/clear
        if path == "/mock/admin/api/logs/clear" and m == "POST":
            request_logger.clear()
            return json_response(200, {"success": True, "message": "Request logs cleared"})

        # 4. GET /mock/admin/api/scenarios
        if path == "/mock/admin/api/scenarios" and m == "GET":
            scenarios = scenario_manager.get_available_scenarios()
            return json_response(200, {
                "active_scenario": scenario_manager.active_scenario_name,
                "scenarios": scenarios
            })

        # 5. POST /mock/admin/api/scenarios/switch
        if path == "/mock/admin/api/scenarios/switch" and m == "POST":
            target_name = ""
            if body_str:
                try:
                    payload = json.loads(body_str)
                    target_name = payload.get("scenario") or payload.get("name", "")
                except json.JSONDecodeError:
                    pass
            if not target_name and "scenario" in params:
                target_name = params["scenario"][0] if isinstance(params["scenario"], list) else params["scenario"]

            if not target_name:
                return json_response(400, {"error": "Missing 'scenario' parameter in request body or query"})

            success = scenario_manager.set_active_scenario(target_name)
            if success:
                return json_response(200, {
                    "success": True,
                    "active_scenario": scenario_manager.active_scenario_name,
                    "message": f"Successfully switched to scenario '{target_name}'"
                })
            else:
                return json_response(404, {
                    "error": f"Scenario '{target_name}' not found. Reload scenarios or check available list."
                })

        # 6. POST /mock/admin/api/scenarios/reload hoặc /mock/admin/api/rules/reload
        if (path in ("/mock/admin/api/scenarios/reload", "/mock/admin/api/rules/reload")) and m == "POST":
            scenario_manager.load_all()
            return json_response(200, {
                "success": True,
                "active_rules_count": len(scenario_manager.get_all_active_rules()),
                "available_scenarios": scenario_manager.get_available_scenarios(),
                "message": "Toàn bộ Rules và Scenarios đã được nạp lại từ ổ đĩa thành công"
            })

        # 7. GET /mock/admin/api/rules
        if path == "/mock/admin/api/rules" and m == "GET":
            rules = scenario_manager.get_all_active_rules()
            return json_response(200, {
                "total": len(rules),
                "rules": rules
            })

        # 8. POST /mock/admin/api/rules (Add dynamic rule)
        if path == "/mock/admin/api/rules" and m == "POST":
            try:
                rule_data = json.loads(body_str)
            except json.JSONDecodeError as e:
                return json_response(400, {"error": f"Invalid JSON payload: {e}"})

            if not isinstance(rule_data, dict):
                return json_response(400, {"error": "Rule must be a JSON object"})

            rule = scenario_manager.add_dynamic_rule(rule_data)
            return json_response(201, {
                "success": True,
                "rule": rule.to_dict(),
                "message": f"Dynamic rule '{rule.name}' added with highest priority"
            })

        # 8b. GET /mock/admin/api/rules/<id> (Lấy chi tiết 1 rule)
        if "/mock/admin/api/rules/" in path and m == "GET" and not path.endswith("/rules"):
            parts = path.split("/")
            rule_id = parts[parts.index("rules") + 1]
            all_rules = scenario_manager.get_all_active_rules()
            found = next((r for r in all_rules if r.get("id") == rule_id), None)
            if found:
                return json_response(200, {"success": True, "rule": found})
            return json_response(404, {"error": f"Rule '{rule_id}' not found"})

        # 8c. PUT hoặc POST /mock/admin/api/rules/<id> (Cập nhật và lưu lại rule)
        if "/mock/admin/api/rules/" in path and m in ("PUT", "POST") and not path.endswith("/toggle") and not path.endswith("/rules"):
            parts = path.split("/")
            rule_id = parts[parts.index("rules") + 1]
            try:
                rule_data = json.loads(body_str)
            except json.JSONDecodeError as e:
                return json_response(400, {"error": f"Invalid JSON payload: {e}"})

            if not isinstance(rule_data, dict):
                return json_response(400, {"error": "Rule must be a JSON object"})

            success, msg, rule_obj = scenario_manager.update_rule(rule_id, rule_data)
            return json_response(200 if success else 400, {
                "success": success,
                "message": msg,
                "rule": rule_obj.to_dict() if rule_obj else None
            })

        # 9. POST /mock/admin/api/rules/<id>/toggle
        if "/mock/admin/api/rules/" in path and path.endswith("/toggle") and m == "POST":
            parts = path.split("/")
            rule_id = parts[parts.index("rules") + 1]
            enabled = True
            if body_str:
                try:
                    payload = json.loads(body_str)
                    enabled = payload.get("enabled", True)
                except json.JSONDecodeError:
                    pass
            success = scenario_manager.toggle_rule(rule_id, enabled)
            return json_response(200, {"success": success, "rule_id": rule_id, "enabled": enabled})

        # 10. DELETE /mock/admin/api/rules/<id>
        if "/mock/admin/api/rules/" in path and m == "DELETE":
            parts = path.split("/")
            rule_id = parts[parts.index("rules") + 1]
            success = scenario_manager.remove_dynamic_rule(rule_id)
            return json_response(200, {"success": success, "rule_id": rule_id})

        # 11. MOCK SENDER (/mock/admin/api/sender/...) - bắn log tới collector
        if path.startswith("/mock/admin/api/sender"):
            def body_json():
                if not body_str:
                    return {}
                return json.loads(body_str)

            try:
                if path == "/mock/admin/api/sender/defaults" and m == "GET":
                    return json_response(200, {
                        "messages": DEFAULT_MESSAGES,
                        "form": DEFAULT_FORM,
                        "forms": DEFAULT_FORMS,
                        "levels": list(LOG_LEVELS.keys()),
                        "facilities": list(FACILITIES.keys()),
                        "severities": list(SEVERITIES.keys()),
                    })
                if path == "/mock/admin/api/sender/jobs" and m == "GET":
                    return json_response(200, {"jobs": mock_sender.list()})
                if path == "/mock/admin/api/sender/preview" and m == "POST":
                    return json_response(200, mock_sender.preview(body_json()))
                if path == "/mock/admin/api/sender/jobs" and m == "POST":
                    job = mock_sender.start(body_json())
                    return json_response(201, {"success": True, "job": job.to_dict()})
                if path == "/mock/admin/api/sender/stop_all" and m == "POST":
                    return json_response(200, {"success": True, "stopped": mock_sender.stop_all()})
                if path.startswith("/mock/admin/api/sender/jobs/"):
                    rest = path[len("/mock/admin/api/sender/jobs/"):].strip("/").split("/")
                    job_id = rest[0]
                    if len(rest) == 2 and rest[1] == "stop" and m == "POST":
                        ok = mock_sender.stop(job_id)
                        return json_response(200 if ok else 404, {"success": ok, "job_id": job_id})
                    if len(rest) == 1 and m == "DELETE":
                        ok = mock_sender.remove(job_id)
                        return json_response(200 if ok else 404, {"success": ok, "job_id": job_id})
            except json.JSONDecodeError as e:
                return json_response(400, {"error": f"Invalid JSON payload: {e}"})
            except SenderError as e:
                return json_response(400, {"error": str(e)})

        # 12. INPUT HTTP: biến môi trường + token X-API-KEY cho shipper
        if path == "/mock/admin/api/http_input/env" and m == "GET":
            from .http_input_keys import shipper_env, shipper_env_script
            fmt = params.get("format", [""])[0] if isinstance(params.get("format"), list) else params.get("format", "")
            if fmt == "shell":
                b = shipper_env_script().encode("utf-8")
                return 200, {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(b))}, b
            return json_response(200, shipper_env())
        if path == "/mock/admin/api/http_input/sign" and m == "POST":
            from .http_input_keys import sign_with_key
            try:
                data = json.loads(body_str) if body_str else {}
                return json_response(200, sign_with_key(data.get("private_key", ""), data.get("payload")))
            except (ValueError, json.JSONDecodeError) as e:
                return json_response(400, {"error": str(e)})
        if path == "/mock/admin/api/http_input/token" and m == "GET":
            from .http_input_keys import make_token
            b = make_token().encode("utf-8")
            return 200, {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(b))}, b

        # 12b. GCP PUB/SUB (pubsub_mock chạy kèm)
        if path.startswith("/mock/admin/api/pubsub"):
            from . import pubsub_runner
            if path == "/mock/admin/api/pubsub/status" and m == "GET":
                return json_response(200, pubsub_runner.status())
            if path == "/mock/admin/api/pubsub/config" and m == "GET":
                host = params.get("host", [""])[0] if isinstance(params.get("host"), list) else params.get("host", "")
                return json_response(200, pubsub_runner.shipper_config(host or "<ip-mock>"))
            if path == "/mock/admin/api/pubsub/publish" and m == "POST":
                try:
                    data = json.loads(body_str) if body_str else {}
                except json.JSONDecodeError as e:
                    return json_response(400, {"error": f"Invalid JSON payload: {e}"})
                code, res = pubsub_runner.publish(data)
                return json_response(code or 502, res)

        # 13. NGUỒN LUỒNG (SLS Alibaba, Azure Event Hubs): trạng thái + bơm thêm log
        if path.startswith("/mock/admin/api/streams"):
            from . import sls_mock, event_hubs_broker, azure_blob_mock
            try:
                data = json.loads(body_str) if body_str else {}
            except json.JSONDecodeError as e:
                return json_response(400, {"error": f"Invalid JSON payload: {e}"})
            if path == "/mock/admin/api/streams" and m == "GET":
                return json_response(200, {
                    "log_service_alibaba": sls_mock.snapshot(),
                    "azure_event_hubs": event_hubs_broker.snapshot(),
                    "azure_blob": azure_blob_mock.snapshot(),
                })
            if path == "/mock/admin/api/streams/sls/inject" and m == "POST":
                if not data.get("project") or not data.get("logstore"):
                    return json_response(400, {"error": "Cần 'project' và 'logstore'"})
                n = sls_mock.inject(data["project"], data["logstore"], int(data.get("count", 10)), {})
                return json_response(200, {"success": True, "injected": n})
            if path == "/mock/admin/api/streams/azure_event_hubs/inject" and m == "POST":
                hub = data.get("hub") or data.get("hub_name") or "insights-logs"
                n = event_hubs_broker.inject(hub, int(data.get("count", 10)))
                return json_response(200, {"success": True, "injected": n})

        return json_response(404, {"error": "Admin API endpoint not found", "path": path})
