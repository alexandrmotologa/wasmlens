"""Binary stream reader for WebAssembly binary format."""

from __future__ import annotations

import struct
from typing import Callable, List, Optional, TypeVar

from wasmlens.parser.leb128 import (
    decode_u32,
    decode_u64,
    decode_i32,
    decode_i64,
    LEB128Error,
)
from wasmlens.parser.types import Limits, ValueType

T = TypeVar("T")


class BinaryReaderError(ValueError):
    """Raised when binary reading fails."""
    pass


class BinaryReader:
    """Cursor-based reader over a byte sequence."""

    def __init__(self, data: bytes, base_offset: int = 0) -> None:
        self.data = data
        self.cursor = 0
        self.base_offset = base_offset

    @property
    def remaining(self) -> int:
        return len(self.data) - self.cursor

    @property
    def has_more(self) -> bool:
        return self.cursor < len(self.data)

    @property
    def current_offset(self) -> int:
        """Absolute offset in original stream."""
        return self.base_offset + self.cursor

    def tell(self) -> int:
        return self.cursor

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self.data):
            raise BinaryReaderError(f"Seek position {pos} out of range (0..{len(self.data)})")
        self.cursor = pos

    def peek_byte(self) -> int:
        if not self.has_more:
            raise BinaryReaderError(f"Unexpected EOF at offset {self.current_offset}")
        return self.data[self.cursor]

    def read_byte(self) -> int:
        if not self.has_more:
            raise BinaryReaderError(f"Unexpected EOF at offset {self.current_offset}")
        b = self.data[self.cursor]
        self.cursor += 1
        return b

    def read_bytes(self, n: int) -> bytes:
        if n < 0:
            raise BinaryReaderError(f"Negative byte count requested: {n}")
        if self.cursor + n > len(self.data):
            raise BinaryReaderError(
                f"Unexpected EOF: requested {n} bytes at offset {self.current_offset}, but only {self.remaining} available"
            )
        chunk = self.data[self.cursor : self.cursor + n]
        self.cursor += n
        return chunk

    def read_u32(self) -> int:
        try:
            val, n = decode_u32(self.data, self.cursor)
            self.cursor += n
            return val
        except LEB128Error as e:
            raise BinaryReaderError(f"Failed to read u32 at offset {self.current_offset}: {e}")

    def read_u64(self) -> int:
        try:
            val, n = decode_u64(self.data, self.cursor)
            self.cursor += n
            return val
        except LEB128Error as e:
            raise BinaryReaderError(f"Failed to read u64 at offset {self.current_offset}: {e}")

    def read_i32(self) -> int:
        try:
            val, n = decode_i32(self.data, self.cursor)
            self.cursor += n
            return val
        except LEB128Error as e:
            raise BinaryReaderError(f"Failed to read i32 at offset {self.current_offset}: {e}")

    def read_i64(self) -> int:
        try:
            val, n = decode_i64(self.data, self.cursor)
            self.cursor += n
            return val
        except LEB128Error as e:
            raise BinaryReaderError(f"Failed to read i64 at offset {self.current_offset}: {e}")

    def read_f32(self) -> float:
        raw = self.read_bytes(4)
        return struct.unpack("<f", raw)[0]

    def read_f64(self) -> float:
        raw = self.read_bytes(8)
        return struct.unpack("<d", raw)[0]

    def read_name(self) -> str:
        """Read a UTF-8 string prefixed with byte length (u32)."""
        length = self.read_u32()
        raw = self.read_bytes(length)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise BinaryReaderError(f"Invalid UTF-8 string at offset {self.current_offset - length}: {e}")

    def read_vec(self, item_reader: Callable[[], T]) -> List[T]:
        """Read a vector of items prefixed with item count (u32)."""
        count = self.read_u32()
        items: List[T] = []
        for _ in range(count):
            items.append(item_reader())
        return items

    def read_valtype(self) -> ValueType:
        b = self.read_byte()
        try:
            return ValueType.from_byte(b)
        except ValueError as e:
            raise BinaryReaderError(f"Invalid valtype byte 0x{b:02X} at offset {self.current_offset - 1}: {e}")

    def read_limits(self) -> Limits:
        flags = self.read_byte()
        min_val = self.read_u32()
        max_val: Optional[int] = None
        is_shared = (flags & 0x02) != 0
        is_64bit = (flags & 0x04) != 0

        if (flags & 0x01) != 0:
            max_val = self.read_u32()

        return Limits(min=min_val, max=max_val, is_shared=is_shared, is_64bit=is_64bit)

    def sub_reader(self, length: int) -> BinaryReader:
        """Create a bounded reader of length bytes, advancing current cursor."""
        chunk = self.read_bytes(length)
        return BinaryReader(chunk, base_offset=self.current_offset - length)
