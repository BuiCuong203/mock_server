"""Sinh file JSON các document r7_assets đúng như job sync_rapid7_nexpose lưu vào MongoDB.

Chạy: python3 gen_r7_assets_mongo.py [so_ban_ghi] [file_output]
Import: mongoimport --uri "<MONGO_URI>" --collection r7_assets --jsonArray --file r7_assets_1000.json
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from nexpose_mock_server import AssetStore

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
OUT = sys.argv[2] if len(sys.argv) > 2 else f"r7_assets_{COUNT}.json"


def sanitize_mongo_keys(obj):
    # Giống integration_service.utils.sanitize_mongo_keys
    if isinstance(obj, dict):
        return {k: sanitize_mongo_keys(v) for k, v in obj.items()
                if not (isinstance(k, str) and ("." in k or k.startswith("$")))}
    if isinstance(obj, list):
        return [sanitize_mongo_keys(x) for x in obj]
    return obj


store = AssetStore(COUNT, rescan=0, new=0, seed=7,
                   base_url="https://localhost:3780/api/3", tz=ZoneInfo("Asia/Ho_Chi_Minh"))
# Một phần asset có nhiều lần scan để history đa dạng
now = datetime.now(timezone.utc)
for a in store.rng.sample(list(store.assets.values()), k=COUNT // 3):
    first = datetime.strptime(a["history"][-1]["date"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    store._scan(a, min(now, first + timedelta(hours=store.rng.randint(1, 240))))

sync_time = datetime.now().isoformat()  # giống _now_iso() của service
docs = []
for a in sorted(store.assets.values(), key=lambda x: x["id"]):
    doc = sanitize_mongo_keys(a)
    doc["id"] = str(doc["id"])
    doc["last_sync_date"] = sync_time
    doc["lastScanAt"] = doc["history"][-1]["date"]
    docs.append(doc)

with open(OUT, "w") as f:
    json.dump(docs, f, ensure_ascii=False)
print(f"Generated {len(docs)} documents -> {OUT}")
