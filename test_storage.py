import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydb.storage.page import Page, PageFullError
from pydb.storage.heap_file import HeapFile
from pydb.storage.record import Schema, Column, ColType
from pydb.storage.constants import PAGE_SIZE


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test.db")


# ---------- Page-level tests ----------

def test_page_insert_and_get():
    page = Page()
    slot_id = page.insert(b"hello world")
    assert page.get(slot_id) == b"hello world"


def test_page_multiple_records():
    page = Page()
    ids = [page.insert(f"record-{i}".encode()) for i in range(10)]
    for i, slot_id in enumerate(ids):
        assert page.get(slot_id) == f"record-{i}".encode()


def test_page_delete_marks_tombstone():
    page = Page()
    slot_id = page.insert(b"to be deleted")
    page.delete(slot_id)
    with pytest.raises(KeyError):
        page.get(slot_id)


def test_page_full_raises():
    page = Page()
    big_chunk = b"x" * 500
    with pytest.raises(PageFullError):
        for _ in range(20):  # 20 * ~504 bytes > 4096
            page.insert(big_chunk)


def test_page_live_slots_skips_tombstones():
    page = Page()
    s1 = page.insert(b"keep-me")
    s2 = page.insert(b"delete-me")
    page.delete(s2)
    live = dict(page.live_slots())
    assert live == {s1: b"keep-me"}


def test_page_roundtrip_through_bytes():
    page = Page()
    slot_id = page.insert(b"survives serialization")
    raw = page.to_bytes()
    assert len(raw) == PAGE_SIZE
    page2 = Page(raw)
    assert page2.get(slot_id) == b"survives serialization"


# ---------- HeapFile-level tests ----------

def test_heap_insert_and_get(tmp_db_path):
    heap = HeapFile(tmp_db_path)
    rid = heap.insert(b"row one")
    assert heap.get(rid) == b"row one"
    heap.close()


def test_heap_scan_order_and_contents(tmp_db_path):
    heap = HeapFile(tmp_db_path)
    inserted = [f"row-{i}".encode() for i in range(5)]
    for data in inserted:
        heap.insert(data)
    scanned = [data for _rid, data in heap.scan()]
    assert scanned == inserted
    heap.close()


def test_heap_spans_multiple_pages(tmp_db_path):
    heap = HeapFile(tmp_db_path)
    big_chunk = b"y" * 500
    n = 50  # forces allocation of several pages
    for _ in range(n):
        heap.insert(big_chunk)
    assert heap.pager.num_pages > 1
    results = list(heap.scan())
    assert len(results) == n
    heap.close()


def test_heap_delete_then_scan(tmp_db_path):
    heap = HeapFile(tmp_db_path)
    rid1 = heap.insert(b"keep")
    rid2 = heap.insert(b"remove")
    heap.delete(rid2)
    remaining = [data for _rid, data in heap.scan()]
    assert remaining == [b"keep"]
    heap.close()


def test_heap_durability_across_reopen(tmp_db_path):
    heap = HeapFile(tmp_db_path)
    heap.insert(b"persisted row")
    heap.close()  # flushes buffer pool

    heap2 = HeapFile(tmp_db_path)
    results = [data for _rid, data in heap2.scan()]
    assert results == [b"persisted row"]
    heap2.close()


# ---------- Record schema tests ----------

def test_record_serialize_roundtrip():
    schema = Schema([
        Column("id", ColType.INT),
        Column("name", ColType.VARCHAR),
    ])
    row = {"id": 42, "name": "Ada Lovelace"}
    data = schema.serialize(row)
    assert schema.deserialize(data) == row


def test_record_with_heap_file(tmp_db_path):
    schema = Schema([Column("id", ColType.INT), Column("email", ColType.VARCHAR)])
    heap = HeapFile(tmp_db_path)
    rid = heap.insert(schema.serialize({"id": 1, "email": "a@b.com"}))
    row = schema.deserialize(heap.get(rid))
    assert row == {"id": 1, "email": "a@b.com"}
    heap.close()
