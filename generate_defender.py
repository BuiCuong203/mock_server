import json
import uuid
import random
from datetime import datetime, timedelta

start_time = datetime(2026, 10, 6, 0, 0, 0)
end_time = datetime(2026, 10, 7, 12, 0, 0)
delta_seconds = int((end_time - start_time).total_seconds())

records = []
for i in range(10000):
    offset = random.randint(0, delta_seconds)
    evt_time = start_time + timedelta(seconds=offset)
    past_evt_time = evt_time - timedelta(seconds=random.randint(10, 600))
    
    records.append({
        "id": f"da-{int(evt_time.timestamp())}-{uuid.uuid4().hex[:6]}",
        "incidentId": random.randint(10000, 99999),
        "investigationId": None,
        "assignedTo": None,
        "severity": random.choice(["Low", "Medium", "High", "Informational"]),
        "status": "New",
        "classification": None,
        "determination": None,
        "investigationState": "Queued",
        "detectionSource": "WindowsDefenderAtp",
        "detectorId": random.choice(["powershell_encoded_exec", "malware_signature_match", "brute_force_login"]),
        "category": random.choice(["Execution", "DefenseEvasion", "CredentialAccess"]),
        "threatFamilyName": None,
        "title": random.choice(["Suspicious execution via PowerShell encoded payload", "Malware detected on machine", "Multiple failed login attempts"]),
        "description": "A suspicious activity was detected which aligns with known attack techniques.",
        "alertCreationTime": evt_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "creationTime": evt_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),  # Thêm field này để OData filter dễ dàng nếu shipper cần
        "firstEventTime": past_evt_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "lastEventTime": evt_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "lastUpdateTime": evt_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "machineId": str(uuid.uuid4()),
        "computerDnsName": f"DESKTOP-SEC-VN{random.randint(10, 99)}"
    })

# Sort chronologically
records.sort(key=lambda x: x["alertCreationTime"])

with open("/Users/hoangnx/Project/Playbox/mock-server/datasets/defender_seed.json", "w") as f:
    json.dump(records, f, indent=2)
print(f"Generated {len(records)} records in defender_seed.json")
