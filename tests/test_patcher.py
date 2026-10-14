"""Unit tests for binary emitter and patcher."""

import pytest
from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.emitter import emit_wasm
from wasmlens.patcher.patcher import WasmPatcher, PatchError
from wasmlens.parser.types import Instruction


def build_sample_wasm() -> bytes:
    """Build an authentic wasm module with an exported func: i32.const 42, return."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type section: () -> i32
    type_payload = bytes([0x01, 0x60, 0x00, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Func section: func 0 has type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Export section: "getValue"
    name = b"getValue"
    export_payload = bytes([0x01]) + encode_u32(len(name)) + name + bytes([0x00, 0x00])
    export_sec = bytes([0x07]) + encode_u32(len(export_payload)) + export_payload

    # Code section: i32.const 42 (0x41, 0x2A), end (0x0B)
    code_instr = bytes([
        0x00,        # 0 locals
        0x41, 0x2A,  # i32.const 42
        0x0B,        # end
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    return header + type_sec + func_sec + export_sec + code_sec


def test_emitter_roundtrip():
    raw = build_sample_wasm()
    mod = parse_wasm(raw)
    emitted = emit_wasm(mod)

    # Parse emitted binary and check parity
    reparsed = parse_wasm(emitted)
    assert len(reparsed.types) == 1
    assert len(reparsed.codes) == 1
    assert len(reparsed.exports) == 1
    assert reparsed.codes[0].instructions[0].mnemonic == "i32.const"
    assert reparsed.codes[0].instructions[0].operands == 42


def test_patch_constant():
    raw = build_sample_wasm()
    patcher = WasmPatcher(raw)
    patcher.patch_constant(func_index=0, pc=0, new_val=1337)

    patched_bytes = patcher.emit_binary()
    reparsed = parse_wasm(patched_bytes)
    assert reparsed.codes[0].instructions[0].operands == 1337


def test_nop_instruction():
    raw = build_sample_wasm()
    patcher = WasmPatcher(raw)
    patcher.nop_instruction(func_index=0, pc=0)

    patched_bytes = patcher.emit_binary()
    reparsed = parse_wasm(patched_bytes)
    assert reparsed.codes[0].instructions[0].mnemonic == "nop"


def test_patch_instruction():
    raw = build_sample_wasm()
    patcher = WasmPatcher(raw)
    patcher.patch_instruction(0, 0, Instruction(opcode=0x41, mnemonic="i32.const", operands=999))

    reparsed = parse_wasm(patcher.emit_binary())
    assert reparsed.codes[0].instructions[0].operands == 999


def test_patch_invalid_indices():
    raw = build_sample_wasm()
    patcher = WasmPatcher(raw)

    with pytest.raises(PatchError, match="Function index 5 out of bounds"):
        patcher.patch_constant(5, 0, 10)

    with pytest.raises(PatchError, match="Instruction index 99 out of range"):
        patcher.patch_constant(0, 99, 10)

    with pytest.raises(PatchError, match="not a constant"):
        # pc 1 is 'end'
        patcher.patch_constant(0, 1, 10)


def test_patcher_save(tmp_path):
    raw = build_sample_wasm()
    patcher = WasmPatcher(raw)
    patcher.patch_constant(0, 0, 777)
    out_file = tmp_path / "patched.wasm"
    patcher.save(out_file)

    assert out_file.exists()
    reparsed = parse_wasm(out_file)
    assert reparsed.codes[0].instructions[0].operands == 777


def test_emitter_diverse_instructions():
    from wasmlens.parser.emitter import assemble_instruction

    # i64.const
    i64_bytes = assemble_instruction(Instruction(opcode=0x42, mnemonic="i64.const", operands=1000000000000))
    assert i64_bytes[0] == 0x42

    # f32.const
    f32_bytes = assemble_instruction(Instruction(opcode=0x43, mnemonic="f32.const", operands=3.14))
    assert f32_bytes[0] == 0x43

    # f64.const
    f64_bytes = assemble_instruction(Instruction(opcode=0x44, mnemonic="f64.const", operands=2.71828))
    assert f64_bytes[0] == 0x44

    # br_table (targets=[0, 1], default=2)
    br_tbl_bytes = assemble_instruction(Instruction(opcode=0x0E, mnemonic="br_table", operands=([0, 1], 2)))
    assert br_tbl_bytes[0] == 0x0E

    # call_indirect (type=0, table=0)
    call_ind_bytes = assemble_instruction(Instruction(opcode=0x11, mnemonic="call_indirect", operands=(0, 0)))
    assert call_ind_bytes[0] == 0x11

    # mem_arg (align=2, offset=16)
    mem_bytes = assemble_instruction(Instruction(opcode=0x28, mnemonic="i32.load", operands=(2, 16)))
    assert mem_bytes[0] == 0x28


def test_emitter_complex_module_roundtrip():
    from wasmlens.parser.module import parse_wasm
    from wasmlens.parser.emitter import emit_wasm

    # Test roundtrip on our sample files
    from pathlib import Path
    samples = [
        Path("src/wasmlens/samples/factorial.wasm"),
        Path("src/wasmlens/samples/memory_ops.wasm"),
    ]
    for s in samples:
        if s.exists():
            mod = parse_wasm(s)
            emitted = emit_wasm(mod)
            reparsed = parse_wasm(emitted)
            assert reparsed.magic == b"\x00asm"
            assert reparsed.version == 1
            assert len(reparsed.types) == len(mod.types)
            assert len(reparsed.codes) == len(mod.codes)

