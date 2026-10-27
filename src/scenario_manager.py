import os
import json
import threading
from typing import Dict, List, Optional, Tuple, Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .config import RULES_DIR, SCENARIOS_DIR, GREEN, YELLOW, CYAN, RESET
from .rule_engine import MockRule


class ScenarioManager:
    """
    Quản lý tập trung toàn bộ các Rule và Scenario động:
    - Base Rules: Đọc tự động từ thư mục rules/*.json / *.yaml (REST API, Azure, Defender, M365 Proxy, AWS Proxy, ...)
    - Scenarios: Đọc từ thư mục scenarios/*.json (default, rate_limit_429, auth_fail_401, mix_example, ...)
    - Dynamic Rules: Thêm/Sửa/Xóa realtime từ Web Dashboard hoặc Admin REST API (lưu vào rules/custom_overrides.json)
    """
    def __init__(self, rules_dir: str = RULES_DIR, scenarios_dir: str = SCENARIOS_DIR):
        self.rules_dir = rules_dir
        self.scenarios_dir = scenarios_dir
        self.base_rules: List[MockRule] = []
        self.dynamic_rules: List[MockRule] = []
        self.scenarios: Dict[str, Dict[str, Any]] = {}
        self.active_scenario_name = "default"
        self._lock = threading.Lock()

        self.load_all()

    def load_all(self):
        with self._lock:
            self._load_base_rules()
            self._load_dynamic_rules()
            self._load_scenarios()

    def _load_base_rules(self):
        self.base_rules.clear()
        if not os.path.exists(self.rules_dir):
            os.makedirs(self.rules_dir, exist_ok=True)
            return

        rule_files = sorted(os.listdir(self.rules_dir))
        for fname in rule_files:
            if fname == "custom_overrides.json":
                continue # Nạp riêng
            fpath = os.path.join(self.rules_dir, fname)
            if not os.path.isfile(fpath):
                continue

            rules_data = self._read_data_file(fpath)
            if isinstance(rules_data, list):
                for r in rules_data:
                    if isinstance(r, dict):
                        self.base_rules.append(MockRule(r, source_file=fname))
            elif isinstance(rules_data, dict):
                # Trường hợp file chứa 1 rule
                self.base_rules.append(MockRule(rules_data, source_file=fname))

        print(f"{GREEN}[RULES] Đã nạp {len(self.base_rules)} base rules động từ {self.rules_dir}{RESET}")

    def _load_dynamic_rules(self):
        self.dynamic_rules.clear()
        custom_file = os.path.join(self.rules_dir, "custom_overrides.json")
        if os.path.exists(custom_file):
            data = self._read_data_file(custom_file)
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict):
                        self.dynamic_rules.append(MockRule(r, source_file="custom_overrides.json"))

    def _load_scenarios(self):
        self.scenarios.clear()
        if not os.path.exists(self.scenarios_dir):
            os.makedirs(self.scenarios_dir, exist_ok=True)
            return

        for fname in sorted(os.listdir(self.scenarios_dir)):
            fpath = os.path.join(self.scenarios_dir, fname)
            if not os.path.isfile(fpath):
                continue

            content = self._read_data_file(fpath)
            scenario_id = os.path.splitext(fname)[0]

            if content and isinstance(content, dict):
                name = content.get("name", scenario_id)
                description = content.get("description", "")
                raw_rules = content.get("rules", [])
                rules = [MockRule(r, source_file=fname) for r in raw_rules if isinstance(r, dict)]

                self.scenarios[name] = {
                    "name": name,
                    "description": description,
                    "file": fname,
                    "rules": rules
                }

        print(f"{GREEN}[SCENARIO] Đã nạp {len(self.scenarios)} kịch bản: {', '.join(self.scenarios.keys())}{RESET}")

    def _read_data_file(self, fpath: str) -> Any:
        try:
            if fpath.endswith(".json"):
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif fpath.endswith((".yaml", ".yml")) and HAS_YAML:
                with open(fpath, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
        except Exception as e:
            print(f"{YELLOW}[MOCK] Cảnh báo lỗi đọc file {fpath}: {e}{RESET}")
        return None

    def _save_dynamic_rules(self):
        custom_file = os.path.join(self.rules_dir, "custom_overrides.json")
        try:
            with open(custom_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.dynamic_rules], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{YELLOW}[RULES] Lỗi lưu custom_overrides.json: {e}{RESET}")

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for name, sc in self.scenarios.items():
                result.append({
                    "name": name,
                    "description": sc.get("description", ""),
                    "rules_count": len(sc.get("rules", [])),
                    "is_active": name == self.active_scenario_name
                })
            return result

    def set_active_scenario(self, name: str) -> bool:
        with self._lock:
            if name in self.scenarios:
                self.active_scenario_name = name
                print(f"{CYAN}[SCENARIO] Đã chuyển sang kịch bản hoạt động: {name}{RESET}")
                return True
            return False

    def add_dynamic_rule(self, rule_data: Dict[str, Any]) -> MockRule:
        with self._lock:
            rule = MockRule(rule_data, source_file="custom_overrides.json")
            self.dynamic_rules.insert(0, rule)
            self._save_dynamic_rules()
            return rule

    def remove_dynamic_rule(self, rule_id: str) -> bool:
        with self._lock:
            initial_len = len(self.dynamic_rules)
            self.dynamic_rules = [r for r in self.dynamic_rules if r.id != rule_id]
            if len(self.dynamic_rules) < initial_len:
                self._save_dynamic_rules()
                return True
            return False

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        with self._lock:
            # 1. Dynamic rules
            for r in self.dynamic_rules:
                if r.id == rule_id:
                    r.enabled = enabled
                    self._save_dynamic_rules()
                    return True
            # 2. Scenario rules
            active_sc = self.scenarios.get(self.active_scenario_name, {})
            for r in active_sc.get("rules", []):
                if r.id == rule_id:
                    r.enabled = enabled
                    return True
            # 3. Base rules
            for r in self.base_rules:
                if r.id == rule_id:
                    r.enabled = enabled
                    return True
            return False

    def update_rule(self, rule_id: str, new_data: Dict[str, Any]) -> Tuple[bool, str, Optional[MockRule]]:
        with self._lock:
            # 1. Dynamic rules
            for i, r in enumerate(self.dynamic_rules):
                if r.id == rule_id:
                    updated = MockRule(new_data, source_file="custom_overrides.json")
                    updated.id = rule_id
                    self.dynamic_rules[i] = updated
                    self._save_dynamic_rules()
                    return True, "Cập nhật Dynamic Rule thành công", updated

            # 2. Base rules (lưu ngược lại file nguồn trong rules/)
            for i, r in enumerate(self.base_rules):
                if r.id == rule_id:
                    src_file = r.source_file
                    updated = MockRule(new_data, source_file=src_file)
                    updated.id = rule_id
                    self.base_rules[i] = updated

                    if src_file:
                        fpath = os.path.join(self.rules_dir, src_file)
                        if os.path.exists(fpath):
                            try:
                                with open(fpath, "r", encoding="utf-8") as f:
                                    file_data = json.load(f)
                                if isinstance(file_data, list):
                                    for idx, item in enumerate(file_data):
                                        if isinstance(item, dict) and item.get("id") == rule_id:
                                            clean_data = new_data.copy()
                                            clean_data["id"] = rule_id
                                            file_data[idx] = clean_data
                                            break
                                    with open(fpath, "w", encoding="utf-8") as f:
                                        json.dump(file_data, f, indent=2, ensure_ascii=False)
                                elif isinstance(file_data, dict) and file_data.get("id") == rule_id:
                                    clean_data = new_data.copy()
                                    clean_data["id"] = rule_id
                                    with open(fpath, "w", encoding="utf-8") as f:
                                        json.dump(clean_data, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                print(f"[UPDATE ERROR] Không thể ghi file {src_file}: {e}")
                    return True, f"Cập nhật và lưu vào {src_file} thành công", updated

            # 3. Active scenario rules
            active_sc = self.scenarios.get(self.active_scenario_name, {})
            sc_rules = active_sc.get("rules", [])
            for i, r in enumerate(sc_rules):
                if r.id == rule_id:
                    sc_file = active_sc.get("file")
                    updated = MockRule(new_data, source_file=sc_file)
                    updated.id = rule_id
                    sc_rules[i] = updated
                    if sc_file:
                        fpath = os.path.join(self.scenarios_dir, sc_file)
                        if os.path.exists(fpath):
                            try:
                                with open(fpath, "r", encoding="utf-8") as f:
                                    sc_data = json.load(f)
                                if isinstance(sc_data, dict) and "rules" in sc_data:
                                    for idx, item in enumerate(sc_data["rules"]):
                                        if isinstance(item, dict) and item.get("id") == rule_id:
                                            clean_data = new_data.copy()
                                            clean_data["id"] = rule_id
                                            sc_data["rules"][idx] = clean_data
                                            break
                                    with open(fpath, "w", encoding="utf-8") as f:
                                        json.dump(sc_data, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                print(f"[UPDATE ERROR] Không thể ghi scenario {sc_file}: {e}")
                    return True, f"Cập nhật kịch bản {self.active_scenario_name} thành công", updated

            # 4. Nếu không tìm thấy, tự động tạo mới dưới dạng Dynamic Rule
            rule = self.add_dynamic_rule(new_data)
            return True, "Đã tạo mới Dynamic Rule thành công", rule

    def get_all_active_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            rules_list = []
            # 1. Dynamic overrides (highest priority)
            for r in self.dynamic_rules:
                d = r.to_dict()
                d["source"] = "dynamic_override"
                rules_list.append(d)

            # 2. Active scenario rules
            active_sc = self.scenarios.get(self.active_scenario_name, {})
            for r in active_sc.get("rules", []):
                d = r.to_dict()
                d["source"] = f"scenario:{self.active_scenario_name}"
                rules_list.append(d)

            # 3. Base rules
            for r in self.base_rules:
                d = r.to_dict()
                d["source"] = f"base:{r.source_file or 'rules'}"
                rules_list.append(d)

            return rules_list

    def find_matching_rule(
        self,
        method: str,
        path: str,
        host: str,
        headers: Dict[str, str],
        body: str,
        is_proxy: bool = False
    ) -> Optional[Tuple[MockRule, str]]:
        with self._lock:
            # 1. Dynamic overrides (ưu tiên số 1)
            for rule in self.dynamic_rules:
                if rule.matches(method, path, host, headers, body, is_proxy):
                    return rule, "dynamic_override"

            # 2. Active scenario rules (ưu tiên số 2)
            active_sc = self.scenarios.get(self.active_scenario_name, {})
            for rule in active_sc.get("rules", []):
                if rule.matches(method, path, host, headers, body, is_proxy):
                    return rule, f"scenario:{self.active_scenario_name}"

            # 3. Base declarative rules (ưu tiên số 3)
            for rule in self.base_rules:
                if rule.matches(method, path, host, headers, body, is_proxy):
                    return rule, f"base:{rule.source_file or 'rules'}"

            return None


# Global scenario manager instance
scenario_manager = ScenarioManager()
