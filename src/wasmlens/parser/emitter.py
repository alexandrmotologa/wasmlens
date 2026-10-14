"""Authentic WebAssembly 2.0 binary assembler and serializer."""

from __future__ import annotations

import struct
from typing import List

from wasmlens.parser.leb128 import (
    encode_i32,
    encode_i64,
    encode_u32,
)
from wasmlens.parser.opcodes import ImmediateType, lookup_opcode
from wasmlens.parser.types import (
    CustomSection,
    DataSegment,
    ElementSegment,
    ExportEntry,
    ExternalKind,
    FunctionBody,
    FunctionType,
    GlobalEntry,
    ImportEntry,
    Instruction,
    MemoryType,
    SectionId,
    TableType,
    ValueType,
    WasmModule,
)


def assemble_instruction(instr: Instruction) -> bytes:
    """Encode an Instruction into raw WebAssembly bytecode bytes."""
    res = bytearray()
    if instr.prefix is not None:
        res.append(instr.prefix)
        res.extend(encode_u32(instr.opcode))
        info = lookup_opcode(instr.prefix, instr.opcode)
    else:
        res.append(instr.opcode)
        info = lookup_opcode(instr.opcode)

    imm_type = info.immediate_type
    ops = instr.operands

    if imm_type == ImmediateType.NONE:
        pass

    elif imm_type == ImmediateType.BLOCK_TYPE:
        if ops == ValueType.EMPTY_BLOCK or ops == 0x40:
            res.append(0x40)
        elif isinstance(ops, ValueType):
            res.append(ops.value)
        elif isinstance(ops, int):
            if ops in (0x7F, 0x7E, 0x7D, 0x7C, 0x7B, 0x70, 0x6F, 0x40):
                res.append(ops)
            else:
                res.extend(encode_i32(ops))

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
        res.extend(encode_u32(int(ops)))

    elif imm_type == ImmediateType.LABEL_TABLE:
        targets, default_tgt = ops
        res.extend(encode_u32(len(targets)))
        for t in targets:
            res.extend(encode_u32(int(t)))
        res.extend(encode_u32(int(default_tgt)))

    elif imm_type == ImmediateType.CALL_INDIRECT:
        type_idx, table_idx = ops
        res.extend(encode_u32(int(type_idx)))
        res.extend(encode_u32(int(table_idx)))

    elif imm_type == ImmediateType.MEM_ARG:
        align, offset = ops
        res.extend(encode_u32(int(align)))
        res.extend(encode_u32(int(offset)))

    elif imm_type in (ImmediateType.MEM_IDX, ImmediateType.MEMORY_FILL):
        res.append(int(ops) & 0xFF)

    elif imm_type == ImmediateType.I32_CONST:
        res.extend(encode_i32(int(ops)))

    elif imm_type == ImmediateType.I64_CONST:
        res.extend(encode_i64(int(ops)))

    elif imm_type == ImmediateType.F32_CONST:
        res.extend(struct.pack("<f", float(ops)))

    elif imm_type == ImmediateType.F64_CONST:
        res.extend(struct.pack("<d", float(ops)))

    elif imm_type == ImmediateType.VALTYPE:
        vt = ops.value if isinstance(ops, ValueType) else int(ops)
        res.append(vt & 0xFF)

    elif imm_type == ImmediateType.SELECT_TYPES:
        res.extend(encode_u32(len(ops)))
        for vt in ops:
            v_byte = vt.value if isinstance(vt, ValueType) else int(vt)
            res.append(v_byte)

    elif imm_type == ImmediateType.MEMORY_INIT:
        data_idx, mem_idx = ops
        res.extend(encode_u32(int(data_idx)))
        res.append(int(mem_idx) & 0xFF)

    elif imm_type == ImmediateType.MEMORY_COPY:
        dst_mem, src_mem = ops
        res.append(int(dst_mem) & 0xFF)
        res.append(int(src_mem) & 0xFF)

    elif imm_type == ImmediateType.TABLE_INIT:
        elem_idx, table_idx = ops
        res.extend(encode_u32(int(elem_idx)))
        res.extend(encode_u32(int(table_idx)))

    elif imm_type == ImmediateType.TABLE_COPY:
        dst_tbl, src_tbl = ops
        res.extend(encode_u32(int(dst_tbl)))
        res.extend(encode_u32(int(src_tbl)))

    return bytes(res)


def assemble_expr(instructions: List[Instruction]) -> bytes:
    """Assemble an expression sequence ending with 0x0B (end)."""
    res = bytearray()
    for instr in instructions:
        res.extend(assemble_instruction(instr))
    if not instructions or instructions[-1].mnemonic != "end":
        res.append(0x0B)
    return bytes(res)


def assemble_function_body(body: FunctionBody) -> bytes:
    """Encode a complete FunctionBody (locals vector + instruction stream)."""
    payload = bytearray()

    # Locals
    payload.extend(encode_u32(len(body.locals)))
    for loc in body.locals:
        payload.extend(encode_u32(loc.count))
        payload.append(loc.valtype.value)

    # Instructions
    for instr in body.instructions:
        payload.extend(assemble_instruction(instr))

    # Function body size prefix followed by payload
    return encode_u32(len(payload)) + bytes(payload)


def assemble_section(section_id: SectionId, payload: bytes) -> bytes:
    """Format a section with its ID and LEB128 payload size prefix."""
    return bytes([section_id.value]) + encode_u32(len(payload)) + payload


def emit_wasm(module: WasmModule) -> bytes:
    """Serialize a complete WasmModule back into binary WebAssembly 2.0 format."""
    out = bytearray()
    out.extend(module.magic)
    out.extend(struct.pack("<I", module.version))

    # 1. Type Section
    if module.types:
        payload = bytearray()
        payload.extend(encode_u32(len(module.types)))
        for t in module.types:
            payload.append(0x60)
            payload.extend(encode_u32(len(t.params)))
            for p in t.params:
                payload.append(p.value)
            payload.extend(encode_u32(len(t.results)))
            for r in t.results:
                payload.append(r.value)
        out.extend(assemble_section(SectionId.TYPE, bytes(payload)))

    # 2. Import Section
    if module.imports:
        payload = bytearray()
        payload.extend(encode_u32(len(module.imports)))
        for imp in module.imports:
            mod_bytes = imp.module.encode("utf-8")
            payload.extend(encode_u32(len(mod_bytes)) + mod_bytes)
            name_bytes = imp.name.encode("utf-8")
            payload.extend(encode_u32(len(name_bytes)) + name_bytes)
            payload.append(imp.kind.value)
            if imp.kind == ExternalKind.FUNCTION:
                payload.extend(encode_u32(int(imp.desc)))
            elif imp.kind == ExternalKind.MEMORY:
                limits = imp.desc.limits
                flags = 0x01 if limits.max is not None else 0x00
                payload.append(flags)
                payload.extend(encode_u32(limits.min))
                if limits.max is not None:
                    payload.extend(encode_u32(limits.max))
            elif imp.kind == ExternalKind.TABLE:
                tbl = imp.desc
                payload.append(tbl.element_type.value)
                flags = 0x01 if tbl.limits.max is not None else 0x00
                payload.append(flags)
                payload.extend(encode_u32(tbl.limits.min))
                if tbl.limits.max is not None:
                    payload.extend(encode_u32(tbl.limits.max))
            elif imp.kind == ExternalKind.GLOBAL:
                gl = imp.desc
                payload.append(gl.valtype.value)
                payload.append(0x01 if gl.mutable else 0x00)
        out.extend(assemble_section(SectionId.IMPORT, bytes(payload)))

    # 3. Function Section (type indices)
    if module.functions:
        payload = bytearray()
        payload.extend(encode_u32(len(module.functions)))
        for tid in module.functions:
            payload.extend(encode_u32(tid))
        out.extend(assemble_section(SectionId.FUNCTION, bytes(payload)))

    # 4. Table Section
    if module.tables:
        payload = bytearray()
        payload.extend(encode_u32(len(module.tables)))
        for tbl in module.tables:
            payload.append(tbl.element_type.value)
            flags = 0x01 if tbl.limits.max is not None else 0x00
            payload.append(flags)
            payload.extend(encode_u32(tbl.limits.min))
            if tbl.limits.max is not None:
                payload.extend(encode_u32(tbl.limits.max))
        out.extend(assemble_section(SectionId.TABLE, bytes(payload)))

    # 5. Memory Section
    if module.memories:
        payload = bytearray()
        payload.extend(encode_u32(len(module.memories)))
        for mem in module.memories:
            flags = 0x01 if mem.limits.max is not None else 0x00
            payload.append(flags)
            payload.extend(encode_u32(mem.limits.min))
            if mem.limits.max is not None:
                payload.extend(encode_u32(mem.limits.max))
        out.extend(assemble_section(SectionId.MEMORY, bytes(payload)))

    # 6. Global Section
    if module.globals:
        payload = bytearray()
        payload.extend(encode_u32(len(module.globals)))
        for g in module.globals:
            payload.append(g.type.valtype.value)
            payload.append(0x01 if g.type.mutable else 0x00)
            payload.extend(assemble_expr(g.init_expr))
        out.extend(assemble_section(SectionId.GLOBAL, bytes(payload)))

    # 7. Export Section
    if module.exports:
        payload = bytearray()
        payload.extend(encode_u32(len(module.exports)))
        for exp in module.exports:
            name_bytes = exp.name.encode("utf-8")
            payload.extend(encode_u32(len(name_bytes)) + name_bytes)
            payload.append(exp.kind.value)
            payload.extend(encode_u32(exp.index))
        out.extend(assemble_section(SectionId.EXPORT, bytes(payload)))

    # 8. Start Section
    if module.start_func is not None:
        payload = encode_u32(module.start_func)
        out.extend(assemble_section(SectionId.START, payload))

    # 9. Element Section
    if module.elements:
        payload = bytearray()
        payload.extend(encode_u32(len(module.elements)))
        for el in module.elements:
            payload.extend(encode_u32(0))  # standard active segment flag 0
            payload.extend(assemble_expr(el.offset_expr or []))
            payload.extend(encode_u32(len(el.init_indices)))
            for idx in el.init_indices:
                payload.extend(encode_u32(idx))
        out.extend(assemble_section(SectionId.ELEMENT, bytes(payload)))

    # 10. Code Section
    if module.codes:
        payload = bytearray()
        payload.extend(encode_u32(len(module.codes)))
        for code in module.codes:
            payload.extend(assemble_function_body(code))
        out.extend(assemble_section(SectionId.CODE, bytes(payload)))

    # 11. Data Section
    if module.datas:
        payload = bytearray()
        payload.extend(encode_u32(len(module.datas)))
        for d in module.datas:
            if d.is_passive:
                payload.extend(encode_u32(1))
                payload.extend(encode_u32(len(d.data)) + d.data)
            else:
                payload.extend(encode_u32(0))
                payload.extend(assemble_expr(d.offset_expr or []))
                payload.extend(encode_u32(len(d.data)) + d.data)
        out.extend(assemble_section(SectionId.DATA, bytes(payload)))

    # Custom Sections
    for cs in module.custom_sections:
        name_bytes = cs.name.encode("utf-8")
        sec_payload = encode_u32(len(name_bytes)) + name_bytes + cs.data
        out.extend(assemble_section(SectionId.CUSTOM, sec_payload))

    return bytes(out)
