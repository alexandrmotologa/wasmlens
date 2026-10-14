"""Unit tests for WebAssembly 2.0 bytecode emulator and step tracer."""

from pathlib import Path

from wasmlens.emulator.vm import WasmVM
from wasmlens.parser.module import parse_wasm


def test_emulator_factorial():
    module = parse_wasm(Path("src/wasmlens/samples/factorial.wasm"))
    vm = WasmVM(module)
    vm.invoke(0, [5])
    results = vm.run_to_completion()
    assert results == [120]


def test_emulator_fibonacci():
    module = parse_wasm(Path("src/wasmlens/samples/fibonacci.wasm"))
    vm = WasmVM(module)
    vm.invoke(0, [7])
    results = vm.run_to_completion()
    assert results == [13]


def test_emulator_memory_ops_and_tracing():
    module = parse_wasm(Path("src/wasmlens/samples/memory_ops.wasm"))
    vm = WasmVM(module)
    vm.invoke(0, [256, 42])

    traces = vm.trace_execution()
    assert len(traces) >= 5

    # Check store instruction memory diff
    store_traces = [t for t in traces if t.instruction_mnemonic == "i32.store"]
    assert len(store_traces) == 1
    assert store_traces[0].memory_diff is not None
    assert store_traces[0].memory_diff.address == 256
    assert store_traces[0].memory_diff.new_bytes == (42).to_bytes(4, byteorder="little")

    # Final result
    assert not vm.stack.is_empty()
    assert vm.stack.pop_i32() == 42
