import json

with open('datasets/rest_cursor_page1.json', 'r') as f1:
    d1 = json.load(f1)
with open('datasets/rest_cursor_page2.json', 'r') as f2:
    d2 = json.load(f2)

full_events = d1.get('events', []) + d2.get('events', [])

with open('datasets/rest_cursor_dataset.json', 'w') as out:
    json.dump(full_events, out, indent=2)

print(f"Created rest_cursor_dataset.json with {len(full_events)} events.")
