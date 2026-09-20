"""
A slotted page: the classic layout real databases (Postgres, SQLite, etc.)
use to store variable-length records on a fixed-size page.

Layout inside a PAGE_SIZE byte buffer:

    +----------+------------------+----------------+------------------+
    | header   | slot directory   |   free space   |   record data    |
    | (6 B)    | (grows forward)  |                | (grows backward) |
    +----------+------------------+----------------+------------------+

Records are appended from the *end* of the page backward; slot-directory
entries are appended from just after the header *forward*. When they meet,
the page is full. Deleting a record just marks its slot as a tombstone
(no compaction here yet -- that's a nice Phase-1.5 exercise).
"""

import struct
from .constants import PAGE_SIZE, PAGE_HEADER_SIZE, SLOT_SIZE, TOMBSTONE

_HEADER_FMT = "<HHH"      # num_slots, free_space_start, free_space_end
_SLOT_FMT = "<HH"         # offset, length


class PageFullError(Exception):
    pass


class Page:
    def __init__(self, raw: bytes = None):
        if raw is None:
            buf = bytearray(PAGE_SIZE)
            self._write_header(buf, num_slots=0,
                                free_space_start=PAGE_HEADER_SIZE,
                                free_space_end=PAGE_SIZE)
            self.buf = buf
        else:
            assert len(raw) == PAGE_SIZE
            self.buf = bytearray(raw)

    # ---------- header helpers ----------

    def _read_header(self):
        return struct.unpack_from(_HEADER_FMT, self.buf, 0)

    def _write_header(self, buf, num_slots, free_space_start, free_space_end):
        struct.pack_into(_HEADER_FMT, buf, 0, num_slots, free_space_start, free_space_end)

    @property
    def num_slots(self):
        return self._read_header()[0]

    # ---------- slot directory helpers ----------

    def _slot_offset(self, slot_id):
        return PAGE_HEADER_SIZE + slot_id * SLOT_SIZE

    def _read_slot(self, slot_id):
        off = self._slot_offset(slot_id)
        return struct.unpack_from(_SLOT_FMT, self.buf, off)  # (record_offset, length)

    def _write_slot(self, slot_id, record_offset, length):
        off = self._slot_offset(slot_id)
        struct.pack_into(_SLOT_FMT, self.buf, off, record_offset, length)

    # ---------- public API ----------

    def free_space(self):
        num_slots, fs_start, fs_end = self._read_header()
        return fs_end - fs_start

    def insert(self, data: bytes) -> int:
        """Insert a record, return its slot_id (used as part of the RID)."""
        num_slots, fs_start, fs_end = self._read_header()
        needed = len(data) + SLOT_SIZE
        if needed > (fs_end - fs_start):
            raise PageFullError(f"page has {fs_end - fs_start} bytes free, need {needed}")

        new_fs_end = fs_end - len(data)
        self.buf[new_fs_end:fs_end] = data

        slot_id = num_slots
        self._write_slot(slot_id, new_fs_end, len(data))

        new_fs_start = fs_start + SLOT_SIZE
        self._write_header(self.buf, num_slots + 1, new_fs_start, new_fs_end)
        return slot_id

    def get(self, slot_id: int) -> bytes:
        if slot_id >= self.num_slots:
            raise IndexError(f"no such slot {slot_id}")
        record_offset, length = self._read_slot(slot_id)
        if length == TOMBSTONE:
            raise KeyError(f"slot {slot_id} was deleted")
        return bytes(self.buf[record_offset:record_offset + length])

    def delete(self, slot_id: int):
        if slot_id >= self.num_slots:
            raise IndexError(f"no such slot {slot_id}")
        record_offset, _length = self._read_slot(slot_id)
        self._write_slot(slot_id, record_offset, TOMBSTONE)

    def live_slots(self):
        """Yield (slot_id, record_bytes) for every non-deleted record."""
        for slot_id in range(self.num_slots):
            record_offset, length = self._read_slot(slot_id)
            if length != TOMBSTONE:
                yield slot_id, bytes(self.buf[record_offset:record_offset + length])

    def to_bytes(self) -> bytes:
        return bytes(self.buf)
