"""Disassembler package for WebAssembly modules."""

from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
    format_instruction,
)

__all__ = [
    "disassemble_function",
    "disassemble_module",
    "format_instruction",
]
