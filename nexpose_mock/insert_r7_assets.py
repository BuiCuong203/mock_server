"""Insert file r7_assets_*.json vào MongoDB (collection r7_assets của siem-va-integrate).

Cài thư viện:  pip install pymongo
Chạy:          python3 insert_r7_assets.py
               python3 insert_r7_assets.py r7_assets_5000.json
"""
import json
import os
import sys

from pymongo import MongoClient, ReplaceOne

# ====== ĐIỀN THÔNG TIN Ở ĐÂY ======
MONGO_URI = "mongodb://siem:<password>@localhost:27017/siem?authSource=siem"
COLLECTION = "r7_assets"
DATA_FILE = "r7_assets_1000.json"
CLEAR_BEFORE_INSERT = False  # True: xóa toàn bộ r7_assets trước khi insert
BATCH_SIZE = 500
# ==================================


def main():
    data_file = sys.argv[1] if len(sys.argv) > 1 else DATA_FILE
    if not os.path.isabs(data_file):
        data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), data_file)

    with open(data_file, encoding="utf-8") as f:
        docs = json.load(f)
    print(f"Đọc {len(docs)} bản ghi từ {data_file}")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    col = client.get_database()[COLLECTION]  # database lấy từ URI (/siem)
    client.admin.command("ping")
    print(f"Kết nối OK -> {col.database.name}.{COLLECTION} (hiện có {col.count_documents({})} bản ghi)")

    if CLEAR_BEFORE_INSERT:
        deleted = col.delete_many({}).deleted_count
        print(f"Đã xóa {deleted} bản ghi cũ")

    # Upsert theo id giống job sync: chạy lại nhiều lần không bị trùng
    inserted = updated = 0
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        result = col.bulk_write([ReplaceOne({"id": d["id"]}, d, upsert=True) for d in batch], ordered=False)
        inserted += result.upserted_count
        updated += result.modified_count
        print(f"  {min(i + BATCH_SIZE, len(docs))}/{len(docs)}")

    print(f"Xong: thêm mới {inserted}, cập nhật {updated}. Tổng trong collection: {col.count_documents({})}")


if __name__ == "__main__":
    main()
