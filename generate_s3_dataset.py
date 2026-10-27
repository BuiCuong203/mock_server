import json
import datetime

start_time = datetime.datetime.fromisoformat("2026-10-07T20:17:00+07:00")
end_time = datetime.datetime.fromisoformat("2026-10-08T23:59:59+07:00")

curr_time = start_time
event_id = 1

with open('datasets/aws_s3_large.log', 'w') as f:
    while curr_time <= end_time:
        ts_iso = curr_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for i in range(5):
            record = {
                "eventVersion": "1.08",
                "userIdentity": {"type": "IAMUser", "userName": f"user-{event_id}"},
                "eventTime": ts_iso,
                "eventSource": "s3.amazonaws.com",
                "eventName": "GetObject",
                "awsRegion": "us-east-1",
                "requestParameters": {"bucketName": "mock-s3-bucket", "key": f"data-{event_id}.txt"},
                "responseElements": None,
                "eventID": f"s3-evt-{event_id}"
            }
            f.write(json.dumps(record) + "\n")
            event_id += 1
        
        curr_time += datetime.timedelta(minutes=1)

print(f"Generated {event_id-1} records for AWS S3.")
