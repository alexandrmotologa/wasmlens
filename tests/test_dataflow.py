"""Unit tests for data-flow analysis and stack-effect simulator."""

from wasmlens.analysis.dataflow import (
    analyze_dataflow,
    get_instruction_stack_effect,
)
from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.types import Instruction


def build_dataflow_sample_wasm() -> bytes:
    """Build a sample function with locals and arithmetic operations:

    (func (param i32 i32) (result i32)
      local.get 0
      local.get 1
      i32.add
      return
    )
    """
    header = b"\x00asm\x01\x00\x00\x00"

    # Type section: (i32, i32) -> i32
    type_payload = bytes([0x01, 0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Func section: func 0 has type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Code section
    code_instr = bytes([
        0x00,        # 0 locals
        0x20, 0x00,  # local.get 0
        0x20, 0x01,  # local.get 1
        0x6A,        # i32.add
        0x0F,        # return
        0x0B,        # end
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    return header + type_sec + func_sec + code_sec


def test_instruction_stack_effect():
    add_instr = Instruction(opcode=0x6A, mnemonic="i32.add")
    pops, pushes = get_instruction_stack_effect(add_instr)
    assert pops == 2
    assert pushes == 1

    const_instr = Instruction(opcode=0x41, mnemonic="i32.const", operands=42)
    pops, pushes = get_instruction_stack_effect(const_instr)
    assert pops == 0
    assert pushes == 1

    drop_instr = Instruction(opcode=0x1A, mnemonic="drop")
    pops, pushes = get_instruction_stack_effect(drop_instr)
    assert pops == 1
    assert pushes == 0


def test_analyze_dataflow():
    raw = build_dataflow_sample_wasm()
    mod = parse_wasm(raw)
    result = analyze_dataflow(mod, 0)

    assert result.func_index == 0
    assert result.max_stack_depth == 2
    assert len(result.instructions) == 5

    # Check depth at steps
    # local.get 0: depth 0 -> 1
    assert result.instructions[0].stack_depth_in == 0
    assert result.instructions[0].stack_depth_out == 1
    assert result.instructions[0].reads_locals == [0]

    # local.get 1: depth 1 -> 2
    assert result.instructions[1].stack_depth_in == 1
    assert result.instructions[1].stack_depth_out == 2
    assert result.instructions[1].reads_locals == [1]

    # i32.add: depth 2 -> 1
    assert result.instructions[2].stack_depth_in == 2
    assert result.instructions[2].stack_depth_out == 1

    # Check def-use map
    assert 0 in result.local_def_use
    assert -1 in result.local_def_use[0]["defs"]  # arg defined
    assert 0 in result.local_def_use[0]["uses"]   # read at pc 0

    assert 1 in result.local_def_use
    assert 1 in result.local_def_use[1]["uses"]   # read at pc 1

    # Check serialization
    d = result.to_dict()
    assert d["max_stack_depth"] == 2
    assert len(d["instructions"]) == 5
