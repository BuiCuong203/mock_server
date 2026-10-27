#!/usr/bin/env python3
"""
Sinh toàn bộ dataset cho scenario "default" (6 nguồn cloud), đúng schema mà CyM-Log-Shipper đọc.

Khoảng thời gian: từ 00:00 UTC của --days-before ngày trước tới hết --days-after ngày sau.
Scenario bật realtime nên bản ghi ở tương lai chỉ "xuất hiện" khi tới giờ -> log phát sinh dần như thật.
Bản ghi trong cùng nguồn cách đều nhau (không trùng giây) để mốc checkpoint không bỏ sót / không trùng.
Sinh lại định kỳ (vd mỗi tuần) để dữ liệu luôn phủ thời điểm hiện tại.

  datasets/rest_kafka_demo.json   REST /mock/rest_api/v2/logs  (data[], created_at)      - cym.rest_api_kafka.yml
  datasets/rest_large.json        REST /mock/rest_api/logs     (events[], timestamp)     - cym.mock_all_cloud.yml
  datasets/azure_large.json       Graph auditLogs/signIns      (value[], createdDateTime)
  datasets/azure_directory_audits.json Graph auditLogs/directoryAudits (value[], activityDateTime)
  datasets/m365_large.json        Office 365 Activity Feed     (CreationTime, contentType = 4 loại Audit.*)
  datasets/defender_large.json    Defender alerts              (value[], alertCreationTime)
  datasets/cloudwatch_large.json  FilterLogEvents              (timestamp ms, message, ingestionTime)
  datasets/s3_cloudtrail.json     File CloudTrail trên S3       (Records[], eventTime)

Dùng: python3 generate_default_datasets.py [--days-before 2] [--days-after 5]
"""
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

USERS = ["sec_admin", "sales_manager", "sys_daemon", "dev_nguyen", "hr_tran", "finance_le", "guest_01"]
IPS = lambda rnd: f"{rnd.choice([10, 172, 118, 14])}.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}"


def z(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def ticks(start, end, per_minute):
    step = timedelta(seconds=60 / per_minute)
    t = start
    while t < end:
        yield t
        t += step


def uid(rnd):
    return str(uuid.UUID(int=rnd.getrandbits(128), version=4))


def dump(name, records):
    with open(f"datasets/{name}", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
    print(f"datasets/{name:24s} {len(records):6d} bản ghi")


def gen_rest_v2(start, end, rnd):
    actions = [("login_success", "info", "User logged in successfully"), ("login_failed", "medium", "Invalid password"),
               ("export_customers", "low", "User exported customer profiles to CSV"),
               ("permission_changed", "high", "Role changed to administrator"),
               ("file_deleted", "medium", "File removed from shared drive"),
               ("backup_completed", "info", "Daily database snapshot completed"),
               ("api_key_created", "high", "New API key generated")]
    out = []
    for n, t in enumerate(ticks(start, end, 5), 1):
        user = rnd.choice(USERS)
        action, severity, text = rnd.choice(actions)
        out.append({"event_id": f"rest-{n:07d}", "created_at": z(t), "user": user, "src_ip": IPS(rnd),
                    "action": action, "severity": severity, "message": f"{text} ({user})"})
    return out


def gen_rest_v1(start, end, rnd):
    out = []
    for n, t in enumerate(ticks(start, end, 5), 1):
        ok = rnd.random() > 0.2
        out.append({"id": f"rest-evt-{n:07d}", "timestamp": z(t), "user": rnd.choice(USERS), "src_ip": IPS(rnd),
                    "status": "success" if ok else "failure",
                    "message": "Access granted" if ok else "Access denied"})
    return out


def gen_azure(start, end, rnd):
    apps = ["Office 365 Exchange Online", "Microsoft Teams", "Azure Portal", "SharePoint Online", "Microsoft Graph"]
    cities = [("Hanoi", "VN"), ("Ho Chi Minh City", "VN"), ("Singapore", "SG"), ("Tokyo", "JP")]
    out = []
    for t in ticks(start, end, 5):
        user = rnd.choice(USERS)
        failed = rnd.random() < 0.15
        city, country = rnd.choice(cities)
        out.append({"id": uid(rnd), "createdDateTime": z(t),
                    "userPrincipalName": f"{user}@contoso.onmicrosoft.com", "userDisplayName": user,
                    "userId": uid(rnd), "appId": uid(rnd), "appDisplayName": rnd.choice(apps),
                    "ipAddress": IPS(rnd), "clientAppUsed": rnd.choice(["Browser", "Mobile Apps and Desktop clients"]),
                    "status": {"errorCode": 50126 if failed else 0,
                               "failureReason": "Invalid username or password" if failed else None},
                    "location": {"city": city, "countryOrRegion": country}})
    return out


def gen_m365(start, end, rnd):
    kinds = [("Audit.AzureActiveDirectory", "AzureActiveDirectory", "UserLoggedIn", 15),
             ("Audit.Exchange", "Exchange", "MailItemsAccessed", 50),
             ("Audit.SharePoint", "SharePoint", "FileAccessed", 6),
             ("Audit.General", "MicrosoftTeams", "TeamsSessionStarted", 25)]
    out = []
    for i, t in enumerate(ticks(start, end, 8)):
        ct, workload, op, rtype = kinds[i % 4]  # 2 bản ghi/phút cho mỗi content type
        user = rnd.choice(USERS)
        out.append({"CreationTime": t.strftime("%Y-%m-%dT%H:%M:%S"), "Id": uid(rnd), "Operation": op,
                    "OrganizationId": "mock-tenant-id", "RecordType": rtype, "ResultStatus": "Succeeded",
                    "UserKey": uid(rnd), "UserType": 0, "Workload": workload,
                    "UserId": f"{user}@contoso.onmicrosoft.com", "ClientIP": IPS(rnd),
                    "ObjectId": f"{workload.lower()}-object-{rnd.randint(1, 999)}", "contentType": ct})
    return out


def gen_defender(start, end, rnd):
    kinds = [("Suspicious PowerShell command line", "Execution", "Medium"),
             ("Credential dumping activity observed", "CredentialAccess", "High"),
             ("Ransomware behavior detected", "Impact", "High"),
             ("Suspicious network connection", "CommandAndControl", "Low"),
             ("Malicious file blocked", "Malware", "Informational")]
    out = []
    for n, t in enumerate(ticks(start, end, 2), 1):
        title, category, severity = rnd.choice(kinds)
        out.append({"id": f"da{n:09d}", "incidentId": 10000 + n // 3, "investigationId": None,
                    "severity": severity, "status": "New", "classification": None, "determination": None,
                    "detectionSource": "WindowsDefenderAtp", "category": category, "title": title,
                    "description": f"{title} on host-{n % 50:02d}",
                    "alertCreationTime": z(t), "createdTime": z(t), "firstEventTime": z(t - timedelta(minutes=1)),
                    "lastEventTime": z(t), "lastUpdateTime": z(t), "machineId": uid(rnd),
                    "computerDnsName": f"host-{n % 50:02d}.contoso.local"})
    return out


def gen_cloudwatch(start, end, rnd):
    actions = ["ConsoleLogin", "CreateSecurityGroup", "AuthorizeSecurityGroupIngress", "DeleteBucket", "AssumeRole"]
    out = []
    for n, t in enumerate(ticks(start, end, 5), 1):
        ms = int(t.timestamp() * 1000)
        msg = {"event_id": f"cw-{n:07d}", "log_type": "cloudtrail", "user": rnd.choice(USERS),
               "action": rnd.choice(actions), "ip": IPS(rnd), "time": z(t)}
        out.append({"eventId": f"cw-{n:07d}", "logStreamName": "mock-stream-01", "timestamp": ms,
                    "message": json.dumps(msg, separators=(",", ":")), "ingestionTime": ms + 500})
    return out


def gen_s3(start, end, rnd):
    names = [("signin.amazonaws.com", "ConsoleLogin"), ("s3.amazonaws.com", "GetObject"),
             ("ec2.amazonaws.com", "RunInstances"), ("iam.amazonaws.com", "CreateUser"),
             ("sts.amazonaws.com", "AssumeRole")]
    out = []
    for t in ticks(start, end, 5):
        source, name = rnd.choice(names)
        out.append({"eventVersion": "1.08", "userIdentity": {"type": "IAMUser", "userName": rnd.choice(USERS),
                                                              "accountId": "123456789012"},
                    "eventTime": z(t), "eventSource": source, "eventName": name, "awsRegion": "us-east-1",
                    "sourceIPAddress": IPS(rnd), "userAgent": "aws-cli/2.15.0", "eventID": uid(rnd),
                    "eventType": "AwsApiCall", "recipientAccountId": "123456789012"})
    return out


def gen_azure_audits(start, end, rnd):
    acts = [("Add user", "UserManagement", "Add", "Core Directory"),
            ("Update user", "UserManagement", "Update", "Core Directory"),
            ("Add member to group", "GroupManagement", "Assign", "Core Directory"),
            ("Reset password (by admin)", "UserManagement", "Update", "Self-service Password Management"),
            ("Consent to application", "ApplicationManagement", "Assign", "Core Directory"),
            ("Delete user", "UserManagement", "Delete", "Core Directory")]
    out = []
    for t in ticks(start, end, 5):
        name, category, op, service = rnd.choice(acts)
        actor, target = rnd.choice(USERS), rnd.choice(USERS)
        ok = rnd.random() > 0.1
        out.append({"id": f"Directory_{uid(rnd)}", "category": category, "correlationId": uid(rnd),
                    "result": "success" if ok else "failure", "resultReason": "" if ok else "Insufficient privileges",
                    "activityDisplayName": name, "activityDateTime": z(t), "loggedByService": service,
                    "operationType": op,
                    "initiatedBy": {"user": {"id": uid(rnd), "userPrincipalName": f"{actor}@contoso.onmicrosoft.com",
                                             "ipAddress": IPS(rnd)}, "app": None},
                    "targetResources": [{"id": uid(rnd), "type": "User", "displayName": target,
                                         "userPrincipalName": f"{target}@contoso.onmicrosoft.com"}],
                    "additionalDetails": []})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-before", type=int, default=2)
    ap.add_argument("--days-after", type=int, default=5)
    ap.add_argument("--only", default="",
                    help="Chỉ sinh các nguồn liệt kê, cách nhau dấu phẩy: "
                         "rest_v2,rest_v1,azure,m365,defender,cloudwatch,s3,azure_audits (mặc định: tất cả)")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = today - timedelta(days=args.days_before), today + timedelta(days=args.days_after + 1)
    print(f"Khoảng thời gian: {z(start)} -> {z(end)}")

    jobs = [("rest_v2", "rest_kafka_demo.json", gen_rest_v2), ("rest_v1", "rest_large.json", gen_rest_v1),
            ("azure", "azure_large.json", gen_azure), ("m365", "m365_large.json", gen_m365),
            ("defender", "defender_large.json", gen_defender), ("cloudwatch", "cloudwatch_large.json", gen_cloudwatch),
            ("s3", "s3_cloudtrail.json", gen_s3), ("azure_audits", "azure_directory_audits.json", gen_azure_audits)]
    unknown = only - {j[0] for j in jobs}
    if unknown:
        raise SystemExit(f"--only không hợp lệ: {', '.join(sorted(unknown))}")
    for i, (key, fname, gen) in enumerate(jobs):
        if only and key not in only:
            continue
        # Mỗi nguồn một seed riêng: sinh lại riêng lẻ (--only) vẫn ra cùng nội dung như khi sinh tất cả
        dump(fname, gen(start, end, random.Random(20261008 + i)))


if __name__ == "__main__":
    main()
