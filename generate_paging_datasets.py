import json
import uuid
from datetime import datetime, timedelta

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_time(offset_mins):
    base_time = datetime(2030, 10, 6, 0, 0, 0)
    t = base_time + timedelta(minutes=offset_mins)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

# 1. AZURE SIGN-INS
def generate_azure_page(page_num, count, has_next=False):
    records = []
    for i in range(count):
        records.append({
            "id": str(uuid.uuid4()),
            "createdDateTime": get_time(page_num * 1000 + i),
            "userPrincipalName": f"user{i}@contoso.onmicrosoft.com",
            "appDisplayName": "Office 365 Exchange Online",
            "ipAddress": f"118.70.1.{i%255}",
            "location": {"city": "Hanoi", "countryOrRegion": "VN"},
            "status": {"errorCode": 0},
            "clientAppUsed": "Browser"
        })
    body = {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#auditLogs/signIns",
        "value": records
    }
    if has_next:
        body["@odata.nextLink"] = "https://graph.microsoft.com/v1.0/auditLogs/signIns?$skiptoken=skip_token_page_2"
    else:
        body["@odata.nextLink"] = None
    return body

save_json("datasets/azure_sign_ins_page1.json", generate_azure_page(1, 100, True))
save_json("datasets/azure_sign_ins_page2.json", generate_azure_page(2, 50, False))

with open("scenarios/azure_pagination_sign_ins.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "azure_sign_ins_page1.json"},
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "azure_sign_ins_page2.json"}
]
save_json("scenarios/azure_pagination_sign_ins.json", s)

# 2. M365
def generate_m365_page(page_num, count):
    records = []
    for i in range(count):
        records.append({
            "CreationTime": get_time(page_num * 1000 + i),
            "Id": str(uuid.uuid4()),
            "Operation": "FileDownloaded",
            "OrganizationId": "tenant-01",
            "RecordType": 6,
            "ResultStatus": "Success",
            "UserId": f"employee{i}@contoso.com",
            "ClientIPAddress": f"14.162.22.{i%255}",
            "SourceFileName": f"Report_2030_{i}.xlsx"
        })
    return records

save_json("datasets/m365_page1.json", generate_m365_page(1, 150))
save_json("datasets/m365_page2.json", generate_m365_page(2, 80))

with open("scenarios/m365_pagination_nextpageuri.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json", "NextPageUri": "https://manage.office.com/api/v1.0/tenant/activity/feed/subscriptions/content?nextPage=page_2"}, "body_type": "fixture", "fixture": "m365_page1.json"},
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "m365_page2.json"}
]
save_json("scenarios/m365_pagination_nextpageuri.json", s)


# 3. REST API CURSOR
def generate_rest_page(page_num, count, next_cursor=None, limit_offset=False, page_size=False, next_link=False):
    records = []
    for i in range(count):
        records.append({
            "id": f"evt-{page_num}-{i}",
            "timestamp": get_time(page_num * 1000 + i),
            "event_type": "login_success",
            "src_ip": f"10.0.0.{i%255}",
            "username": f"admin{i}",
            "severity": "info"
        })
    body = {"events": records}
    if not limit_offset and not page_size:
        if next_cursor is not None:
            body["next_cursor"] = next_cursor
        if next_link:
            body["next_page_url"] = next_link
    return body

save_json("datasets/rest_cursor_page1.json", generate_rest_page(1, 100, next_cursor="token_pg2"))
save_json("datasets/rest_cursor_page2.json", generate_rest_page(2, 45, next_cursor=None))

with open("scenarios/rest_api_paging_cursor.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_cursor_page1.json"},
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_cursor_page2.json"}
]
save_json("scenarios/rest_api_paging_cursor.json", s)

# REST API Limit-Offset
save_json("datasets/rest_limit_page1.json", generate_rest_page(1, 100, limit_offset=True))
save_json("datasets/rest_limit_page2.json", generate_rest_page(2, 0, limit_offset=True))
with open("scenarios/rest_api_paging_limit_offset.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_limit_page1.json"},
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_limit_page2.json"}
]
save_json("scenarios/rest_api_paging_limit_offset.json", s)

# REST API Page-Size
with open("scenarios/rest_api_paging_page_size.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_limit_page1.json"}, # reuse
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_limit_page2.json"}
]
save_json("scenarios/rest_api_paging_page_size.json", s)

# REST API NextLink
save_json("datasets/rest_nextlink_page1.json", generate_rest_page(1, 100, next_link="http://localhost:8881/mock/rest_api/logs?page=2"))
save_json("datasets/rest_nextlink_page2.json", generate_rest_page(2, 35, next_link=None))
with open("scenarios/rest_api_paging_next_link.json", "r") as f:
    s = json.load(f)
s["rules"][0]["response"]["sequence"] = [
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_nextlink_page1.json"},
    {"status": 200, "headers": {"Content-Type": "application/json"}, "body_type": "fixture", "fixture": "rest_nextlink_page2.json"}
]
save_json("scenarios/rest_api_paging_next_link.json", s)

print("Created paging datasets and updated scenarios.")
