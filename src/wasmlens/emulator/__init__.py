"""Bytecode emulator package for WebAssembly modules."""

from wasmlens.emulator.frame import ActivationFrame, ControlLabel
from wasmlens.emulator.stack import OperandStack, VMError, WasmValue
from wasmlens.emulator.vm import MemoryDiff, StepTrace, WasmVM

__all__ = [
    "WasmVM",
    "OperandStack",
    "WasmValue",
    "VMError",
    "ActivationFrame",
    "ControlLabel",
    "StepTrace",
    "MemoryDiff",
]
