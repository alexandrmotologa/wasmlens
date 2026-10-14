"""Unit tests for binary bloat and section size profiler."""

from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm
from wasmlens.profiler.bloat import analyze_bloat


def build_bloat_sample_wasm() -> bytes:
    """Build a module with multiple sections for bloat testing."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type section: 1 type
    type_payload = bytes([0x01, 0x60, 0x00, 0x00])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Function section: 1 func
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Code section: 1 function with a few instructions
    code_instr = bytes([
        0x00,              # 0 locals
        0x41, 0x01,        # i32.const 1
        0x41, 0x02,        # i32.const 2
        0x6A,              # i32.add
        0x1A,              # drop
        0x0B,              # end
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    return header + type_sec + func_sec + code_sec


def test_analyze_bloat():
    raw = build_bloat_sample_wasm()
    mod = parse_wasm(raw)
    report = analyze_bloat(mod, raw)

    assert report.total_size == len(raw)
    assert report.header_size == 8
    assert len(report.sections) >= 3

    # Check Treemap structure
    assert report.treemap_data["name"] == "wasm_module"
    assert len(report.treemap_data["children"]) >= 3

    # Check function attribution
    assert len(report.functions) == 1
    assert report.functions[0].instruction_count == 5

    # Check dictionary serialization
    d = report.to_dict()
    assert "sections" in d
    assert "treemap_data" in d
