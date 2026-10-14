"""WebAssembly binary parser module."""

from wasmlens.parser.types import (
    WasmModule,
    SectionId,
    ValueType,
    FunctionType,
    Limits,
    TableType,
    MemoryType,
    GlobalType,
    ImportEntry,
    ExportEntry,
    Instruction,
    FunctionBody,
)
from wasmlens.parser.leb128 import decode_u32, decode_u64, decode_i32, decode_i64
from wasmlens.parser.reader import BinaryReader
from wasmlens.parser.module import parse_wasm

__all__ = [
    "WasmModule",
    "SectionId",
    "ValueType",
    "FunctionType",
    "Limits",
    "TableType",
    "MemoryType",
    "GlobalType",
    "ImportEntry",
    "ExportEntry",
    "Instruction",
    "FunctionBody",
    "decode_u32",
    "decode_u64",
    "decode_i32",
    "decode_i64",
    "BinaryReader",
    "parse_wasm",
]
