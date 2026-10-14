"""Linear memory search utilities."""

from __future__ import annotations

import struct
from typing import List


def find_bytes(buffer: bytearray | bytes, pattern: bytes) -> List[int]:
    """Find all starting byte offsets of pattern in buffer."""
    if not pattern:
        return []
    matches = []
    start = 0
    while True:
        pos = buffer.find(pattern, start)
        if pos == -1:
            break
        matches.append(pos)
        start = pos + 1
    return matches


def find_string(buffer: bytearray | bytes, query: str, encoding: str = "utf-8") -> List[int]:
    """Find all starting byte offsets of a string query."""
    pattern = query.encode(encoding)
    return find_bytes(buffer, pattern)


def find_i32(buffer: bytearray | bytes, value: int) -> List[int]:
    """Find all 4-byte aligned and unaligned offsets of 32-bit integer."""
    pattern = struct.pack("<i", value)
    return find_bytes(buffer, pattern)


def find_i64(buffer: bytearray | bytes, value: int) -> List[int]:
    """Find all 8-byte offsets of 64-bit integer."""
    pattern = struct.pack("<q", value)
    return find_bytes(buffer, pattern)
