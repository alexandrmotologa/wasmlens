"""Authentic WebAssembly 2.0 bytecode emulator with step-by-step tracing and advanced debugging."""

from __future__ import annotations

import copy
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

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
    hit_breakpoint: bool = False
    hit_watchpoint: Optional[str] = None


@dataclass
class ExecutionSnapshot:
    """Complete frozen virtual machine state snapshot for time-travel debugging."""
    step_counter: int
    call_stack: List[ActivationFrame]
    stack: List[WasmValue]
    memory: bytearray
    globals: List[WasmValue]


class WasmVM:
    """WebAssembly 2.0 virtual machine runtime with breakpoints, watchpoints and time-travel debugging."""

    def __init__(self, module: WasmModule) -> None:
        self.module = module
        self.inspector = MemoryInspector(module)
        self.memory: bytearray = self.inspector.buffer
        self.stack = OperandStack()
        self.call_stack: List[ActivationFrame] = []
        self.globals: List[WasmValue] = []
        self.step_counter = 0

        # Debugger state
        self.breakpoints: Set[Tuple[int, int]] = set()  # (func_index, pc)
        self.read_watchpoints: Set[int] = set()         # memory addresses
        self.write_watchpoints: Set[int] = set()        # memory addresses
        self.history: List[ExecutionSnapshot] = []
        self.history_limit: int = 1000

        self._init_globals()

    def _init_globals(self) -> None:
        """Initialize globals by executing init expressions."""
        for g in self.module.globals:
            val = 0
            for instr in g.init_expr:
                if instr.mnemonic in ("i32.const", "i64.const", "f32.const", "f64.const"):
                    val = instr.operands
            self.globals.append(WasmValue(g.type.valtype, val))

    def add_breakpoint(self, func_index: int, pc: int) -> None:
        """Add an execution breakpoint at (func_index, pc)."""
        self.breakpoints.add((func_index, pc))

    def remove_breakpoint(self, func_index: int, pc: int) -> None:
        """Remove a breakpoint at (func_index, pc)."""
        self.breakpoints.discard((func_index, pc))

    def clear_breakpoints(self) -> None:
        """Remove all breakpoints."""
        self.breakpoints.clear()

    def add_watchpoint(self, address: int, on_read: bool = False, on_write: bool = True) -> None:
        """Add a memory watchpoint on read, write, or both."""
        if on_read:
            self.read_watchpoints.add(address)
        if on_write:
            self.write_watchpoints.add(address)

    def remove_watchpoint(self, address: int) -> None:
        """Remove memory watchpoints at address."""
        self.read_watchpoints.discard(address)
        self.write_watchpoints.discard(address)

    def clear_watchpoints(self) -> None:
        """Clear all watchpoints."""
        self.read_watchpoints.clear()
        self.write_watchpoints.clear()

    def create_snapshot(self) -> ExecutionSnapshot:
        """Capture an immutable snapshot of the current VM state."""
        cloned_frames: List[ActivationFrame] = []
        for f in self.call_stack:
            copied_frame = ActivationFrame(
                func_index=f.func_index,
                func_name=f.func_name,
                locals=[WasmValue(v.type, v.value) for v in f.locals],
                instructions=f.instructions,
                pc=f.pc,
                labels=[
                    ControlLabel(
                        kind=lbl.kind,
                        start_pc=lbl.start_pc,
                        continuation_pc=lbl.continuation_pc,
                        end_pc=lbl.end_pc,
                        stack_height=lbl.stack_height,
                        result_type=lbl.result_type,
                    )
                    for lbl in f.labels
                ],
            )
            copied_frame.matching_end = dict(f.matching_end)
            copied_frame.matching_else = dict(f.matching_else)
            cloned_frames.append(copied_frame)

        cloned_stack = [WasmValue(v.type, v.value) for v in self.stack._stack]
        cloned_memory = bytearray(self.memory)
        cloned_globals = [WasmValue(v.type, v.value) for v in self.globals]

        return ExecutionSnapshot(
            step_counter=self.step_counter,
            call_stack=cloned_frames,
            stack=cloned_stack,
            memory=cloned_memory,
            globals=cloned_globals,
        )

    def restore_snapshot(self, snap: ExecutionSnapshot) -> None:
        """Restore virtual machine state from a recorded snapshot."""
        self.step_counter = snap.step_counter
        self.call_stack = []
        for f in snap.call_stack:
            restored_frame = ActivationFrame(
                func_index=f.func_index,
                func_name=f.func_name,
                locals=[WasmValue(v.type, v.value) for v in f.locals],
                instructions=f.instructions,
                pc=f.pc,
                labels=[
                    ControlLabel(
                        kind=lbl.kind,
                        start_pc=lbl.start_pc,
                        continuation_pc=lbl.continuation_pc,
                        end_pc=lbl.end_pc,
                        stack_height=lbl.stack_height,
                        result_type=lbl.result_type,
                    )
                    for lbl in f.labels
                ],
            )
            restored_frame.matching_end = dict(f.matching_end)
            restored_frame.matching_else = dict(f.matching_else)
            self.call_stack.append(restored_frame)

        self.stack._stack = [WasmValue(v.type, v.value) for v in snap.stack]
        self.memory[:] = snap.memory
        self.globals = [WasmValue(v.type, v.value) for v in snap.globals]

    def step_backward(self) -> Optional[StepTrace]:
        """Rewind virtual machine by one execution step."""
        if not self.history:
            return None
        snapshot = self.history.pop()
        self.restore_snapshot(snapshot)

        if not self.call_stack:
            return StepTrace(
                step_number=self.step_counter,
                func_index=0,
                func_name="",
                pc=0,
                instruction_mnemonic="halted",
                instruction_operands="",
                instruction_offset=0,
                stack_before=[],
                stack_after=self.stack.snapshot(),
                locals_snapshot=[],
                is_halted=True,
            )

        frame = self.call_stack[-1]
        instr = (
            frame.instructions[frame.pc]
            if frame.pc < len(frame.instructions)
            else Instruction(opcode=0x0B, mnemonic="end")
        )
        return StepTrace(
            step_number=self.step_counter,
            func_index=frame.func_index,
            func_name=frame.func_name,
            pc=frame.pc,
            instruction_mnemonic=instr.mnemonic,
            instruction_operands=str(instr.operands) if instr.operands is not None else "",
            instruction_offset=instr.offset,
            stack_before=self.stack.snapshot(),
            stack_after=self.stack.snapshot(),
            locals_snapshot=frame.snapshot_locals(),
            is_halted=not self.is_running,
        )

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
        self.history.clear()

    @property
    def is_running(self) -> bool:
        return len(self.call_stack) > 0

    def step(self) -> StepTrace:
        """Execute a single bytecode instruction and return execution trace."""
        if not self.call_stack:
            raise VMError("Virtual machine is halted; no active call frame")

        # Record snapshot for time-travel
        snapshot = self.create_snapshot()
        self.history.append(snapshot)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

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

        mem_diff, watchpoint_hit = self._execute_instruction(frame, instr)

        # Advance PC if instruction didn't perform a jump or function call
        if self.call_stack and self.call_stack[-1] is frame:
            if frame.pc == pc_before:
                frame.pc += 1

        stack_after = self.stack.snapshot()
        locals_snap = frame.snapshot_locals()

        # Check if next instruction is on a breakpoint
        hit_bp = False
        if self.call_stack:
            next_frame = self.call_stack[-1]
            if (next_frame.func_index, next_frame.pc) in self.breakpoints:
                hit_bp = True

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
            hit_breakpoint=hit_bp,
            hit_watchpoint=watchpoint_hit,
        )

    def _check_watchpoint(self, addr: int, size: int, mode: str) -> Optional[str]:
        target_set = self.read_watchpoints if mode == "read" else self.write_watchpoints
        if not target_set:
            return None
        for b_offset in range(size):
            if (addr + b_offset) in target_set:
                return f"{mode.upper()} watchpoint hit at 0x{(addr + b_offset):06X}"
        return None

    def _execute_instruction(
        self, frame: ActivationFrame, instr: Instruction
    ) -> Tuple[Optional[MemoryDiff], Optional[str]]:
        m = instr.mnemonic
        mem_diff: Optional[MemoryDiff] = None
        watchpoint_hit: Optional[str] = None

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
        elif m in (
            "i32.load",
            "i64.load",
            "f32.load",
            "f64.load",
            "i32.load8_s",
            "i32.load8_u",
            "i32.load16_s",
            "i32.load16_u",
        ):
            align, offset = instr.operands
            addr = self.stack.pop_i32() + offset
            if addr < 0 or addr >= len(self.memory):
                raise VMError(f"Out of bounds memory access at 0x{addr:08X}")

            read_size = 4
            if m in ("i64.load", "f64.load"):
                read_size = 8
            elif m in ("i32.load8_s", "i32.load8_u"):
                read_size = 1
            elif m in ("i32.load16_s", "i32.load16_u"):
                read_size = 2

            watchpoint_hit = self._check_watchpoint(addr, read_size, "read")

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

            watchpoint_hit = self._check_watchpoint(addr, len(raw), "write")
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

            frame.pc += 1
            self.invoke(target_fn_idx, call_args)

        elif m == "drop":
            self.stack.pop()

        return mem_diff, watchpoint_hit

    def run_until_break(self, max_steps: int = 10000) -> Tuple[bool, Optional[str]]:
        """Run execution until a breakpoint is hit, watchpoint triggers, or VM halts.

        Returns (is_halted, stop_reason).
        """
        for _ in range(max_steps):
            if not self.is_running:
                return True, "halted"

            frame = self.call_stack[-1]
            if (frame.func_index, frame.pc) in self.breakpoints and self.step_counter > 0:
                return False, f"Breakpoint at func {frame.func_index} pc {frame.pc}"

            trace = self.step()
            if trace.hit_watchpoint:
                return False, trace.hit_watchpoint

            if not self.is_running:
                return True, "completed"

            # Check if next instruction is a breakpoint
            if self.call_stack:
                next_f = self.call_stack[-1]
                if (next_f.func_index, next_f.pc) in self.breakpoints:
                    return False, f"Breakpoint at func {next_f.func_index} pc {next_f.pc}"

        return False, "step_limit_reached"

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
