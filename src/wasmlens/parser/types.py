"""WebAssembly 2.0 type definitions and module schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


class SectionId(IntEnum):
    """Standard WebAssembly section identifiers."""
    CUSTOM = 0
    TYPE = 1
    IMPORT = 2
    FUNCTION = 3
    TABLE = 4
    MEMORY = 5
    GLOBAL = 6
    EXPORT = 7
    START = 8
    ELEMENT = 9
    CODE = 10
    DATA = 11
    DATA_COUNT = 12


class ValueType(IntEnum):
    """WebAssembly 2.0 value types encoded as negative 7-bit ints."""
    I32 = 0x7F
    I64 = 0x7E
    F32 = 0x7D
    F64 = 0x7C
    V128 = 0x7B
    FUNCREF = 0x70
    EXTERNREF = 0x6F
    EMPTY_BLOCK = 0x40

    @classmethod
    def from_byte(cls, b: int) -> ValueType:
        try:
            return cls(b)
        except ValueError:
            raise ValueError(f"Unknown Wasm value type byte: 0x{b:02X}")

    def to_wat(self) -> str:
        mapping = {
            ValueType.I32: "i32",
            ValueType.I64: "i64",
            ValueType.F32: "f32",
            ValueType.F64: "f64",
            ValueType.V128: "v128",
            ValueType.FUNCREF: "funcref",
            ValueType.EXTERNREF: "externref",
            ValueType.EMPTY_BLOCK: "nil",
        }
        return mapping.get(self, f"unknown_0x{self.value:02X}")


class ExternalKind(IntEnum):
    """Import/Export external entity kind."""
    FUNCTION = 0
    TABLE = 1
    MEMORY = 2
    GLOBAL = 3


@dataclass
class Limits:
    """Resizable limits for memories and tables (min, max)."""
    min: int
    max: Optional[int] = None
    is_shared: bool = False
    is_64bit: bool = False

    def to_wat(self) -> str:
        if self.max is not None:
            return f"{self.min} {self.max}"
        return f"{self.min}"


@dataclass
class FunctionType:
    """WebAssembly function signature (parameters -> results)."""
    params: List[ValueType] = field(default_factory=list)
    results: List[ValueType] = field(default_factory=list)

    def to_wat(self) -> str:
        p_str = " ".join(p.to_wat() for p in self.params)
        r_str = " ".join(r.to_wat() for r in self.results)
        parts = []
        if p_str:
            parts.append(f"(param {p_str})")
        if r_str:
            parts.append(f"(result {r_str})")
        return " ".join(parts)


@dataclass
class TableType:
    """Table definition with element type and limits."""
    element_type: ValueType
    limits: Limits


@dataclass
class MemoryType:
    """Linear memory definition with 64KB page limits."""
    limits: Limits


@dataclass
class GlobalType:
    """Global variable specification with value type and mutability."""
    valtype: ValueType
    mutable: bool


@dataclass
class Instruction:
    """Decoded WebAssembly bytecode instruction."""
    opcode: int
    mnemonic: str
    operands: Any = None
    offset: int = 0
    size: int = 1
    prefix: Optional[int] = None

    def to_wat(self) -> str:
        if self.operands is None:
            return self.mnemonic
        if isinstance(self.operands, (list, tuple)):
            ops_str = " ".join(str(op) for op in self.operands)
            return f"{self.mnemonic} {ops_str}".strip()
        return f"{self.mnemonic} {self.operands}"


@dataclass
class ImportEntry:
    """Imported entity descriptor."""
    module: str
    name: str
    kind: ExternalKind
    desc: Any  # func type_idx (int), TableType, MemoryType, GlobalType


@dataclass
class ExportEntry:
    """Exported entity descriptor."""
    name: str
    kind: ExternalKind
    index: int


@dataclass
class GlobalEntry:
    """Global variable definition with init expression."""
    type: GlobalType
    init_expr: List[Instruction]


@dataclass
class ElementSegment:
    """Element segment for populating tables."""
    index: int
    table_index: int
    offset_expr: Optional[List[Instruction]]
    init_indices: List[int]
    is_passive: bool = False
    is_declarative: bool = False


@dataclass
class DataSegment:
    """Linear memory data segment."""
    index: int
    memory_index: int
    offset_expr: Optional[List[Instruction]]
    data: bytes
    is_passive: bool = False


@dataclass
class LocalEntry:
    """Count of local variables sharing a specific value type."""
    count: int
    valtype: ValueType


@dataclass
class FunctionBody:
    """Function code body: locals and instruction stream."""
    func_index: int
    type_index: int
    locals: List[LocalEntry] = field(default_factory=list)
    instructions: List[Instruction] = field(default_factory=list)
    offset: int = 0
    size: int = 0
    raw_bytes: bytes = b""

    @property
    def total_locals_count(self) -> int:
        return sum(loc.count for loc in self.locals)

    def get_all_local_types(self) -> List[ValueType]:
        types: List[ValueType] = []
        for loc in self.locals:
            types.extend([loc.valtype] * loc.count)
        return types


@dataclass
class CustomSection:
    """Custom section representation."""
    name: str
    data: bytes
    offset: int = 0


@dataclass
class SectionInfo:
    """Header and metadata for a binary section."""
    id: SectionId
    size: int
    offset: int
    payload_offset: int
    name: Optional[str] = None


@dataclass
class WasmModule:
    """Fully parsed WebAssembly 2.0 module."""
    magic: bytes = b"\x00asm"
    version: int = 1
    types: List[FunctionType] = field(default_factory=list)
    imports: List[ImportEntry] = field(default_factory=list)
    functions: List[int] = field(default_factory=list)  # type index per internal func
    tables: List[TableType] = field(default_factory=list)
    memories: List[MemoryType] = field(default_factory=list)
    globals: List[GlobalEntry] = field(default_factory=list)
    exports: List[ExportEntry] = field(default_factory=list)
    start_func: Optional[int] = None
    elements: List[ElementSegment] = field(default_factory=list)
    codes: List[FunctionBody] = field(default_factory=list)
    datas: List[DataSegment] = field(default_factory=list)
    data_count: Optional[int] = None
    custom_sections: List[CustomSection] = field(default_factory=list)
    sections: List[SectionInfo] = field(default_factory=list)
    
    # Metadata extracted from name section or auto-generated
    function_names: Dict[int, str] = field(default_factory=dict)
    local_names: Dict[int, Dict[int, str]] = field(default_factory=dict)
    source_file: Optional[str] = None

    @property
    def imported_func_count(self) -> int:
        return sum(1 for imp in self.imports if imp.kind == ExternalKind.FUNCTION)

    @property
    def total_func_count(self) -> int:
        return self.imported_func_count + len(self.functions)

    def get_function_type_index(self, func_idx: int) -> int:
        imported_funcs = [imp for imp in self.imports if imp.kind == ExternalKind.FUNCTION]
        if func_idx < len(imported_funcs):
            return int(imported_funcs[func_idx].desc)
        internal_idx = func_idx - len(imported_funcs)
        if 0 <= internal_idx < len(self.functions):
            return self.functions[internal_idx]
        raise IndexError(f"Function index {func_idx} out of bounds")

    def get_function_type(self, func_idx: int) -> FunctionType:
        type_idx = self.get_function_type_index(func_idx)
        return self.types[type_idx]

    def get_function_name(self, func_idx: int) -> str:
        if func_idx in self.function_names:
            return self.function_names[func_idx]
        for exp in self.exports:
            if exp.kind == ExternalKind.FUNCTION and exp.index == func_idx:
                return exp.name
        return f"func_{func_idx}"
