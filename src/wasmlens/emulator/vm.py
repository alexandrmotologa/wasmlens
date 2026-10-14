"""Authentic WebAssembly 2.0 bytecode emulator with step-by-step tracing."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from wasmlens.emulator.frame import ActivationFrame, ControlLabel
from wasmlens.emulator.stack import OperandStack, VMError, WasmValue
from wasmlens.memory.inspector import MemoryInspector, WASM_PAGE_SIZE
from wasmlens.parser.types import ExternalKind, Instruction, ValueType, WasmModule


@dataclass
class MemoryDiff:
    """Recorded memory change during an instruction execution."""
    address: int
    size: int
    old_bytes: bytes
    new_bytes: bytes


@dataclass
class StepTrace:
    """Execution state snapshot before and after a single instruction step."""
    step_number: int
    func_index: int
    func_name: str
    pc: int
    instruction_mnemonic: str
    instruction_operands: str
    instruction_offset: int
    stack_before: List[dict]
    stack_after: List[dict]
    locals_snapshot: List[dict]
    memory_diff: Optional[MemoryDiff] = None
    is_halted: bool = False


class WasmVM:
    """WebAssembly 2.0 virtual machine runtime."""

    def __init__(self, module: WasmModule) -> None:
        self.module = module
        self.inspector = MemoryInspector(module)
        self.memory: bytearray = self.inspector.buffer
        self.stack = OperandStack()
        self.call_stack: List[ActivationFrame] = []
        self.globals: List[WasmValue] = []
        self.step_counter = 0

        self._init_globals()

    def _init_globals(self) -> None:
        """Initialize globals by executing init expressions."""
        for g in self.module.globals:
            val = 0
            for instr in g.init_expr:
                if instr.mnemonic in ("i32.const", "i64.const", "f32.const", "f64.const"):
                    val = instr.operands
            self.globals.append(WasmValue(g.type.valtype, val))

    def invoke(self, func_index: int, args: List[int | float]) -> None:
        """Set up call stack for function execution."""
        imported_count = self.module.imported_func_count
        if func_index < imported_count:
            raise VMError(f"Cannot directly invoke imported function {func_index} without host binding")

        body_idx = func_index - imported_count
        body = self.module.codes[body_idx]
        sig = self.module.get_function_type(func_index)
        fn_name = self.module.get_function_name(func_index)

        if len(args) != len(sig.params):
            raise VMError(f"Function {fn_name} expected {len(sig.params)} arguments, got {len(args)}")

        # Initialize locals: arguments followed by zeroed declared locals
        locals_list: List[WasmValue] = []
        for i, val in enumerate(args):
            locals_list.append(WasmValue(sig.params[i], val))

        for loc in body.locals:
            for _ in range(loc.count):
                default_val = 0.0 if loc.valtype in (ValueType.F32, ValueType.F64) else 0
                locals_list.append(WasmValue(loc.valtype, default_val))

        frame = ActivationFrame(
            func_index=func_index,
            func_name=fn_name,
            locals=locals_list,
            instructions=body.instructions,
            pc=0,
        )
        self.call_stack.append(frame)

    @property
    def is_running(self) -> bool:
        return len(self.call_stack) > 0

    def step(self) -> StepTrace:
        """Execute a single bytecode instruction and return execution trace."""
        if not self.call_stack:
            raise VMError("Virtual machine is halted; no active call frame")

        frame = self.call_stack[-1]
        if frame.pc >= len(frame.instructions):
            self.call_stack.pop()
            return StepTrace(
                step_number=self.step_counter,
                func_index=frame.func_index,
                func_name=frame.func_name,
                pc=frame.pc,
                instruction_mnemonic="return",
                instruction_operands="",
                instruction_offset=0,
                stack_before=self.stack.snapshot(),
                stack_after=self.stack.snapshot(),
                locals_snapshot=frame.snapshot_locals(),
                is_halted=not self.is_running,
            )

        instr = frame.instructions[frame.pc]
        pc_before = frame.pc
        stack_before = self.stack.snapshot()
        self.step_counter += 1

        mem_diff = self._execute_instruction(frame, instr)

        # Advance PC if instruction didn't perform a jump or function call
        if self.call_stack and self.call_stack[-1] is frame:
            if frame.pc == pc_before:
                frame.pc += 1

        stack_after = self.stack.snapshot()
        locals_snap = frame.snapshot_locals()

        return StepTrace(
            step_number=self.step_counter,
            func_index=frame.func_index,
            func_name=frame.func_name,
            pc=pc_before,
            instruction_mnemonic=instr.mnemonic,
            instruction_operands=str(instr.operands) if instr.operands is not None else "",
            instruction_offset=instr.offset,
            stack_before=stack_before,
            stack_after=stack_after,
            locals_snapshot=locals_snap,
            memory_diff=mem_diff,
            is_halted=not self.is_running,
        )

    def _execute_instruction(self, frame: ActivationFrame, instr: Instruction) -> Optional[MemoryDiff]:
        m = instr.mnemonic
        mem_diff: Optional[MemoryDiff] = None

        # 1. Constants
        if m == "i32.const":
            self.stack.push_i32(instr.operands)
        elif m == "i64.const":
            self.stack.push_i64(instr.operands)
        elif m == "f32.const":
            self.stack.push_f32(instr.operands)
        elif m == "f64.const":
            self.stack.push_f64(instr.operands)

        # 2. Variable access
        elif m == "local.get":
            idx = instr.operands
            self.stack.push(frame.locals[idx])
        elif m == "local.set":
            idx = instr.operands
            frame.locals[idx] = self.stack.pop()
        elif m == "local.tee":
            idx = instr.operands
            val = self.stack.peek()
            frame.locals[idx] = val
        elif m == "global.get":
            idx = instr.operands
            self.stack.push(self.globals[idx])
        elif m == "global.set":
            idx = instr.operands
            self.globals[idx] = self.stack.pop()

        # 3. Memory load
        elif m in ("i32.load", "i64.load", "f32.load", "f64.load", "i32.load8_s", "i32.load8_u", "i32.load16_s", "i32.load16_u"):
            align, offset = instr.operands
            addr = self.stack.pop_i32() + offset
            if addr < 0 or addr >= len(self.memory):
                raise VMError(f"Out of bounds memory access at 0x{addr:08X}")

            if m == "i32.load":
                val = struct.unpack("<i", self.memory[addr : addr + 4])[0]
                self.stack.push_i32(val)
            elif m == "i64.load":
                val = struct.unpack("<q", self.memory[addr : addr + 8])[0]
                self.stack.push_i64(val)
            elif m == "f32.load":
                val = struct.unpack("<f", self.memory[addr : addr + 4])[0]
                self.stack.push_f32(val)
            elif m == "f64.load":
                val = struct.unpack("<d", self.memory[addr : addr + 8])[0]
                self.stack.push_f64(val)
            elif m == "i32.load8_s":
                val = struct.unpack("<b", self.memory[addr : addr + 1])[0]
                self.stack.push_i32(val)
            elif m == "i32.load8_u":
                val = struct.unpack("<B", self.memory[addr : addr + 1])[0]
                self.stack.push_i32(val)
            elif m == "i32.load16_s":
                val = struct.unpack("<h", self.memory[addr : addr + 2])[0]
                self.stack.push_i32(val)
            elif m == "i32.load16_u":
                val = struct.unpack("<H", self.memory[addr : addr + 2])[0]
                self.stack.push_i32(val)

        # 4. Memory store
        elif m in ("i32.store", "i64.store", "f32.store", "f64.store", "i32.store8", "i32.store16"):
            align, offset = instr.operands
            val = self.stack.pop().value
            addr = self.stack.pop_i32() + offset
            if addr < 0 or addr >= len(self.memory):
                raise VMError(f"Out of bounds memory write at 0x{addr:08X}")

            if m == "i32.store":
                raw = struct.pack("<i", int(val) & 0xFFFFFFFF)
            elif m == "i64.store":
                raw = struct.pack("<q", int(val))
            elif m == "f32.store":
                raw = struct.pack("<f", float(val))
            elif m == "f64.store":
                raw = struct.pack("<d", float(val))
            elif m == "i32.store8":
                raw = struct.pack("<B", int(val) & 0xFF)
            elif m == "i32.store16":
                raw = struct.pack("<H", int(val) & 0xFFFF)
            else:
                raw = b""

            old_bytes = bytes(self.memory[addr : addr + len(raw)])
            self.memory[addr : addr + len(raw)] = raw
            mem_diff = MemoryDiff(address=addr, size=len(raw), old_bytes=old_bytes, new_bytes=raw)

        # 5. Arithmetic & Bitwise
        elif m == "i32.add":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a + b)
        elif m == "i32.sub":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a - b)
        elif m == "i32.mul":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a * b)
        elif m == "i32.div_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            if b == 0:
                raise VMError("Integer divide by zero")
            self.stack.push_i32(int(a / b))
        elif m == "i32.div_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            if b == 0:
                raise VMError("Integer divide by zero")
            self.stack.push_i32(a // b)
        elif m == "i32.rem_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            if b == 0:
                raise VMError("Integer divide by zero")
            self.stack.push_i32(int(math.fmod(a, b)))
        elif m == "i32.rem_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            if b == 0:
                raise VMError("Integer divide by zero")
            self.stack.push_i32(a % b)
        elif m == "i32.and":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a & b)
        elif m == "i32.or":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a | b)
        elif m == "i32.xor":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(a ^ b)
        elif m == "i32.shl":
            b = self.stack.pop_i32() & 0x1F
            a = self.stack.pop_i32()
            self.stack.push_i32(a << b)
        elif m == "i32.shr_s":
            b = self.stack.pop_i32() & 0x1F
            a = self.stack.pop_i32()
            self.stack.push_i32(a >> b)
        elif m == "i32.shr_u":
            b = self.stack.pop_i32() & 0x1F
            a = self.stack.pop_i32() & 0xFFFFFFFF
            self.stack.push_i32(a >> b)

        # 6. Comparisons
        elif m == "i32.eqz":
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a == 0 else 0)
        elif m == "i32.eq":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a == b else 0)
        elif m == "i32.ne":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a != b else 0)
        elif m == "i32.lt_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a < b else 0)
        elif m == "i32.lt_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            self.stack.push_i32(1 if a < b else 0)
        elif m == "i32.gt_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a > b else 0)
        elif m == "i32.gt_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            self.stack.push_i32(1 if a > b else 0)
        elif m == "i32.le_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a <= b else 0)
        elif m == "i32.le_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            self.stack.push_i32(1 if a <= b else 0)
        elif m == "i32.ge_s":
            b = self.stack.pop_i32()
            a = self.stack.pop_i32()
            self.stack.push_i32(1 if a >= b else 0)
        elif m == "i32.ge_u":
            b = self.stack.pop_i32() & 0xFFFFFFFF
            a = self.stack.pop_i32() & 0xFFFFFFFF
            self.stack.push_i32(1 if a >= b else 0)

        # 7. Control Flow
        elif m == "nop":
            pass
        elif m == "unreachable":
            raise VMError("Executed unreachable instruction")

        elif m == "block":
            end_pc = frame.matching_end.get(frame.pc, len(frame.instructions) - 1)
            frame.labels.append(
                ControlLabel(
                    kind="block",
                    start_pc=frame.pc,
                    continuation_pc=end_pc + 1,
                    end_pc=end_pc,
                    stack_height=len(self.stack),
                )
            )

        elif m == "loop":
            end_pc = frame.matching_end.get(frame.pc, len(frame.instructions) - 1)
            frame.labels.append(
                ControlLabel(
                    kind="loop",
                    start_pc=frame.pc,
                    continuation_pc=frame.pc + 1,
                    end_pc=end_pc,
                    stack_height=len(self.stack),
                )
            )

        elif m == "if":
            cond = self.stack.pop_i32()
            end_pc = frame.matching_end.get(frame.pc, len(frame.instructions) - 1)
            else_pc = frame.matching_else.get(frame.pc)

            frame.labels.append(
                ControlLabel(
                    kind="if",
                    start_pc=frame.pc,
                    continuation_pc=end_pc + 1,
                    end_pc=end_pc,
                    stack_height=len(self.stack),
                )
            )

            if cond == 0:
                if else_pc is not None:
                    frame.pc = else_pc + 1
                else:
                    frame.labels.pop()
                    frame.pc = end_pc + 1

        elif m == "else":
            if frame.labels and frame.labels[-1].kind == "if":
                label = frame.labels.pop()
                frame.pc = label.end_pc + 1
            else:
                frame.pc += 1

        elif m == "end":
            if frame.labels:
                frame.labels.pop()
            else:
                self.call_stack.pop()

        elif m == "br":
            depth = instr.operands
            label = frame.labels[-(depth + 1)]
            if label.kind == "loop":
                if depth > 0:
                    frame.labels = frame.labels[:-depth]
                frame.pc = label.continuation_pc
            else:
                frame.labels = frame.labels[: -(depth + 1)]
                frame.pc = label.continuation_pc

        elif m == "br_if":
            depth = instr.operands
            cond = self.stack.pop_i32()
            if cond != 0:
                label = frame.labels[-(depth + 1)]
                if label.kind == "loop":
                    if depth > 0:
                        frame.labels = frame.labels[:-depth]
                    frame.pc = label.continuation_pc
                else:
                    frame.labels = frame.labels[: -(depth + 1)]
                    frame.pc = label.continuation_pc

        elif m == "return":
            self.call_stack.pop()

        elif m == "call":
            target_fn_idx = instr.operands
            target_sig = self.module.get_function_type(target_fn_idx)
            call_args = []
            for _ in range(len(target_sig.params)):
                call_args.insert(0, self.stack.pop().value)

            # Advance current frame PC so when return happens, it resumes at next instruction
            frame.pc += 1
            self.invoke(target_fn_idx, call_args)

        elif m == "drop":
            self.stack.pop()

        return mem_diff

    def run_to_completion(self, max_steps: int = 50000) -> List[int | float]:
        """Execute continuously until all call frames return."""
        while self.is_running and self.step_counter < max_steps:
            self.step()

        if self.step_counter >= max_steps:
            raise VMError(f"Execution exceeded maximum step limit ({max_steps})")

        results = []
        while not self.stack.is_empty():
            results.insert(0, self.stack.pop().value)
        return results

    def trace_execution(self, max_steps: int = 5000) -> List[StepTrace]:
        """Record all step traces until execution completes."""
        traces: List[StepTrace] = []
        while self.is_running and self.step_counter < max_steps:
            trace = self.step()
            traces.append(trace)
        return traces
