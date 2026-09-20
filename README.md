# pydb — Phase 1: Storage Engine

A from-scratch database storage engine, built as a learning project. This
covers Phase 1 of a full DBMS build: durable, page-based storage for
variable-length records. Indexing, a query layer, and transactions come
in later phases.

## Architecture

```
Your code
   │
   ▼
HeapFile        <- insert(bytes) -> RID, get(RID), delete(RID), scan()
   │                unordered collection of records across many pages
   ▼
BufferPool      <- caches Page objects in memory, LRU eviction,
   │                only writes dirty pages back to disk
   ▼
Pager           <- the only thing that touches the OS file directly;
   │                translates page_num <-> byte offset
   ▼
Disk file (.db)    fixed 4096-byte pages
```

Records are serialized/deserialized by `Schema` (`pydb/storage/record.py`),
which is a separate concern from storage — the heap file only ever sees
raw bytes, and doesn't know or care what's inside them. That separation
matters: it's what lets you swap in a smarter storage layout later
without touching anything above it.

### Page layout (`pydb/storage/page.py`)

Each 4KB page uses a **slotted page** layout — the same idea Postgres and
SQLite use:

```
+--------+------------------+----------------+------------------+
| header | slot directory   |  free space    |   record data    |
| 6 B    | grows forward -> |                | <- grows backward|
+--------+------------------+----------------+------------------+
```

The slot directory holds `(offset, length)` pairs pointing at record
bytes stored from the *end* of the page. This indirection is what lets a
record's slot ID stay stable even if the record itself is deleted or the
page gets compacted later — a `RID` (`page_num, slot_id`) is a durable
handle to a row.

### Durability

`Pager.write_page` calls `fsync` after every write, so once
`HeapFile.close()` (or a buffer pool flush) returns, that data survives
a crash. This is the cheap, non-performant version of durability — real
systems use a write-ahead log so they don't have to fsync full pages on
every write. That's exactly what Phase 4 (transactions) adds.

## Try it

```bash
python demo.py          # end-to-end walkthrough with output
python -m pytest tests/ -v
```

## Phase 2: B+Tree index (`pydb/index/btree.py`, `pydb/table.py`)

`HeapFile.scan()` alone means finding one row costs O(n) — checking
every row, every time. `BPlusTree` fixes that: it maps a key (e.g. an
`id`) straight to a `RID` in O(log n), and `HeapFile.get(rid)` then
fetches the actual bytes directly, without touching any other page.

```
Table
   │
   ├── BPlusTree     key -> RID          (in-memory, O(log n) lookup)
   └── HeapFile       RID -> row bytes    (on-disk, from Phase 1)
```

Why a B+Tree specifically, not a plain binary tree: a BST branches 2
ways per node, so a million keys means ~20 levels deep. A B+Tree
branches many ways per node (the `order`), so the same million keys
might be only 3-4 levels deep — far fewer node hops per lookup. Only
leaf nodes hold real data; internal nodes are pure routing. Leaves are
linked (`leaf.next`), which is what makes range queries
(`range_by_key(10, 50)`) cheap — find the start once, then walk the
chain.

**This index is in-memory only.** `Table` rebuilds it with one full
scan whenever a file is opened (`_rebuild_index`). Persisting the
tree's own nodes as pages on disk (so it survives without a rebuild)
is a great next exercise once this version feels solid.

`benchmark.py` measures the payoff directly — scan-based lookup grows
linearly with table size; indexed lookup stays roughly flat. Run it to
see the gap widen as the table grows.

## What's deliberately left out (future phases)

- **No compaction** — deleted heap records leave holes; pages never
  reclaim tombstoned space. A good Phase 1.5 exercise.
- **No on-disk index** — the B+Tree lives in memory and is rebuilt on
  open. Persisting it as pages is a natural Phase 2.5.
- **No B+Tree rebalancing on delete** — `BPlusTree.delete()` removes
  the key but doesn't merge/redistribute underfull nodes.
- **No WAL / crash recovery** — durability today is "fsync on every
  write," which is correct but slow. Phase 4 replaces this.
- **No concurrency control** — single-writer, single-reader only.

## Suggested next steps

1. **Phase 2.5 (optional but valuable):** persist the B+Tree's nodes as
   pages so it doesn't need rebuilding via a full scan on every open.
2. **Phase 3:** a small SQL subset parser (`SELECT`, `WHERE`, `INSERT`)
   that compiles down to calls against `Table`.
3. **Phase 4:** write-ahead log + transactions, replacing the
   fsync-every-write durability model.
