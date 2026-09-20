"""
Buffer pool: caches deserialized Page objects in memory so we don't hit
disk on every read. Uses simple LRU eviction. Dirty pages are flushed to
disk when evicted or on explicit flush_all().

This is intentionally simple (no pinning, no clock/LRU-K) -- real
databases get much fancier here, but this is the right shape to reason
about the tradeoffs.
"""

from collections import OrderedDict
from .constants import PAGE_SIZE
from .page import Page
from .pager import Pager


class BufferPool:
    def __init__(self, pager: Pager, capacity: int = 64):
        self.pager = pager
        self.capacity = capacity
        self._cache: "OrderedDict[int, Page]" = OrderedDict()
        self._dirty: set[int] = set()

    def get_page(self, page_num: int) -> Page:
        if page_num in self._cache:
            self._cache.move_to_end(page_num)  # mark as recently used
            return self._cache[page_num]

        raw = self.pager.read_page(page_num)
        page = Page(raw)
        self._insert(page_num, page)
        return page

    def new_page(self) -> tuple[int, Page]:
        page_num = self.pager.allocate_page()
        page = Page()  # fresh, empty page
        self._insert(page_num, page)
        self.mark_dirty(page_num)
        return page_num, page

    def mark_dirty(self, page_num: int):
        self._dirty.add(page_num)

    def _insert(self, page_num: int, page: Page):
        if len(self._cache) >= self.capacity:
            self._evict_one()
        self._cache[page_num] = page
        self._cache.move_to_end(page_num)

    def _evict_one(self):
        evict_page_num, _ = next(iter(self._cache.items()))  # least recently used
        self._flush_page(evict_page_num)
        del self._cache[evict_page_num]

    def _flush_page(self, page_num: int):
        if page_num in self._dirty:
            self.pager.write_page(page_num, self._cache[page_num].to_bytes())
            self._dirty.discard(page_num)

    def flush_all(self):
        for page_num in list(self._dirty):
            self._flush_page(page_num)

    def close(self):
        self.flush_all()
        self.pager.close()
