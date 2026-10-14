"""Unit tests for standalone HTML report and C header exporters."""

from wasmlens.export.header import generate_c_header
from wasmlens.export.report import generate_html_report
from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm


def build_export_sample_wasm() -> bytes:
    """Build a module with memory, an exported function, and a global."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type section: (i32, i32) -> i32
    type_payload = bytes([0x01, 0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Memory section: min 1 page, max 4 pages
    mem_payload = bytes([0x01, 0x01, 0x01, 0x04])
    mem_sec = bytes([0x05]) + encode_u32(len(mem_payload)) + mem_payload

    # Func section: func 0 has type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Global section: 1 immutable i32 global = 42
    glob_payload = bytes([0x01, 0x7F, 0x00, 0x41, 0x2A, 0x0B])
    glob_sec = bytes([0x06]) + encode_u32(len(glob_payload)) + glob_payload

    # Export section: export "calculate" func 0
    name = b"calculate"
    exp_payload = bytes([0x01]) + encode_u32(len(name)) + name + bytes([0x00, 0x00])
    exp_sec = bytes([0x07]) + encode_u32(len(exp_payload)) + exp_payload

    # Code section
    code_instr = bytes([
        0x00,        # 0 locals
        0x20, 0x00,  # local.get 0
        0x20, 0x01,  # local.get 1
        0x6A,        # i32.add
        0x0B,        # end
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    return header + type_sec + mem_sec + func_sec + glob_sec + exp_sec + code_sec


def test_generate_c_header():
    raw = build_export_sample_wasm()
    mod = parse_wasm(raw)
    h_text = generate_c_header(mod, module_name="test_math")

    assert "#ifndef WASMLENS_TEST_MATH_H" in h_text
    assert "#define WASMLENS_TEST_MATH_H" in h_text
    assert "WASM_MEMORY_INITIAL_PAGES 1" in h_text
    assert "WASM_MEMORY_MAX_PAGES 4" in h_text
    assert "int32_t calculate(int32_t arg0, int32_t arg1);" in h_text
    assert "extern /* const */ int32_t wasm_global_0;" in h_text


def test_generate_html_report():
    raw = build_export_sample_wasm()
    mod = parse_wasm(raw)
    html_text = generate_html_report(mod)

    assert "<!DOCTYPE html>" in html_text
    assert "WasmLens Binary Report" in html_text
    assert "calculate" in html_text
    assert "i32.add" in html_text
    assert "Binary Sections" in html_text
    assert "Binary Bloat Breakdown" in html_text
