"""
Phase 1 demo: define a schema, insert rows, scan them back, delete one,
and reopen the file to prove durability (data survives a process restart).

Run: python demo.py
"""

import os
from pydb.storage.heap_file import HeapFile
from pydb.storage.record import Schema, Column, ColType

DB_FILE = "demo.db"

users_schema = Schema([
    Column("id", ColType.INT),
    Column("name", ColType.VARCHAR),
    Column("email", ColType.VARCHAR),
])


def fresh_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


def main():
    fresh_db()

    print("--- inserting rows ---")
    heap = HeapFile(DB_FILE)
    rids = []
    sample_users = [
        {"id": 1, "name": "Ada Lovelace", "email": "ada@example.com"},
        {"id": 2, "name": "Alan Turing", "email": "alan@example.com"},
        {"id": 3, "name": "Grace Hopper", "email": "grace@example.com"},
    ]
    for user in sample_users:
        data = users_schema.serialize(user)
        rid = heap.insert(data)
        rids.append(rid)
        print(f"  inserted {user['name']!r} at RID {rid}")

    print("\n--- scanning all rows ---")
    for rid, data in heap.scan():
        row = users_schema.deserialize(data)
        print(f"  RID {rid}: {row}")

    print(f"\n--- deleting RID {rids[1]} (Alan Turing) ---")
    heap.delete(rids[1])

    print("\n--- scanning after delete ---")
    for rid, data in heap.scan():
        row = users_schema.deserialize(data)
        print(f"  RID {rid}: {row}")

    print("\n--- closing (flushes buffer pool to disk) ---")
    heap.close()

    print("\n--- reopening file from disk to check durability ---")
    heap2 = HeapFile(DB_FILE)
    for rid, data in heap2.scan():
        row = users_schema.deserialize(data)
        print(f"  RID {rid}: {row}")
    heap2.close()

    print("\nDone. File on disk:", os.path.getsize(DB_FILE), "bytes")


if __name__ == "__main__":
    main()
