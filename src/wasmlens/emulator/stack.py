"""Operand stack implementation with WebAssembly 2.0 type enforcement."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, List

from wasmlens.parser.types import ValueType


class VMError(RuntimeError):
    """Raised on WebAssembly VM runtime error (trap)."""
    pass


@dataclass
class WasmValue:
    """Typed WebAssembly runtime value."""
    type: ValueType
    value: int | float

    def __repr__(self) -> str:
        return f"{self.type.to_wat()}({self.value})"


class OperandStack:
    """LIFO operand stack for WebAssembly execution."""

    def __init__(self) -> None:
        self._stack: List[WasmValue] = []

    def __len__(self) -> int:
        return len(self._stack)

    def is_empty(self) -> bool:
        return len(self._stack) == 0

    def push(self, val: WasmValue) -> None:
        self._stack.append(val)

    def push_i32(self, val: int) -> None:
        # Wrap into signed 32-bit integer range
        val = val & 0xFFFFFFFF
        if val >= 0x80000000:
            val -= 0x100000000
        self._stack.append(WasmValue(ValueType.I32, val))

    def push_i64(self, val: int) -> None:
        val = val & 0xFFFFFFFFFFFFFFFF
        if val >= 0x8000000000000000:
            val -= 0x10000000000000000
        self._stack.append(WasmValue(ValueType.I64, val))

    def push_f32(self, val: float) -> None:
        self._stack.append(WasmValue(ValueType.F32, float(val)))

    def push_f64(self, val: float) -> None:
        self._stack.append(WasmValue(ValueType.F64, float(val)))

    def pop(self) -> WasmValue:
        if not self._stack:
            raise VMError("Stack underflow")
        return self._stack.pop()

    def pop_i32(self) -> int:
        v = self.pop()
        return int(v.value)

    def pop_i64(self) -> int:
        v = self.pop()
        return int(v.value)

    def pop_f32(self) -> float:
        v = self.pop()
        return float(v.value)

    def pop_f64(self) -> float:
        v = self.pop()
        return float(v.value)

    def peek(self) -> WasmValue:
        if not self._stack:
            raise VMError("Stack underflow on peek")
        return self._stack[-1]

    def snapshot(self) -> List[dict]:
        """Serialize stack items for UI and step debugger."""
        return [
            {"type": v.type.to_wat(), "value": v.value}
            for v in self._stack
        ]
