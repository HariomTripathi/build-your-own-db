"""Shared constants for the storage engine."""

PAGE_SIZE = 4096  # bytes per page, matches typical OS/DB page size

# Page header layout (all little-endian unsigned shorts, 2 bytes each)
#   [0:2]  num_slots        -> how many slot-directory entries exist
#   [2:4]  free_space_start -> offset where the next slot directory entry goes
#   [4:6]  free_space_end   -> offset where the next record's data ends (grows downward)
PAGE_HEADER_SIZE = 6

# Each slot directory entry: [offset: 2 bytes][length: 2 bytes]
# length == 0xFFFF means the slot is a tombstone (deleted record)
SLOT_SIZE = 4
TOMBSTONE = 0xFFFF
