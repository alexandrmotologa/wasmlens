"""Unit tests for advanced emulator debugger features: breakpoints, watchpoints, and time-travel."""

import pytest
from wasmlens.emulator.vm import WasmVM
from wasmlens.parser.leb128 import encode_u32
from wasmlens.parser.module import parse_wasm


def build_memory_test_wasm() -> bytes:
    """Build a module with memory operations:

    func 0:
      i32.const 16       ;; address
      i32.const 1337     ;; value
      i32.store 2 0      ;; store at 16
      i32.const 16       ;; address
      i32.load 2 0       ;; load from 16
      end
    """
    header = b"\x00asm\x01\x00\x00\x00"

    # Type section: () -> i32
    type_payload = bytes([0x01, 0x60, 0x00, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Memory section: 1 memory, min=1 page
    mem_payload = bytes([0x01, 0x00, 0x01])
    mem_sec = bytes([0x05]) + encode_u32(len(mem_payload)) + mem_payload

    # Function section: func 0 uses type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Code section
    code_instr = bytes([
        0x00,              # 0 locals
        0x41, 0x10,        # i32.const 16 (pc 0)
        0x41, 0xB9, 0x0A,  # i32.const 1337 (pc 1)
        0x36, 0x02, 0x00,  # i32.store 2 0 (pc 2)
        0x41, 0x10,        # i32.const 16 (pc 3)
        0x28, 0x02, 0x00,  # i32.load 2 0 (pc 4)
        0x0B,              # end (pc 5)
    ])
    code_body = encode_u32(len(code_instr)) + code_instr
    code_payload = bytes([0x01]) + code_body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    return header + type_sec + mem_sec + func_sec + code_sec


def test_breakpoint():
    raw = build_memory_test_wasm()
    mod = parse_wasm(raw)
    vm = WasmVM(mod)
    vm.invoke(0, [])

    # Set breakpoint at pc=3
    vm.add_breakpoint(0, 3)

    is_halted, reason = vm.run_until_break()
    assert not is_halted
    assert "Breakpoint at func 0 pc 3" in reason
    assert vm.call_stack[-1].pc == 3

    # Remove breakpoint and continue
    vm.remove_breakpoint(0, 3)
    is_halted, reason = vm.run_until_break()
    assert is_halted
    assert reason in ("completed", "halted")
    assert vm.stack.pop_i32() == 1337


def test_write_watchpoint():
    raw = build_memory_test_wasm()
    mod = parse_wasm(raw)
    vm = WasmVM(mod)
    vm.invoke(0, [])

    # Set write watchpoint on address 16
    vm.add_watchpoint(16, on_read=False, on_write=True)

    is_halted, reason = vm.run_until_break()
    assert not is_halted
    assert "WRITE watchpoint hit at 0x000010" in reason


def test_read_watchpoint():
    raw = build_memory_test_wasm()
    mod = parse_wasm(raw)
    vm = WasmVM(mod)
    vm.invoke(0, [])

    # Set read watchpoint on address 16
    vm.add_watchpoint(16, on_read=True, on_write=False)

    is_halted, reason = vm.run_until_break()
    assert not is_halted
    assert "READ watchpoint hit at 0x000010" in reason


def test_time_travel_step_backward():
    raw = build_memory_test_wasm()
    mod = parse_wasm(raw)
    vm = WasmVM(mod)
    vm.invoke(0, [])

    # Step 3 times: const 16, const 1337, store
    t1 = vm.step()
    assert t1.pc == 0
    t2 = vm.step()
    assert t2.pc == 1
    t3 = vm.step()
    assert t3.pc == 2

    # Memory at 16 was updated to 1337
    import struct
    assert struct.unpack("<i", vm.memory[16:20])[0] == 1337

    # Step backward past store
    b1 = vm.step_backward()
    assert b1.pc == 2
    # Memory should be restored to 0
    assert struct.unpack("<i", vm.memory[16:20])[0] == 0

    # Step backward again to pc 1
    b2 = vm.step_backward()
    assert b2.pc == 1
    assert len(vm.stack) == 1
    assert vm.stack.peek().value == 16
