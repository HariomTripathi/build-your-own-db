"""
A heap file is the simplest possible table storage: an unordered
collection of pages, records inserted wherever there's room. No
indexing here -- lookups by anything other than RID require a full
scan. That's exactly the gap Phase 2 (B-Tree index) fills.
"""

from dataclasses import dataclass
from .buffer_pool import BufferPool
from .pager import Pager
from .page import PageFullError


@dataclass(frozen=True)
class RID:
    """Record ID: uniquely locates a record as (page_num, slot_id)."""
    page_num: int
    slot_id: int

    def __str__(self):
        return f"{self.page_num}:{self.slot_id}"


class HeapFile:
    def __init__(self, path: str, buffer_pool_capacity: int = 64):
        self.pager = Pager(path)
        self.buffer_pool = BufferPool(self.pager, capacity=buffer_pool_capacity)
        # Hint for where to look for free space first, avoids rescanning
        # every page from 0 on every insert. Real systems use a proper
        # free-space map; this is the minimal version of that idea.
        self._free_page_hint = 0

    def insert(self, data: bytes) -> RID:
        page_num = self._free_page_hint
        while page_num < self.pager.num_pages:
            page = self.buffer_pool.get_page(page_num)
            try:
                slot_id = page.insert(data)
                self.buffer_pool.mark_dirty(page_num)
                self._free_page_hint = page_num  # this page might still have room
                return RID(page_num, slot_id)
            except PageFullError:
                page_num += 1

        # no existing page had room -- allocate a fresh one
        page_num, page = self.buffer_pool.new_page()
        slot_id = page.insert(data)
        self.buffer_pool.mark_dirty(page_num)
        self._free_page_hint = page_num
        return RID(page_num, slot_id)

    def get(self, rid: RID) -> bytes:
        page = self.buffer_pool.get_page(rid.page_num)
        return page.get(rid.slot_id)

    def delete(self, rid: RID):
        page = self.buffer_pool.get_page(rid.page_num)
        page.delete(rid.slot_id)
        self.buffer_pool.mark_dirty(rid.page_num)
        if rid.page_num < self._free_page_hint:
            self._free_page_hint = rid.page_num

    def scan(self):
        """Yield (RID, record_bytes) for every live record, in page order."""
        for page_num in range(self.pager.num_pages):
            page = self.buffer_pool.get_page(page_num)
            for slot_id, data in page.live_slots():
                yield RID(page_num, slot_id), data

    def close(self):
        self.buffer_pool.close()
