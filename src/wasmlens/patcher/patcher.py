"""Binary mutation engine and patcher for WebAssembly 2.0 modules."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional, Union

from wasmlens.parser.emitter import emit_wasm
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.opcodes import lookup_opcode
from wasmlens.parser.types import Instruction, WasmModule


class PatchError(ValueError):
    """Raised when patch operation is invalid."""
    pass


class WasmPatcher:
    """Modifies bytecode instructions in a WasmModule and serializes valid binaries."""

    def __init__(self, source: Union[WasmModule, bytes, str, Path]) -> None:
        if isinstance(source, WasmModule):
            self.module = copy.deepcopy(source)
        else:
            self.module = parse_wasm(source)

    def _get_body(self, func_index: int):
        imported_count = self.module.imported_func_count
        if func_index < imported_count:
            raise PatchError(f"Cannot patch imported function {func_index} (no code body)")
        body_idx = func_index - imported_count
        if body_idx >= len(self.module.codes):
            raise PatchError(f"Function index {func_index} out of bounds")
        return self.module.codes[body_idx]

    def patch_instruction(self, func_index: int, pc: int, new_instr: Instruction) -> None:
        """Replace the instruction at pc in function func_index."""
        body = self._get_body(func_index)
        if pc < 0 or pc >= len(body.instructions):
            raise PatchError(f"Instruction index {pc} out of range (0..{len(body.instructions)-1})")
        body.instructions[pc] = new_instr

    def patch_constant(self, func_index: int, pc: int, new_val: int | float) -> None:
        """Update immediate constant value for instruction at pc."""
        body = self._get_body(func_index)
        if pc < 0 or pc >= len(body.instructions):
            raise PatchError(f"Instruction index {pc} out of range")
        instr = body.instructions[pc]
        if not instr.mnemonic.endswith(".const"):
            raise PatchError(f"Instruction at pc={pc} ({instr.mnemonic}) is not a constant")
        body.instructions[pc] = Instruction(
            opcode=instr.opcode,
            mnemonic=instr.mnemonic,
            operands=new_val,
            offset=instr.offset,
            size=instr.size,
            prefix=instr.prefix,
        )

    def nop_instruction(self, func_index: int, pc: int) -> None:
        """Replace instruction at pc with a NOP (0x01)."""
        body = self._get_body(func_index)
        if pc < 0 or pc >= len(body.instructions):
            raise PatchError(f"Instruction index {pc} out of range")
        body.instructions[pc] = Instruction(opcode=0x01, mnemonic="nop", operands=None)

    def emit_binary(self) -> bytes:
        """Serialize patched module to authentic .wasm binary bytes."""
        return emit_wasm(self.module)

    def save(self, path: Union[str, Path]) -> None:
        """Save patched binary to disk."""
        target = Path(path)
        target.write_bytes(self.emit_binary())
