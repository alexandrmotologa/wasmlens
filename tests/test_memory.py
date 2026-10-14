"""Unit tests for linear memory inspector, hexdump, and search."""

from pathlib import Path

from wasmlens.memory.hexdump import format_hexdump, hexdump_lines
from wasmlens.memory.inspector import MemoryInspector, WASM_PAGE_SIZE
from wasmlens.memory.search import find_bytes, find_i32, find_string
from wasmlens.parser.module import parse_wasm


def test_memory_inspection_and_pages():
    sample_path = Path("src/wasmlens/samples/memory_ops.wasm")
    module = parse_wasm(sample_path)

    inspector = MemoryInspector(module)
    assert inspector.min_pages == 1
    assert inspector.max_pages == 2
    assert len(inspector.buffer) == WASM_PAGE_SIZE

    # The active data segment "WasmLens Runtime 2026\x00" was placed at offset 0
    read_back = inspector.read_bytes(0, 21)
    assert read_back == b"WasmLens Runtime 2026"

    pages = inspector.get_pages()
    assert len(pages) == 1
    page0 = pages[0]
    assert page0.index == 0
    assert page0.start_address == 0
    assert page0.end_address == WASM_PAGE_SIZE
    assert len(page0.regions) == 1
    assert page0.regions[0].name == "data_seg_0"
    assert page0.regions[0].start == 0

    # Test hexdump
    dump = format_hexdump(read_back, collapse_zeroes=False)
    assert "57 61 73 6D" in dump.upper()
    assert "WasmLens Runtime" in dump
    assert "2026" in dump

    # Test search
    offsets = find_string(inspector.buffer, "Runtime")
    assert offsets == [9]

    byte_offsets = find_bytes(inspector.buffer, b"2026")
    assert byte_offsets == [17]
