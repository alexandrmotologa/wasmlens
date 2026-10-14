"""Hex dump formatting for linear memory inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class HexdumpLine:
    """Single line of formatted hex dump output."""
    address: int
    hex_left: str
    hex_right: str
    ascii_text: str
    is_zero_line: bool = False

    def to_string(self) -> str:
        return f"{self.address:08X}  {self.hex_left:<23}  {self.hex_right:<23}  |{self.ascii_text}|"


def format_ascii(chunk: bytes) -> str:
    """Format bytes as printable ASCII characters with dots for non-printables."""
    chars = []
    for b in chunk:
        if 32 <= b <= 126:
            chars.append(chr(b))
        else:
            chars.append(".")
    return "".join(chars)


def hexdump_lines(data: bytes, base_address: int = 0, bytes_per_line: int = 16) -> List[HexdumpLine]:
    """Generate structured HexdumpLine objects from byte data."""
    lines: List[HexdumpLine] = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        addr = base_address + i

        # Split into two 8-byte halves
        left_bytes = chunk[:8]
        right_bytes = chunk[8:]

        hex_left = " ".join(f"{b:02X}" for b in left_bytes)
        hex_right = " ".join(f"{b:02X}" for b in right_bytes)
        ascii_text = format_ascii(chunk)
        is_zero = all(b == 0 for b in chunk)

        lines.append(
            HexdumpLine(
                address=addr,
                hex_left=hex_left,
                hex_right=hex_right,
                ascii_text=ascii_text,
                is_zero_line=is_zero,
            )
        )
    return lines


def format_hexdump(data: bytes, base_address: int = 0, bytes_per_line: int = 16, collapse_zeroes: bool = True) -> str:
    """Generate traditional multi-line hex dump text."""
    lines = hexdump_lines(data, base_address, bytes_per_line)
    if not lines:
        return "(empty)"

    output: List[str] = []
    last_was_star = False

    for line in lines:
        if collapse_zeroes and line.is_zero_line:
            if not last_was_star:
                output.append("*")
                last_was_star = True
            continue
        last_was_star = False
        output.append(line.to_string())

    return "\n".join(output)
