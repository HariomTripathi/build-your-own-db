"""
Turns Python dicts/tuples into fixed layout bytes (and back), based on a
declared Schema. Two column types for now:

    INT      -> 8-byte signed little-endian integer
    VARCHAR  -> 2-byte length prefix + UTF-8 bytes

This is deliberately simple -- no NULLs, no fixed-width strings. Good
Phase-1.5 exercises: add NULL bitmaps, add FLOAT, add fixed-width CHAR(n).
"""

import struct
from dataclasses import dataclass
from enum import Enum


class ColType(Enum):
    INT = "INT"
    VARCHAR = "VARCHAR"


@dataclass
class Column:
    name: str
    type: ColType


class Schema:
    def __init__(self, columns: list[Column]):
        self.columns = columns

    def column_names(self):
        return [c.name for c in self.columns]

    def serialize(self, row: dict) -> bytes:
        out = bytearray()
        for col in self.columns:
            value = row[col.name]
            if col.type == ColType.INT:
                out += struct.pack("<q", int(value))
            elif col.type == ColType.VARCHAR:
                raw = str(value).encode("utf-8")
                if len(raw) > 0xFFFF:
                    raise ValueError(f"VARCHAR value too long: {len(raw)} bytes")
                out += struct.pack("<H", len(raw))
                out += raw
            else:
                raise ValueError(f"unknown column type {col.type}")
        return bytes(out)

    def deserialize(self, data: bytes) -> dict:
        row = {}
        pos = 0
        for col in self.columns:
            if col.type == ColType.INT:
                (value,) = struct.unpack_from("<q", data, pos)
                pos += 8
            elif col.type == ColType.VARCHAR:
                (length,) = struct.unpack_from("<H", data, pos)
                pos += 2
                value = data[pos:pos + length].decode("utf-8")
                pos += length
            else:
                raise ValueError(f"unknown column type {col.type}")
            row[col.name] = value
        return row
