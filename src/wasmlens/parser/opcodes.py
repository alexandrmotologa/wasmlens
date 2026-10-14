"""Complete WebAssembly 2.0 opcode registry, mnemonics, and immediate layout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple


class ImmediateType(Enum):
    """Types of immediate arguments encoded with instructions."""
    NONE = "none"
    BLOCK_TYPE = "block_type"
    LABEL_IDX = "label_idx"
    LABEL_TABLE = "label_table"  # br_table (list of targets + default)
    FUNC_IDX = "func_idx"
    TYPE_IDX = "type_idx"
    CALL_INDIRECT = "call_indirect"  # type_idx, table_idx
    LOCAL_IDX = "local_idx"
    GLOBAL_IDX = "global_idx"
    TABLE_IDX = "table_idx"
    MEM_ARG = "mem_arg"  # align, offset
    MEM_IDX = "mem_idx"
    I32_CONST = "i32_const"
    I64_CONST = "i64_const"
    F32_CONST = "f32_const"
    F64_CONST = "f64_const"
    V128_CONST = "v128_const"
    VALTYPE = "valtype"
    SELECT_TYPES = "select_types"
    MEMORY_INIT = "memory_init"  # data_idx, mem_idx
    DATA_IDX = "data_idx"
    MEMORY_COPY = "memory_copy"  # src_mem, dst_mem
    MEMORY_FILL = "memory_fill"  # mem_idx
    TABLE_INIT = "table_init"  # elem_idx, table_idx
    ELEM_IDX = "elem_idx"
    TABLE_COPY = "table_copy"  # dst_tbl, src_tbl


@dataclass(frozen=True)
class OpcodeInfo:
    """Metadata for a WebAssembly instruction."""
    opcode: int
    mnemonic: str
    immediate_type: ImmediateType = ImmediateType.NONE
    prefix: Optional[int] = None
    stack_pop: int = 0
    stack_push: int = 0
    is_terminator: bool = False
    is_branch: bool = False
    is_call: bool = False


# Map of standard single-byte opcodes (0x00 - 0xFF)
OPCODES: Dict[int, OpcodeInfo] = {
    # Control instructions
    0x00: OpcodeInfo(0x00, "unreachable", is_terminator=True),
    0x01: OpcodeInfo(0x01, "nop"),
    0x02: OpcodeInfo(0x02, "block", ImmediateType.BLOCK_TYPE),
    0x03: OpcodeInfo(0x03, "loop", ImmediateType.BLOCK_TYPE),
    0x04: OpcodeInfo(0x04, "if", ImmediateType.BLOCK_TYPE, stack_pop=1),
    0x05: OpcodeInfo(0x05, "else"),
    0x0B: OpcodeInfo(0x0B, "end"),
    0x0C: OpcodeInfo(0x0C, "br", ImmediateType.LABEL_IDX, is_branch=True, is_terminator=True),
    0x0D: OpcodeInfo(0x0D, "br_if", ImmediateType.LABEL_IDX, stack_pop=1, is_branch=True),
    0x0E: OpcodeInfo(0x0E, "br_table", ImmediateType.LABEL_TABLE, stack_pop=1, is_branch=True, is_terminator=True),
    0x0F: OpcodeInfo(0x0F, "return", is_terminator=True),
    0x10: OpcodeInfo(0x10, "call", ImmediateType.FUNC_IDX, is_call=True),
    0x11: OpcodeInfo(0x11, "call_indirect", ImmediateType.CALL_INDIRECT, stack_pop=1, is_call=True),

    # Parametric instructions
    0x1A: OpcodeInfo(0x1A, "drop", stack_pop=1),
    0x1B: OpcodeInfo(0x1B, "select", stack_pop=3, stack_push=1),
    0x1C: OpcodeInfo(0x1C, "select", ImmediateType.SELECT_TYPES, stack_pop=3, stack_push=1),

    # Variable instructions
    0x20: OpcodeInfo(0x20, "local.get", ImmediateType.LOCAL_IDX, stack_push=1),
    0x21: OpcodeInfo(0x21, "local.set", ImmediateType.LOCAL_IDX, stack_pop=1),
    0x22: OpcodeInfo(0x22, "local.tee", ImmediateType.LOCAL_IDX, stack_pop=1, stack_push=1),
    0x23: OpcodeInfo(0x23, "global.get", ImmediateType.GLOBAL_IDX, stack_push=1),
    0x24: OpcodeInfo(0x24, "global.set", ImmediateType.GLOBAL_IDX, stack_pop=1),

    # Table instructions
    0x25: OpcodeInfo(0x25, "table.get", ImmediateType.TABLE_IDX, stack_pop=1, stack_push=1),
    0x26: OpcodeInfo(0x26, "table.set", ImmediateType.TABLE_IDX, stack_pop=2),

    # Memory load instructions
    0x28: OpcodeInfo(0x28, "i32.load", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x29: OpcodeInfo(0x29, "i64.load", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2A: OpcodeInfo(0x2A, "f32.load", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2B: OpcodeInfo(0x2B, "f64.load", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2C: OpcodeInfo(0x2C, "i32.load8_s", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2D: OpcodeInfo(0x2D, "i32.load8_u", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2E: OpcodeInfo(0x2E, "i32.load16_s", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x2F: OpcodeInfo(0x2F, "i32.load16_u", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x30: OpcodeInfo(0x30, "i64.load8_s", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x31: OpcodeInfo(0x31, "i64.load8_u", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x32: OpcodeInfo(0x32, "i64.load16_s", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x33: OpcodeInfo(0x33, "i64.load16_u", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x34: OpcodeInfo(0x34, "i64.load32_s", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),
    0x35: OpcodeInfo(0x35, "i64.load32_u", ImmediateType.MEM_ARG, stack_pop=1, stack_push=1),

    # Memory store instructions
    0x36: OpcodeInfo(0x36, "i32.store", ImmediateType.MEM_ARG, stack_pop=2),
    0x37: OpcodeInfo(0x37, "i64.store", ImmediateType.MEM_ARG, stack_pop=2),
    0x38: OpcodeInfo(0x38, "f32.store", ImmediateType.MEM_ARG, stack_pop=2),
    0x39: OpcodeInfo(0x39, "f64.store", ImmediateType.MEM_ARG, stack_pop=2),
    0x3A: OpcodeInfo(0x3A, "i32.store8", ImmediateType.MEM_ARG, stack_pop=2),
    0x3B: OpcodeInfo(0x3B, "i32.store16", ImmediateType.MEM_ARG, stack_pop=2),
    0x3C: OpcodeInfo(0x3C, "i64.store8", ImmediateType.MEM_ARG, stack_pop=2),
    0x3D: OpcodeInfo(0x3D, "i64.store16", ImmediateType.MEM_ARG, stack_pop=2),
    0x3E: OpcodeInfo(0x3E, "i64.store32", ImmediateType.MEM_ARG, stack_pop=2),

    # Memory management
    0x3F: OpcodeInfo(0x3F, "memory.size", ImmediateType.MEM_IDX, stack_push=1),
    0x40: OpcodeInfo(0x40, "memory.grow", ImmediateType.MEM_IDX, stack_pop=1, stack_push=1),

    # Constants
    0x41: OpcodeInfo(0x41, "i32.const", ImmediateType.I32_CONST, stack_push=1),
    0x42: OpcodeInfo(0x42, "i64.const", ImmediateType.I64_CONST, stack_push=1),
    0x43: OpcodeInfo(0x43, "f32.const", ImmediateType.F32_CONST, stack_push=1),
    0x44: OpcodeInfo(0x44, "f64.const", ImmediateType.F64_CONST, stack_push=1),

    # i32 comparisons
    0x45: OpcodeInfo(0x45, "i32.eqz", stack_pop=1, stack_push=1),
    0x46: OpcodeInfo(0x46, "i32.eq", stack_pop=2, stack_push=1),
    0x47: OpcodeInfo(0x47, "i32.ne", stack_pop=2, stack_push=1),
    0x48: OpcodeInfo(0x48, "i32.lt_s", stack_pop=2, stack_push=1),
    0x49: OpcodeInfo(0x49, "i32.lt_u", stack_pop=2, stack_push=1),
    0x4A: OpcodeInfo(0x4A, "i32.gt_s", stack_pop=2, stack_push=1),
    0x4B: OpcodeInfo(0x4B, "i32.gt_u", stack_pop=2, stack_push=1),
    0x4C: OpcodeInfo(0x4C, "i32.le_s", stack_pop=2, stack_push=1),
    0x4D: OpcodeInfo(0x4D, "i32.le_u", stack_pop=2, stack_push=1),
    0x4E: OpcodeInfo(0x4E, "i32.ge_s", stack_pop=2, stack_push=1),
    0x4F: OpcodeInfo(0x4F, "i32.ge_u", stack_pop=2, stack_push=1),

    # i64 comparisons
    0x50: OpcodeInfo(0x50, "i64.eqz", stack_pop=1, stack_push=1),
    0x51: OpcodeInfo(0x51, "i64.eq", stack_pop=2, stack_push=1),
    0x52: OpcodeInfo(0x52, "i64.ne", stack_pop=2, stack_push=1),
    0x53: OpcodeInfo(0x53, "i64.lt_s", stack_pop=2, stack_push=1),
    0x54: OpcodeInfo(0x54, "i64.lt_u", stack_pop=2, stack_push=1),
    0x55: OpcodeInfo(0x55, "i64.gt_s", stack_pop=2, stack_push=1),
    0x56: OpcodeInfo(0x56, "i64.gt_u", stack_pop=2, stack_push=1),
    0x57: OpcodeInfo(0x57, "i64.le_s", stack_pop=2, stack_push=1),
    0x58: OpcodeInfo(0x58, "i64.le_u", stack_pop=2, stack_push=1),
    0x59: OpcodeInfo(0x59, "i64.ge_s", stack_pop=2, stack_push=1),
    0x5A: OpcodeInfo(0x5A, "i64.ge_u", stack_pop=2, stack_push=1),

    # f32 comparisons
    0x5B: OpcodeInfo(0x5B, "f32.eq", stack_pop=2, stack_push=1),
    0x5C: OpcodeInfo(0x5C, "f32.ne", stack_pop=2, stack_push=1),
    0x5D: OpcodeInfo(0x5D, "f32.lt", stack_pop=2, stack_push=1),
    0x5E: OpcodeInfo(0x5E, "f32.gt", stack_pop=2, stack_push=1),
    0x5F: OpcodeInfo(0x5F, "f32.le", stack_pop=2, stack_push=1),
    0x60: OpcodeInfo(0x60, "f32.ge", stack_pop=2, stack_push=1),

    # f64 comparisons
    0x61: OpcodeInfo(0x61, "f64.eq", stack_pop=2, stack_push=1),
    0x62: OpcodeInfo(0x62, "f64.ne", stack_pop=2, stack_push=1),
    0x63: OpcodeInfo(0x63, "f64.lt", stack_pop=2, stack_push=1),
    0x64: OpcodeInfo(0x64, "f64.gt", stack_pop=2, stack_push=1),
    0x65: OpcodeInfo(0x65, "f64.le", stack_pop=2, stack_push=1),
    0x66: OpcodeInfo(0x66, "f64.ge", stack_pop=2, stack_push=1),

    # i32 arithmetic / bitwise
    0x67: OpcodeInfo(0x67, "i32.clz", stack_pop=1, stack_push=1),
    0x68: OpcodeInfo(0x68, "i32.ctz", stack_pop=1, stack_push=1),
    0x69: OpcodeInfo(0x69, "i32.popcnt", stack_pop=1, stack_push=1),
    0x6A: OpcodeInfo(0x6A, "i32.add", stack_pop=2, stack_push=1),
    0x6B: OpcodeInfo(0x6B, "i32.sub", stack_pop=2, stack_push=1),
    0x6C: OpcodeInfo(0x6C, "i32.mul", stack_pop=2, stack_push=1),
    0x6D: OpcodeInfo(0x6D, "i32.div_s", stack_pop=2, stack_push=1),
    0x6E: OpcodeInfo(0x6E, "i32.div_u", stack_pop=2, stack_push=1),
    0x6F: OpcodeInfo(0x6F, "i32.rem_s", stack_pop=2, stack_push=1),
    0x70: OpcodeInfo(0x70, "i32.rem_u", stack_pop=2, stack_push=1),
    0x71: OpcodeInfo(0x71, "i32.and", stack_pop=2, stack_push=1),
    0x72: OpcodeInfo(0x72, "i32.or", stack_pop=2, stack_push=1),
    0x73: OpcodeInfo(0x73, "i32.xor", stack_pop=2, stack_push=1),
    0x74: OpcodeInfo(0x74, "i32.shl", stack_pop=2, stack_push=1),
    0x75: OpcodeInfo(0x75, "i32.shr_s", stack_pop=2, stack_push=1),
    0x76: OpcodeInfo(0x76, "i32.shr_u", stack_pop=2, stack_push=1),
    0x77: OpcodeInfo(0x77, "i32.rotl", stack_pop=2, stack_push=1),
    0x78: OpcodeInfo(0x78, "i32.rotr", stack_pop=2, stack_push=1),

    # i64 arithmetic / bitwise
    0x79: OpcodeInfo(0x79, "i64.clz", stack_pop=1, stack_push=1),
    0x7A: OpcodeInfo(0x7A, "i64.ctz", stack_pop=1, stack_push=1),
    0x7B: OpcodeInfo(0x7B, "i64.popcnt", stack_pop=1, stack_push=1),
    0x7C: OpcodeInfo(0x7C, "i64.add", stack_pop=2, stack_push=1),
    0x7D: OpcodeInfo(0x7D, "i64.sub", stack_pop=2, stack_push=1),
    0x7E: OpcodeInfo(0x7E, "i64.mul", stack_pop=2, stack_push=1),
    0x7F: OpcodeInfo(0x7F, "i64.div_s", stack_pop=2, stack_push=1),
    0x80: OpcodeInfo(0x80, "i64.div_u", stack_pop=2, stack_push=1),
    0x81: OpcodeInfo(0x81, "i64.rem_s", stack_pop=2, stack_push=1),
    0x82: OpcodeInfo(0x82, "i64.rem_u", stack_pop=2, stack_push=1),
    0x83: OpcodeInfo(0x83, "i64.and", stack_pop=2, stack_push=1),
    0x84: OpcodeInfo(0x84, "i64.or", stack_pop=2, stack_push=1),
    0x85: OpcodeInfo(0x85, "i64.xor", stack_pop=2, stack_push=1),
    0x86: OpcodeInfo(0x86, "i64.shl", stack_pop=2, stack_push=1),
    0x87: OpcodeInfo(0x87, "i64.shr_s", stack_pop=2, stack_push=1),
    0x88: OpcodeInfo(0x88, "i64.shr_u", stack_pop=2, stack_push=1),
    0x89: OpcodeInfo(0x89, "i64.rotl", stack_pop=2, stack_push=1),
    0x8A: OpcodeInfo(0x8A, "i64.rotr", stack_pop=2, stack_push=1),

    # f32 arithmetic
    0x8B: OpcodeInfo(0x8B, "f32.abs", stack_pop=1, stack_push=1),
    0x8C: OpcodeInfo(0x8C, "f32.neg", stack_pop=1, stack_push=1),
    0x8D: OpcodeInfo(0x8D, "f32.ceil", stack_pop=1, stack_push=1),
    0x8E: OpcodeInfo(0x8E, "f32.floor", stack_pop=1, stack_push=1),
    0x8F: OpcodeInfo(0x8F, "f32.trunc", stack_pop=1, stack_push=1),
    0x90: OpcodeInfo(0x90, "f32.nearest", stack_pop=1, stack_push=1),
    0x91: OpcodeInfo(0x91, "f32.sqrt", stack_pop=1, stack_push=1),
    0x92: OpcodeInfo(0x92, "f32.add", stack_pop=2, stack_push=1),
    0x93: OpcodeInfo(0x93, "f32.sub", stack_pop=2, stack_push=1),
    0x94: OpcodeInfo(0x94, "f32.mul", stack_pop=2, stack_push=1),
    0x95: OpcodeInfo(0x95, "f32.div", stack_pop=2, stack_push=1),
    0x96: OpcodeInfo(0x96, "f32.min", stack_pop=2, stack_push=1),
    0x97: OpcodeInfo(0x97, "f32.max", stack_pop=2, stack_push=1),
    0x98: OpcodeInfo(0x98, "f32.copysign", stack_pop=2, stack_push=1),

    # f64 arithmetic
    0x99: OpcodeInfo(0x99, "f64.abs", stack_pop=1, stack_push=1),
    0x9A: OpcodeInfo(0x9A, "f64.neg", stack_pop=1, stack_push=1),
    0x9B: OpcodeInfo(0x9B, "f64.ceil", stack_pop=1, stack_push=1),
    0x9C: OpcodeInfo(0x9C, "f64.floor", stack_pop=1, stack_push=1),
    0x9D: OpcodeInfo(0x9D, "f64.trunc", stack_pop=1, stack_push=1),
    0x9E: OpcodeInfo(0x9E, "f64.nearest", stack_pop=1, stack_push=1),
    0x9F: OpcodeInfo(0x9F, "f64.sqrt", stack_pop=1, stack_push=1),
    0xA0: OpcodeInfo(0xA0, "f64.add", stack_pop=2, stack_push=1),
    0xA1: OpcodeInfo(0xA1, "f64.sub", stack_pop=2, stack_push=1),
    0xA2: OpcodeInfo(0xA2, "f64.mul", stack_pop=2, stack_push=1),
    0xA3: OpcodeInfo(0xA3, "f64.div", stack_pop=2, stack_push=1),
    0xA4: OpcodeInfo(0xA4, "f64.min", stack_pop=2, stack_push=1),
    0xA5: OpcodeInfo(0xA5, "f64.max", stack_pop=2, stack_push=1),
    0xA6: OpcodeInfo(0xA6, "f64.copysign", stack_pop=2, stack_push=1),

    # Conversions
    0xA7: OpcodeInfo(0xA7, "i32.wrap_i64", stack_pop=1, stack_push=1),
    0xA8: OpcodeInfo(0xA8, "i32.trunc_f32_s", stack_pop=1, stack_push=1),
    0xA9: OpcodeInfo(0xA9, "i32.trunc_f32_u", stack_pop=1, stack_push=1),
    0xAA: OpcodeInfo(0xAA, "i32.trunc_f64_s", stack_pop=1, stack_push=1),
    0xAB: OpcodeInfo(0xAB, "i32.trunc_f64_u", stack_pop=1, stack_push=1),
    0xAC: OpcodeInfo(0xAC, "i64.extend_i32_s", stack_pop=1, stack_push=1),
    0xAD: OpcodeInfo(0xAD, "i64.extend_i32_u", stack_pop=1, stack_push=1),
    0xAE: OpcodeInfo(0xAE, "i64.trunc_f32_s", stack_pop=1, stack_push=1),
    0xAF: OpcodeInfo(0xAF, "i64.trunc_f32_u", stack_pop=1, stack_push=1),
    0xB0: OpcodeInfo(0xB0, "i64.trunc_f64_s", stack_pop=1, stack_push=1),
    0xB1: OpcodeInfo(0xB1, "i64.trunc_f64_u", stack_pop=1, stack_push=1),
    0xB2: OpcodeInfo(0xB2, "f32.convert_i32_s", stack_pop=1, stack_push=1),
    0xB3: OpcodeInfo(0xB3, "f32.convert_i32_u", stack_pop=1, stack_push=1),
    0xB4: OpcodeInfo(0xB4, "f32.convert_i64_s", stack_pop=1, stack_push=1),
    0xB5: OpcodeInfo(0xB5, "f32.convert_i64_u", stack_pop=1, stack_push=1),
    0xB6: OpcodeInfo(0xB6, "f32.demote_f64", stack_pop=1, stack_push=1),
    0xB7: OpcodeInfo(0xB7, "f64.convert_i32_s", stack_pop=1, stack_push=1),
    0xB8: OpcodeInfo(0xB8, "f64.convert_i32_u", stack_pop=1, stack_push=1),
    0xB9: OpcodeInfo(0xB9, "f64.convert_i64_s", stack_pop=1, stack_push=1),
    0xBA: OpcodeInfo(0xBA, "f64.convert_i64_u", stack_pop=1, stack_push=1),
    0xBB: OpcodeInfo(0xBB, "f64.promote_f32", stack_pop=1, stack_push=1),
    0xBC: OpcodeInfo(0xBC, "i32.reinterpret_f32", stack_pop=1, stack_push=1),
    0xBD: OpcodeInfo(0xBD, "i64.reinterpret_f64", stack_pop=1, stack_push=1),
    0xBE: OpcodeInfo(0xBE, "f32.reinterpret_i32", stack_pop=1, stack_push=1),
    0xBF: OpcodeInfo(0xBF, "f64.reinterpret_i64", stack_pop=1, stack_push=1),

    # Sign extensions
    0xC0: OpcodeInfo(0xC0, "i32.extend8_s", stack_pop=1, stack_push=1),
    0xC1: OpcodeInfo(0xC1, "i32.extend16_s", stack_pop=1, stack_push=1),
    0xC2: OpcodeInfo(0xC2, "i64.extend8_s", stack_pop=1, stack_push=1),
    0xC3: OpcodeInfo(0xC3, "i64.extend16_s", stack_pop=1, stack_push=1),
    0xC4: OpcodeInfo(0xC4, "i64.extend32_s", stack_pop=1, stack_push=1),

    # Reference types
    0xD0: OpcodeInfo(0xD0, "ref.null", ImmediateType.VALTYPE, stack_push=1),
    0xD1: OpcodeInfo(0xD1, "ref.is_null", stack_pop=1, stack_push=1),
    0xD2: OpcodeInfo(0xD2, "ref.func", ImmediateType.FUNC_IDX, stack_push=1),
}

# 0xFC prefixes (Bulk memory & Non-trapping float-to-int)
PREFIX_FC_OPCODES: Dict[int, OpcodeInfo] = {
    0: OpcodeInfo(0, "i32.trunc_sat_f32_s", prefix=0xFC, stack_pop=1, stack_push=1),
    1: OpcodeInfo(1, "i32.trunc_sat_f32_u", prefix=0xFC, stack_pop=1, stack_push=1),
    2: OpcodeInfo(2, "i32.trunc_sat_f64_s", prefix=0xFC, stack_pop=1, stack_push=1),
    3: OpcodeInfo(3, "i32.trunc_sat_f64_u", prefix=0xFC, stack_pop=1, stack_push=1),
    4: OpcodeInfo(4, "i64.trunc_sat_f32_s", prefix=0xFC, stack_pop=1, stack_push=1),
    5: OpcodeInfo(5, "i64.trunc_sat_f32_u", prefix=0xFC, stack_pop=1, stack_push=1),
    6: OpcodeInfo(6, "i64.trunc_sat_f64_s", prefix=0xFC, stack_pop=1, stack_push=1),
    7: OpcodeInfo(7, "i64.trunc_sat_f64_u", prefix=0xFC, stack_pop=1, stack_push=1),
    8: OpcodeInfo(8, "memory.init", ImmediateType.MEMORY_INIT, prefix=0xFC, stack_pop=3),
    9: OpcodeInfo(9, "data.drop", ImmediateType.DATA_IDX, prefix=0xFC),
    10: OpcodeInfo(10, "memory.copy", ImmediateType.MEMORY_COPY, prefix=0xFC, stack_pop=3),
    11: OpcodeInfo(11, "memory.fill", ImmediateType.MEMORY_FILL, prefix=0xFC, stack_pop=3),
    12: OpcodeInfo(12, "table.init", ImmediateType.TABLE_INIT, prefix=0xFC, stack_pop=3),
    13: OpcodeInfo(13, "elem.drop", ImmediateType.ELEM_IDX, prefix=0xFC),
    14: OpcodeInfo(14, "table.copy", ImmediateType.TABLE_COPY, prefix=0xFC, stack_pop=3),
    15: OpcodeInfo(15, "table.grow", ImmediateType.TABLE_IDX, prefix=0xFC, stack_pop=2, stack_push=1),
    16: OpcodeInfo(16, "table.size", ImmediateType.TABLE_IDX, prefix=0xFC, stack_push=1),
    17: OpcodeInfo(17, "table.fill", ImmediateType.TABLE_IDX, prefix=0xFC, stack_pop=3),
}


def lookup_opcode(opcode_byte: int, sub_opcode: Optional[int] = None) -> OpcodeInfo:
    """Look up opcode info by primary byte and optional prefix sub-opcode."""
    if opcode_byte == 0xFC:
        if sub_opcode is None or sub_opcode not in PREFIX_FC_OPCODES:
            return OpcodeInfo(
                opcode=sub_opcode or 0,
                mnemonic=f"fc_unknown_{sub_opcode}",
                prefix=0xFC
            )
        return PREFIX_FC_OPCODES[sub_opcode]
    if opcode_byte in OPCODES:
        return OPCODES[opcode_byte]
    return OpcodeInfo(opcode=opcode_byte, mnemonic=f"unknown_0x{opcode_byte:02X}")
