"""WebAssembly 2.0 section parser for all standard and custom sections."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from wasmlens.parser.opcodes import ImmediateType, lookup_opcode
from wasmlens.parser.reader import BinaryReader, BinaryReaderError
from wasmlens.parser.types import (
    CustomSection,
    DataSegment,
    ElementSegment,
    ExportEntry,
    ExternalKind,
    FunctionBody,
    FunctionType,
    GlobalEntry,
    GlobalType,
    ImportEntry,
    Instruction,
    Limits,
    LocalEntry,
    MemoryType,
    SectionId,
    SectionInfo,
    TableType,
    ValueType,
    WasmModule,
)


def read_instruction(reader: BinaryReader) -> Instruction:
    """Decode a single instruction from the reader stream."""
    start_offset = reader.current_offset
    op_byte = reader.read_byte()
    prefix: Optional[int] = None

    if op_byte == 0xFC:
        prefix = 0xFC
        sub_op = reader.read_u32()
        info = lookup_opcode(0xFC, sub_op)
    else:
        info = lookup_opcode(op_byte)

    operands: Any = None
    imm_type = info.immediate_type

    if imm_type == ImmediateType.NONE:
        operands = None
    elif imm_type == ImmediateType.BLOCK_TYPE:
        peek = reader.peek_byte()
        if peek == 0x40:
            reader.read_byte()
            operands = ValueType.EMPTY_BLOCK
        elif peek in (0x7F, 0x7E, 0x7D, 0x7C, 0x7B, 0x70, 0x6F):
            operands = reader.read_valtype()
        else:
            # Type index as signed LEB128 (non-negative)
            operands = reader.read_i32()
    elif imm_type in (
        ImmediateType.LABEL_IDX,
        ImmediateType.FUNC_IDX,
        ImmediateType.LOCAL_IDX,
        ImmediateType.GLOBAL_IDX,
        ImmediateType.TABLE_IDX,
        ImmediateType.TYPE_IDX,
        ImmediateType.ELEM_IDX,
        ImmediateType.DATA_IDX,
    ):
        operands = reader.read_u32()
    elif imm_type == ImmediateType.LABEL_TABLE:
        targets = reader.read_vec(reader.read_u32)
        default_target = reader.read_u32()
        operands = (targets, default_target)
    elif imm_type == ImmediateType.CALL_INDIRECT:
        type_idx = reader.read_u32()
        table_idx = reader.read_u32()
        operands = (type_idx, table_idx)
    elif imm_type == ImmediateType.MEM_ARG:
        align = reader.read_u32()
        offset = reader.read_u32()
        operands = (align, offset)
    elif imm_type == ImmediateType.MEM_IDX:
        operands = reader.read_byte()
    elif imm_type == ImmediateType.I32_CONST:
        operands = reader.read_i32()
    elif imm_type == ImmediateType.I64_CONST:
        operands = reader.read_i64()
    elif imm_type == ImmediateType.F32_CONST:
        operands = reader.read_f32()
    elif imm_type == ImmediateType.F64_CONST:
        operands = reader.read_f64()
    elif imm_type == ImmediateType.VALTYPE:
        operands = reader.read_valtype()
    elif imm_type == ImmediateType.SELECT_TYPES:
        operands = reader.read_vec(reader.read_valtype)
    elif imm_type == ImmediateType.MEMORY_INIT:
        data_idx = reader.read_u32()
        mem_idx = reader.read_byte()
        operands = (data_idx, mem_idx)
    elif imm_type == ImmediateType.MEMORY_COPY:
        dst_mem = reader.read_byte()
        src_mem = reader.read_byte()
        operands = (dst_mem, src_mem)
    elif imm_type == ImmediateType.MEMORY_FILL:
        operands = reader.read_byte()
    elif imm_type == ImmediateType.TABLE_INIT:
        elem_idx = reader.read_u32()
        table_idx = reader.read_u32()
        operands = (elem_idx, table_idx)
    elif imm_type == ImmediateType.TABLE_COPY:
        dst_tbl = reader.read_u32()
        src_tbl = reader.read_u32()
        operands = (dst_tbl, src_tbl)

    size = reader.current_offset - start_offset
    return Instruction(
        opcode=op_byte,
        mnemonic=info.mnemonic,
        operands=operands,
        offset=start_offset,
        size=size,
        prefix=prefix,
    )


def read_expr(reader: BinaryReader) -> List[Instruction]:
    """Read an expression ending with opcode 0x0B (end)."""
    instructions: List[Instruction] = []
    depth = 0
    while reader.has_more:
        instr = read_instruction(reader)
        instructions.append(instr)
        if instr.opcode in (0x02, 0x03, 0x04):  # block, loop, if
            depth += 1
        elif instr.opcode == 0x0B:  # end
            if depth == 0:
                break
            depth -= 1
    return instructions


def parse_type_section(reader: BinaryReader) -> List[FunctionType]:
    """Parse Section 1: Type section."""
    count = reader.read_u32()
    types: List[FunctionType] = []
    for _ in range(count):
        form = reader.read_byte()
        if form != 0x60:
            raise BinaryReaderError(f"Expected function type form 0x60, got 0x{form:02X}")
        params = reader.read_vec(reader.read_valtype)
        results = reader.read_vec(reader.read_valtype)
        types.append(FunctionType(params=params, results=results))
    return types


def parse_import_section(reader: BinaryReader) -> List[ImportEntry]:
    """Parse Section 2: Import section."""
    count = reader.read_u32()
    imports: List[ImportEntry] = []
    for _ in range(count):
        mod_name = reader.read_name()
        field_name = reader.read_name()
        kind_byte = reader.read_byte()
        try:
            kind = ExternalKind(kind_byte)
        except ValueError:
            raise BinaryReaderError(f"Unknown import kind byte 0x{kind_byte:02X}")

        desc: Any = None
        if kind == ExternalKind.FUNCTION:
            desc = reader.read_u32()
        elif kind == ExternalKind.TABLE:
            elem_type = reader.read_valtype()
            limits = reader.read_limits()
            desc = TableType(element_type=elem_type, limits=limits)
        elif kind == ExternalKind.MEMORY:
            limits = reader.read_limits()
            desc = MemoryType(limits=limits)
        elif kind == ExternalKind.GLOBAL:
            valtype = reader.read_valtype()
            mut = reader.read_byte() != 0
            desc = GlobalType(valtype=valtype, mutable=mut)

        imports.append(ImportEntry(module=mod_name, name=field_name, kind=kind, desc=desc))
    return imports


def parse_function_section(reader: BinaryReader) -> List[int]:
    """Parse Section 3: Function section (type indices)."""
    return reader.read_vec(reader.read_u32)


def parse_table_section(reader: BinaryReader) -> List[TableType]:
    """Parse Section 4: Table section."""
    count = reader.read_u32()
    tables: List[TableType] = []
    for _ in range(count):
        elem_type = reader.read_valtype()
        limits = reader.read_limits()
        tables.append(TableType(element_type=elem_type, limits=limits))
    return tables


def parse_memory_section(reader: BinaryReader) -> List[MemoryType]:
    """Parse Section 5: Memory section."""
    count = reader.read_u32()
    memories: List[MemoryType] = []
    for _ in range(count):
        limits = reader.read_limits()
        memories.append(MemoryType(limits=limits))
    return memories


def parse_global_section(reader: BinaryReader) -> List[GlobalEntry]:
    """Parse Section 6: Global section."""
    count = reader.read_u32()
    globals_list: List[GlobalEntry] = []
    for _ in range(count):
        valtype = reader.read_valtype()
        mut = reader.read_byte() != 0
        init_expr = read_expr(reader)
        globals_list.append(GlobalEntry(type=GlobalType(valtype=valtype, mutable=mut), init_expr=init_expr))
    return globals_list


def parse_export_section(reader: BinaryReader) -> List[ExportEntry]:
    """Parse Section 7: Export section."""
    count = reader.read_u32()
    exports: List[ExportEntry] = []
    for _ in range(count):
        name = reader.read_name()
        kind_byte = reader.read_byte()
        try:
            kind = ExternalKind(kind_byte)
        except ValueError:
            raise BinaryReaderError(f"Unknown export kind byte 0x{kind_byte:02X}")
        idx = reader.read_u32()
        exports.append(ExportEntry(name=name, kind=kind, index=idx))
    return exports


def parse_start_section(reader: BinaryReader) -> int:
    """Parse Section 8: Start section."""
    return reader.read_u32()


def parse_element_section(reader: BinaryReader) -> List[ElementSegment]:
    """Parse Section 9: Element section."""
    count = reader.read_u32()
    elements: List[ElementSegment] = []
    for i in range(count):
        flags = reader.read_u32()
        table_idx = 0
        offset_expr: Optional[List[Instruction]] = None
        is_passive = False
        is_declarative = False

        if flags == 0:
            offset_expr = read_expr(reader)
            init_indices = reader.read_vec(reader.read_u32)
        elif flags == 1:
            is_passive = True
            reader.read_byte()  # elemkind (0x00)
            init_indices = reader.read_vec(reader.read_u32)
        elif flags == 2:
            table_idx = reader.read_u32()
            offset_expr = read_expr(reader)
            reader.read_byte()  # elemkind
            init_indices = reader.read_vec(reader.read_u32)
        elif flags == 3:
            is_declarative = True
            reader.read_byte()
            init_indices = reader.read_vec(reader.read_u32)
        else:
            # Fallback for extended element section flags 4..7
            if (flags & 0x01) == 0:
                offset_expr = read_expr(reader)
            if (flags & 0x02) != 0:
                table_idx = reader.read_u32()
            reader.read_byte()  # reftype or elemkind
            init_indices = reader.read_vec(reader.read_u32)

        elements.append(
            ElementSegment(
                index=i,
                table_index=table_idx,
                offset_expr=offset_expr,
                init_indices=init_indices,
                is_passive=is_passive,
                is_declarative=is_declarative,
            )
        )
    return elements


def parse_code_section(reader: BinaryReader, func_type_indices: List[int], imported_func_count: int) -> List[FunctionBody]:
    """Parse Section 10: Code section."""
    count = reader.read_u32()
    bodies: List[FunctionBody] = []
    for i in range(count):
        body_size = reader.read_u32()
        body_start = reader.current_offset
        body_reader = reader.sub_reader(body_size)

        # Parse local declarations
        local_vec_count = body_reader.read_u32()
        locals_list: List[LocalEntry] = []
        for _ in range(local_vec_count):
            cnt = body_reader.read_u32()
            vt = body_reader.read_valtype()
            locals_list.append(LocalEntry(count=cnt, valtype=vt))

        # Parse instructions until end of body
        instructions: List[Instruction] = []
        while body_reader.has_more:
            instr = read_instruction(body_reader)
            instructions.append(instr)

        func_idx = imported_func_count + i
        type_idx = func_type_indices[i] if i < len(func_type_indices) else 0

        bodies.append(
            FunctionBody(
                func_index=func_idx,
                type_index=type_idx,
                locals=locals_list,
                instructions=instructions,
                offset=body_start,
                size=body_size,
                raw_bytes=body_reader.data,
            )
        )
    return bodies


def parse_data_section(reader: BinaryReader) -> List[DataSegment]:
    """Parse Section 11: Data section."""
    count = reader.read_u32()
    datas: List[DataSegment] = []
    for i in range(count):
        flags = reader.read_u32()
        mem_idx = 0
        offset_expr: Optional[List[Instruction]] = None
        is_passive = False

        if flags == 0:
            offset_expr = read_expr(reader)
            byte_count = reader.read_u32()
            raw_data = reader.read_bytes(byte_count)
        elif flags == 1:
            is_passive = True
            byte_count = reader.read_u32()
            raw_data = reader.read_bytes(byte_count)
        elif flags == 2:
            mem_idx = reader.read_u32()
            offset_expr = read_expr(reader)
            byte_count = reader.read_u32()
            raw_data = reader.read_bytes(byte_count)
        else:
            raise BinaryReaderError(f"Unsupported data segment flags: {flags}")

        datas.append(
            DataSegment(
                index=i,
                memory_index=mem_idx,
                offset_expr=offset_expr,
                data=raw_data,
                is_passive=is_passive,
            )
        )
    return datas


def parse_name_section(data: bytes) -> Tuple[Dict[int, str], Dict[int, Dict[int, str]]]:
    """Parse the custom 'name' section for function and local variable names."""
    reader = BinaryReader(data)
    func_names: Dict[int, str] = {}
    local_names: Dict[int, Dict[int, str]] = {}

    while reader.has_more:
        try:
            sub_id = reader.read_byte()
            sub_len = reader.read_u32()
            sub_reader = reader.sub_reader(sub_len)

            if sub_id == 1:  # Function names
                fn_count = sub_reader.read_u32()
                for _ in range(fn_count):
                    f_idx = sub_reader.read_u32()
                    name = sub_reader.read_name()
                    func_names[f_idx] = name
            elif sub_id == 2:  # Local names
                fn_count = sub_reader.read_u32()
                for _ in range(fn_count):
                    f_idx = sub_reader.read_u32()
                    l_count = sub_reader.read_u32()
                    l_dict: Dict[int, str] = {}
                    for _ in range(l_count):
                        l_idx = sub_reader.read_u32()
                        l_name = sub_reader.read_name()
                        l_dict[l_idx] = l_name
                    local_names[f_idx] = l_dict
        except Exception:
            # Name section is optional and best-effort
            break

    return func_names, local_names
