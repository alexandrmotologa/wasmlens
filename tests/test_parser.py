"""Comprehensive unit tests for WebAssembly binary parser and section decoders."""

import pytest
from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.reader import BinaryReaderError
from wasmlens.parser.types import ExternalKind, SectionId, ValueType


def test_empty_module():
    raw = b"\x00asm\x01\x00\x00\x00"
    module = parse_wasm(raw)
    assert module.magic == b"\x00asm"
    assert module.version == 1
    assert len(module.types) == 0
    assert len(module.codes) == 0
    assert len(module.sections) == 0


def test_invalid_header():
    with pytest.raises(BinaryReaderError, match="Invalid magic bytes"):
        parse_wasm(b"\x00abc\x01\x00\x00\x00")

    with pytest.raises(BinaryReaderError, match="Unsupported WebAssembly version"):
        parse_wasm(b"\x00asm\x02\x00\x00\x00")

    with pytest.raises(BinaryReaderError, match="too short"):
        parse_wasm(b"\x00asm")


def test_add_function_module():
    """Build and parse a complete authentic wasm module with an exported add(i32, i32) -> i32."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Section 1: Type section: 1 type: (i32, i32) -> (i32)
    # 0x01 (sec id), size, 0x01 (count), 0x60 (func), 0x02 (params), 0x7F, 0x7F, 0x01 (results), 0x7F
    type_payload = bytes([0x01, 0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Section 3: Function section: 1 func using type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Section 7: Export section: 1 export "add" func 0
    name = b"add"
    export_payload = bytes([0x01]) + encode_u32(len(name)) + name + bytes([0x00, 0x00])
    export_sec = bytes([0x07]) + encode_u32(len(export_payload)) + export_payload

    # Section 10: Code section: 1 body: 0 locals, local.get 0, local.get 1, i32.add, end
    code_instr = bytes([
        0x00,        # 0 local declarations
        0x20, 0x00,  # local.get 0
        0x20, 0x01,  # local.get 1
        0x6A,        # i32.add
        0x0B,        # end
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    full_wasm = header + type_sec + func_sec + export_sec + code_sec
    module = parse_wasm(full_wasm)

    assert len(module.types) == 1
    assert module.types[0].params == [ValueType.I32, ValueType.I32]
    assert module.types[0].results == [ValueType.I32]

    assert len(module.functions) == 1
    assert module.functions[0] == 0

    assert len(module.exports) == 1
    assert module.exports[0].name == "add"
    assert module.exports[0].kind == ExternalKind.FUNCTION
    assert module.exports[0].index == 0

    assert len(module.codes) == 1
    assert len(module.codes[0].instructions) == 4
    assert module.codes[0].instructions[0].mnemonic == "local.get"
    assert module.codes[0].instructions[0].operands == 0
    assert module.codes[0].instructions[1].mnemonic == "local.get"
    assert module.codes[0].instructions[1].operands == 1
    assert module.codes[0].instructions[2].mnemonic == "i32.add"
    assert module.codes[0].instructions[3].mnemonic == "end"


def test_memory_and_data_section():
    """Build and parse a module with memory (min=1, max=2) and an active data segment."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Section 5: Memory section: 1 memory, flags=1 (min=1, max=2)
    mem_payload = bytes([0x01, 0x01, 0x01, 0x02])
    mem_sec = bytes([0x05]) + encode_u32(len(mem_payload)) + mem_payload

    # Section 11: Data section: 1 segment: flags=0, offset=i32.const 16 end, data="Hello"
    text = b"Hello"
    data_payload = bytes([
        0x01,  # 1 segment
        0x00,  # flags=0 (active, memory 0)
        0x41, 0x10, 0x0B,  # i32.const 16, end
    ]) + encode_u32(len(text)) + text
    data_sec = bytes([0x0B]) + encode_u32(len(data_payload)) + data_payload

    full_wasm = header + mem_sec + data_sec
    module = parse_wasm(full_wasm)

    assert len(module.memories) == 1
    assert module.memories[0].limits.min == 1
    assert module.memories[0].limits.max == 2

    assert len(module.datas) == 1
    assert module.datas[0].memory_index == 0
    assert module.datas[0].data == b"Hello"
    assert len(module.datas[0].offset_expr) == 2
    assert module.datas[0].offset_expr[0].mnemonic == "i32.const"
    assert module.datas[0].offset_expr[0].operands == 16


def test_custom_name_section():
    """Build and parse a module with custom 'name' section for function names."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Custom section: name="name"
    # Subsection 1 (functions): 1 name: func 0 is "compute"
    fn_name = b"compute"
    fn_entry = bytes([0x00]) + encode_u32(len(fn_name)) + fn_name
    subsec_payload = bytes([0x01]) + fn_entry
    subsec = bytes([0x01]) + encode_u32(len(subsec_payload)) + subsec_payload

    sec_name = b"name"
    custom_payload = encode_u32(len(sec_name)) + sec_name + subsec
    custom_sec = bytes([0x00]) + encode_u32(len(custom_payload)) + custom_payload

    full_wasm = header + custom_sec
    module = parse_wasm(full_wasm)

    assert len(module.custom_sections) == 1
    assert module.custom_sections[0].name == "name"
    assert module.get_function_name(0) == "compute"
