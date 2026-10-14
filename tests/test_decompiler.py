"""Unit tests for WAT disassembler and structured decompiler."""

from pathlib import Path

from wasmlens.decompiler.reconstructor import Decompiler
from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
)
from wasmlens.parser.module import parse_wasm


def test_disassembler_and_decompiler_samples():
    sample_dir = Path("src/wasmlens/samples")

    # 1. Factorial
    fact_module = parse_wasm(sample_dir / "factorial.wasm")
    wat = disassemble_module(fact_module)
    assert "(module" in wat
    assert "func $factorial" in wat
    assert "loop" in wat
    assert "br_if 1" in wat

    decompiler = Decompiler(fact_module)
    c_code = decompiler.decompile_function(0)
    assert "factorial" in c_code
    assert "while (1) /* loop" in c_code
    assert "break /* to label_1 */" in c_code
    assert "return" in c_code

    # 2. Fibonacci
    fib_module = parse_wasm(sample_dir / "fibonacci.wasm")
    fib_wat = disassemble_function(fib_module, 0)
    assert "if (result i32)" in fib_wat
    assert "call 0" in fib_wat

    fib_c = Decompiler(fib_module).decompile_function(0)
    assert "if (" in fib_c
    assert "fib(" in fib_c

    # 3. Memory ops
    mem_module = parse_wasm(sample_dir / "memory_ops.wasm")
    mem_wat = disassemble_module(mem_module)
    assert "i32.store" in mem_wat
    assert "i32.load" in mem_wat

    mem_c = Decompiler(mem_module).decompile_function(0)
    assert "*(" in mem_c
