"""Authentic LEB128 (Little-Endian Base 128) encoder and decoder for WebAssembly 2.0.

Adheres strictly to the WebAssembly specification:
- Unsigned LEB128 (u32, u64)
- Signed LEB128 (i32, i64)
- Length validation (max 5 bytes for 32-bit, max 10 bytes for 64-bit)
- Unused bit checking to prevent canonical representation attacks
"""

from typing import Tuple


class LEB128Error(ValueError):
    """Raised when LEB128 decoding fails."""
    pass


def decode_u32(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decode an unsigned 32-bit LEB128 integer from data starting at offset.

    Returns:
        (value, bytes_read)
    """
    result = 0
    shift = 0
    bytes_read = 0
    max_bytes = 5

    while True:
        if offset + bytes_read >= len(data):
            raise LEB128Error(f"Unexpected EOF while decoding u32 at offset {offset + bytes_read}")

        byte = data[offset + bytes_read]
        bytes_read += 1

        if bytes_read == max_bytes:
            # 5th byte: only the lowest 4 bits are valid for u32 (32 - 4 * 7 = 4)
            if (byte & 0x80) != 0:
                raise LEB128Error("u32 LEB128 sequence exceeds 5 bytes")
            if (byte & 0x70) != 0:
                raise LEB128Error("u32 LEB128 contains non-zero padding bits in 5th byte")

        result |= (byte & 0x7F) << shift

        if (byte & 0x80) == 0:
            break

        shift += 7

    return result, bytes_read


def decode_u64(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decode an unsigned 64-bit LEB128 integer from data starting at offset.

    Returns:
        (value, bytes_read)
    """
    result = 0
    shift = 0
    bytes_read = 0
    max_bytes = 10

    while True:
        if offset + bytes_read >= len(data):
            raise LEB128Error(f"Unexpected EOF while decoding u64 at offset {offset + bytes_read}")

        byte = data[offset + bytes_read]
        bytes_read += 1

        if bytes_read == max_bytes:
            # 10th byte: only lowest 1 bit is valid for u64 (64 - 9 * 7 = 1)
            if (byte & 0x80) != 0:
                raise LEB128Error("u64 LEB128 sequence exceeds 10 bytes")
            if (byte & 0x7E) != 0:
                raise LEB128Error("u64 LEB128 contains non-zero padding bits in 10th byte")

        result |= (byte & 0x7F) << shift

        if (byte & 0x80) == 0:
            break

        shift += 7

    return result, bytes_read


def decode_i32(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decode a signed 32-bit LEB128 integer from data starting at offset.

    Returns:
        (value, bytes_read)
    """
    result = 0
    shift = 0
    bytes_read = 0
    max_bytes = 5

    while True:
        if offset + bytes_read >= len(data):
            raise LEB128Error(f"Unexpected EOF while decoding i32 at offset {offset + bytes_read}")

        byte = data[offset + bytes_read]
        bytes_read += 1

        result |= (byte & 0x7F) << shift

        if bytes_read == max_bytes:
            if (byte & 0x80) != 0:
                raise LEB128Error("i32 LEB128 sequence exceeds 5 bytes")
            # Sign bit is bit 3 of the 5th byte (32 - 4 * 7 - 1 = 3)
            sign_bit = (byte & 0x08) != 0
            pad = (byte & 0x70) >> 4
            if sign_bit and pad != 0x07:
                raise LEB128Error("i32 LEB128 invalid sign extension in 5th byte")
            if not sign_bit and pad != 0x00:
                raise LEB128Error("i32 LEB128 invalid padding in 5th byte")

        shift += 7

        if (byte & 0x80) == 0:
            if (byte & 0x40) != 0 and shift < 32:
                result |= -(1 << shift)
            break

    # Normalize to 32-bit signed integer
    result = result & 0xFFFFFFFF
    if result & 0x80000000:
        result -= 0x100000000

    return result, bytes_read


def decode_i64(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decode a signed 64-bit LEB128 integer from data starting at offset.

    Returns:
        (value, bytes_read)
    """
    result = 0
    shift = 0
    bytes_read = 0
    max_bytes = 10

    while True:
        if offset + bytes_read >= len(data):
            raise LEB128Error(f"Unexpected EOF while decoding i64 at offset {offset + bytes_read}")

        byte = data[offset + bytes_read]
        bytes_read += 1

        result |= (byte & 0x7F) << shift

        if bytes_read == max_bytes:
            if (byte & 0x80) != 0:
                raise LEB128Error("i64 LEB128 sequence exceeds 10 bytes")
            # Sign bit is bit 0 of 10th byte (64 - 9 * 7 - 1 = 0)
            sign_bit = (byte & 0x01) != 0
            pad = (byte & 0x7E) >> 1
            if sign_bit and pad != 0x3F:
                raise LEB128Error("i64 LEB128 invalid sign extension in 10th byte")
            if not sign_bit and pad != 0x00:
                raise LEB128Error("i64 LEB128 invalid padding in 10th byte")

        shift += 7

        if (byte & 0x80) == 0:
            if (byte & 0x40) != 0 and shift < 64:
                result |= -(1 << shift)
            break

    # Normalize to 64-bit signed integer
    result = result & 0xFFFFFFFFFFFFFFFF
    if result & 0x8000000000000000:
        result -= 0x10000000000000000

    return result, bytes_read


def encode_u32(val: int) -> bytes:
    """Encode an unsigned 32-bit integer into LEB128 bytes."""
    if val < 0 or val > 0xFFFFFFFF:
        raise ValueError(f"Value out of range for u32: {val}")
    res = bytearray()
    while True:
        byte = val & 0x7F
        val >>= 7
        if val != 0:
            byte |= 0x80
        res.append(byte)
        if val == 0:
            break
    return bytes(res)


def encode_i32(val: int) -> bytes:
    """Encode a signed 32-bit integer into LEB128 bytes."""
    if val < -0x80000000 or val > 0x7FFFFFFF:
        raise ValueError(f"Value out of range for i32: {val}")
    res = bytearray()
    more = True
    while more:
        byte = val & 0x7F
        val >>= 7
        sign_bit = (byte & 0x40) != 0
        if (val == 0 and not sign_bit) or (val == -1 and sign_bit):
            more = False
        else:
            byte |= 0x80
        res.append(byte)
    return bytes(res)


def encode_i64(val: int) -> bytes:
    """Encode a signed 64-bit integer into LEB128 bytes."""
    if val < -0x8000000000000000 or val > 0x7FFFFFFFFFFFFFFF:
        raise ValueError(f"Value out of range for i64: {val}")
    res = bytearray()
    more = True
    while more:
        byte = val & 0x7F
        val >>= 7
        sign_bit = (byte & 0x40) != 0
        if (val == 0 and not sign_bit) or (val == -1 and sign_bit):
            more = False
        else:
            byte |= 0x80
        res.append(byte)
    return bytes(res)
