"""Activation frames and control labels for WebAssembly execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from wasmlens.emulator.stack import WasmValue
from wasmlens.parser.types import Instruction, ValueType


@dataclass
class ControlLabel:
    """Structured control construct tracking target PCs and stack heights."""
    kind: str  # "block", "loop", "if"
    start_pc: int
    continuation_pc: int  # For loop: start_pc; for block/if: end_pc
    end_pc: int
    stack_height: int
    result_type: Optional[ValueType] = None


@dataclass
class ActivationFrame:
    """Call stack activation frame."""
    func_index: int
    func_name: str
    locals: List[WasmValue]
    instructions: List[Instruction]
    pc: int = 0
    labels: List[ControlLabel] = field(default_factory=list)

    # Precomputed control structure jump tables
    matching_end: Dict[int, int] = field(default_factory=dict)
    matching_else: Dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._precompute_jumps()

    def _precompute_jumps(self) -> None:
        """Pair opening constructs (block, loop, if) with matching else and end."""
        stack: List[tuple[str, int]] = []
        for i, instr in enumerate(self.instructions):
            m = instr.mnemonic
            if m in ("block", "loop", "if"):
                stack.append((m, i))
            elif m == "else":
                if stack and stack[-1][0] == "if":
                    if_start = stack[-1][1]
                    self.matching_else[if_start] = i
            elif m == "end":
                if stack:
                    kind, start_pc = stack.pop()
                    self.matching_end[start_pc] = i
                    if start_pc in self.matching_else:
                        else_pc = self.matching_else[start_pc]
                        self.matching_end[else_pc] = i

    @property
    def current_instruction(self) -> Optional[Instruction]:
        if 0 <= self.pc < len(self.instructions):
            return self.instructions[self.pc]
        return None

    def snapshot_locals(self) -> List[dict]:
        return [
            {"index": idx, "type": loc.type.to_wat(), "value": loc.value}
            for idx, loc in enumerate(self.locals)
        ]
