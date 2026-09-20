"""
The Pager is the only part of the system allowed to talk to the OS file
directly. Everything above it (buffer pool, heap file) thinks in terms of
page numbers, not byte offsets.
"""

import os
from .constants import PAGE_SIZE


class Pager:
    def __init__(self, path: str):
        self.path = path
        file_exists = os.path.exists(path)
        # 'r+b' requires the file to exist; create it first if needed.
        if not file_exists:
            open(path, "wb").close()
        self.fd = open(path, "r+b")
        self.file_size = os.path.getsize(path)
        self.num_pages = self.file_size // PAGE_SIZE

    def read_page(self, page_num: int) -> bytes:
        if page_num >= self.num_pages:
            raise IndexError(f"page {page_num} does not exist (num_pages={self.num_pages})")
        self.fd.seek(page_num * PAGE_SIZE)
        data = self.fd.read(PAGE_SIZE)
        assert len(data) == PAGE_SIZE, "short read -- corrupt file?"
        return data

    def write_page(self, page_num: int, data: bytes):
        assert len(data) == PAGE_SIZE
        self.fd.seek(page_num * PAGE_SIZE)
        self.fd.write(data)
        self.fd.flush()
        os.fsync(self.fd.fileno())  # durability: force the OS to actually write it

    def allocate_page(self) -> int:
        """Extend the file by one page, return its page number."""
        page_num = self.num_pages
        self.fd.seek(page_num * PAGE_SIZE)
        self.fd.write(bytes(PAGE_SIZE))
        self.fd.flush()
        self.num_pages += 1
        self.file_size += PAGE_SIZE
        return page_num

    def close(self):
        self.fd.close()
