"""Sinh mock data Rapid7 theo đúng format response của API.

- InsightIDR: GET  /idr/v2/investigations           -> datasets/rapid7_idr_investigations.json
- InsightVM : POST /vm/v4/integration/assets        -> datasets/rapid7_vm_assets.json

Chạy: python3 generate_rapid7_dataset.py [so_ban_ghi]
"""
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 50
REGION = "us"
ORG_ID = "44d88612-fea8-a8f3-6de8-2e1278abb02f"
START = datetime(2026, 10, 15, 0, 0, 0, tzinfo=timezone.utc)
SPAN_SECONDS = 2 * 24 * 3600

random.seed(7)


def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def rand_time(base=START, span=SPAN_SECONDS):
    return base + timedelta(seconds=random.randint(0, span))


# ---------------------------------------------------------------- InsightIDR
IDR_TITLES = [
    ("Suspicious Authentication - Brute Force Against Domain Account", "ALERT"),
    ("Attacker Technique - PowerShell Encoded Command", "ALERT"),
    ("Account Authenticated to Critical Asset From New Source", "ALERT"),
    ("Network Access For Threat - Known Malicious IP", "ALERT"),
    ("Ingress From Disabled Account", "ALERT"),
    ("Spoofed Domain Email Received", "ALERT"),
    ("Manual investigation - unusual VPN logins", "MANUAL"),
    ("Threat hunt - lateral movement via SMB", "HUNT"),
]
ANALYSTS = [
    {"name": "SOC Analyst 01", "email": "soc01@example.com"},
    {"name": "SOC Analyst 02", "email": "soc02@example.com"},
    {"name": "SOC Lead", "email": "soclead@example.com"},
]


def gen_investigation(i):
    created = rand_time()
    first_alert = created - timedelta(seconds=random.randint(5, 900))
    latest_alert = created + timedelta(seconds=random.randint(0, 3600))
    status = random.choice(["OPEN", "INVESTIGATING", "WAITING", "CLOSED"])
    title, source = random.choice(IDR_TITLES)
    inv_id = uuid.uuid4()
    return {
        "rrn": f"rrn:investigation:{REGION}:{ORG_ID}:investigation:{inv_id.hex[:12].upper()}",
        "organization_id": ORG_ID,
        "title": title,
        "source": source,
        "status": status,
        "priority": random.choice(["UNSPECIFIED", "LOW", "MEDIUM", "HIGH", "CRITICAL"]),
        "disposition": (random.choice(["BENIGN", "MALICIOUS", "NOT_APPLICABLE"])
                        if status == "CLOSED" else "UNDECIDED"),
        "assignee": random.choice(ANALYSTS + [None]),
        "created_time": ts(created),
        "last_accessed": ts(latest_alert + timedelta(minutes=random.randint(1, 120))),
        "first_alert_time": ts(first_alert) if source == "ALERT" else None,
        "latest_alert_time": ts(latest_alert) if source == "ALERT" else None,
        "responsibility": random.choice(["CUSTOMER", "RAPID7"]),
        "tags": random.sample(["vpn", "ad", "phishing", "critical-asset", "edr"], k=random.randint(0, 2)),
    }


investigations = sorted((gen_investigation(i) for i in range(COUNT)),
                        key=lambda x: x["created_time"], reverse=True)
idr_response = {
    "data": investigations,
    "metadata": {"index": 0, "size": COUNT, "total_data": COUNT, "total_pages": 1},
}

# ----------------------------------------------------------------- InsightVM
VULNS = [
    ("apache-httpd-cve-2021-41773", 443, "Upgrade Apache HTTPD to 2.4.51 or later", "critical"),
    ("openssl-cve-2022-0778", 443, "Upgrade OpenSSL to 1.1.1n or later", "severe"),
    ("ssh-weak-kex-algorithms", 22, "Disable weak SSH key exchange algorithms", "moderate"),
    ("tls-server-cert-expired", 8443, "Renew the TLS server certificate", "moderate"),
    ("msft-cve-2023-23397", None, "Install Microsoft Outlook March 2023 security update", "critical"),
    ("generic-icmp-timestamp", None, "Block ICMP timestamp requests at the firewall", "moderate"),
    ("http-trace-method-enabled", 80, "Disable HTTP TRACE method", "severe"),
    ("wso2-cve-2022-29464", 9443, "Apply WSO2 security patch WSO2-2021-1738", "critical"),
]
OSES = [
    ("Linux", "Ubuntu", "Ubuntu Linux", "22.04", "Ubuntu Linux 22.04"),
    ("Linux", "Red Hat", "Red Hat Enterprise Linux", "8.6", "Red Hat Enterprise Linux 8.6"),
    ("Windows", "Microsoft", "Microsoft Windows Server 2019", "1809", "Microsoft Windows Server 2019 Standard Edition"),
    ("Windows", "Microsoft", "Microsoft Windows 10", "22H2", "Microsoft Windows 10 Enterprise Edition 22H2"),
]
SITES = ["HQ-Datacenter", "Branch-HN", "Branch-HCM", "DMZ"]


def gen_vuln_finding(vuln, scan_end):
    vid, port, fix, _sev = vuln
    first = scan_end - timedelta(days=random.randint(0, 90))
    return {
        "check_id": None,
        "first_found": ts(first),
        "key": "",
        "last_found": ts(scan_end),
        "nic": None,
        "port": port,
        "proof": f"<p>Vulnerable version detected for {vid}</p>",
        "protocol": "TCP" if port else None,
        "solution_fix": f"<p>{fix}</p>",
        "solution_id": f"sol-{vid}",
        "solution_summary": fix,
        "solution_type": "rollup",
        "status": random.choice(["VULNERABLE_VERS", "VULNERABLE_EXPL", "VULNERABLE_POTENTIAL"]),
        "vulnerability_id": vid,
    }


def gen_asset(i):
    family, vendor, name, version, desc = random.choice(OSES)
    scan_end = rand_time()
    scan_start = scan_end - timedelta(minutes=random.randint(3, 40))
    found = random.sample(VULNS, k=random.randint(0, 5))
    sev = [v[3] for v in found]
    is_win = family == "Windows"
    return {
        "id": f"{ORG_ID}-default-asset-{1000 + i}",
        "assessed_for_policies": False,
        "assessed_for_vulnerabilities": True,
        "critical_vulnerabilities": sev.count("critical"),
        "severe_vulnerabilities": sev.count("severe"),
        "moderate_vulnerabilities": sev.count("moderate"),
        "total_vulnerabilities": len(found),
        "exploits": random.randint(0, sev.count("critical")),
        "malware_kits": 0,
        "host_name": f"{'WIN' if is_win else 'srv'}-{random.choice(['app', 'db', 'web', 'ad'])}-{i:03d}",
        "ip": f"10.{random.randint(10, 30)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
        "mac": ":".join(f"{random.randint(0, 255):02X}" for _ in range(6)),
        "os_architecture": "x86_64",
        "os_description": desc,
        "os_family": family,
        "os_name": name,
        "os_system_name": name,
        "os_type": "General",
        "os_vendor": vendor,
        "os_version": version,
        "risk_score": round(sum({"critical": 900, "severe": 400, "moderate": 120}[s] for s in sev)
                            * random.uniform(0.8, 1.2), 2),
        "last_scan_start": ts(scan_start),
        "last_scan_end": ts(scan_end),
        "last_assessed_for_vulnerabilities": ts(scan_end),
        "tags": [
            {"name": random.choice(SITES), "type": "SITE"},
            {"name": random.choice(["Production", "Staging"]), "type": "CUSTOM"},
        ],
        "new": [gen_vuln_finding(v, scan_end) for v in found[:1]],
        "same": [gen_vuln_finding(v, scan_end) for v in found[1:]],
        "remediated": [],
    }


assets = [gen_asset(i) for i in range(COUNT)]
vm_response = {
    "data": assets,
    "metadata": {"number": 0, "size": COUNT, "cursor": None},
    "links": [{"rel": "self", "href": f"https://{REGION}.api.insight.rapid7.com/vm/v4/integration/assets?size={COUNT}"}],
}

with open("datasets/rapid7_idr_investigations.json", "w") as f:
    json.dump(idr_response, f, indent=2, ensure_ascii=False)
with open("datasets/rapid7_vm_assets.json", "w") as f:
    json.dump(vm_response, f, indent=2, ensure_ascii=False)

print(f"Generated {COUNT} investigations -> datasets/rapid7_idr_investigations.json")
print(f"Generated {COUNT} assets         -> datasets/rapid7_vm_assets.json")
