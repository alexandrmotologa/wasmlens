"""Unit tests for LEB128 encoding and decoding."""

import pytest
from wasmlens.parser.leb128 import (
    decode_u32,
    decode_u64,
    decode_i32,
    decode_i64,
    encode_u32,
    encode_i32,
    encode_i64,
    LEB128Error,
)


def test_decode_u32_basic():
    assert decode_u32(bytes([0x00])) == (0, 1)
    assert decode_u32(bytes([0x01])) == (1, 1)
    assert decode_u32(bytes([0x7F])) == (127, 1)
    assert decode_u32(bytes([0x80, 0x01])) == (128, 2)
    assert decode_u32(bytes([0xE5, 0x8E, 0x26])) == (624485, 3)
    assert decode_u32(bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x0F])) == (0xFFFFFFFF, 5)


def test_decode_u32_errors():
    with pytest.raises(LEB128Error):
        decode_u32(b"")
    with pytest.raises(LEB128Error):
        decode_u32(bytes([0x80]))  # Unexpected EOF
    with pytest.raises(LEB128Error):
        # 6 bytes sequence
        decode_u32(bytes([0x80, 0x80, 0x80, 0x80, 0x80, 0x01]))


def test_decode_i32_basic():
    assert decode_i32(bytes([0x00])) == (0, 1)
    assert decode_i32(bytes([0x01])) == (1, 1)
    assert decode_i32(bytes([0x7F])) == (-1, 1)
    assert decode_i32(bytes([0x3F])) == (63, 1)
    assert decode_i32(bytes([0x40])) == (-64, 1)
    assert decode_i32(bytes([0xC0, 0x00])) == (64, 2)
    assert decode_i32(bytes([0x9B, 0xF1, 0x59])) == (-624485, 3)


def test_encode_and_decode_roundtrip():
    test_values_u32 = [0, 1, 63, 64, 127, 128, 255, 256, 16383, 16384, 624485, 0xFFFFFFFF]
    for val in test_values_u32:
        encoded = encode_u32(val)
        decoded, count = decode_u32(encoded)
        assert decoded == val
        assert count == len(encoded)

    test_values_i32 = [
        0, 1, -1, 63, -63, 64, -64, 127, -127, 128, -128,
        624485, -624485, 2147483647, -2147483648
    ]
    for val in test_values_i32:
        encoded = encode_i32(val)
        decoded, count = decode_i32(encoded)
        assert decoded == val
        assert count == len(encoded)


def test_decode_u64_basic():
    assert decode_u64(bytes([0x00])) == (0, 1)
    assert decode_u64(bytes([0x80, 0x01])) == (128, 2)
    val = 0x123456789ABCDEF0
    # encode manually or via roundtrip
    # test roundtrip for 64-bit
    test_values_i64 = [
        0, 1, -1, 128, -128, 0x7FFFFFFFFFFFFFFF, -0x8000000000000000, 123456789012345
    ]
    for v in test_values_i64:
        enc = encode_i64(v)
        dec, count = decode_i64(enc)
        assert dec == v
        assert count == len(enc)
