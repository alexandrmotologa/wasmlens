"""Basic block and edge data models for WebAssembly Control-Flow Graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from wasmlens.parser.types import Instruction


class EdgeType(Enum):
    """Semantic type of control transfer between basic blocks."""
    FALLTHROUGH = "fallthrough"
    BRANCH_TRUE = "branch_true"
    BRANCH_FALSE = "branch_false"
    LOOP_BACK = "loop_back"
    JUMP_TABLE = "jump_table"
    RETURN = "return"


@dataclass
class Edge:
    """Directed control-flow edge."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "label": self.label or self.edge_type.value,
        }


@dataclass
class BasicBlock:
    """Contiguous sequence of instructions with single entry and exit points."""
    id: str
    start_offset: int
    end_offset: int
    instructions: List[Instruction] = field(default_factory=list)
    depth: int = 0
    block_type: str = "normal"  # "entry", "normal", "loop_header", "exit"

    @property
    def terminator(self) -> Optional[Instruction]:
        if not self.instructions:
            return None
        return self.instructions[-1]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "instructions": [
                {
                    "opcode": instr.opcode,
                    "mnemonic": instr.mnemonic,
                    "operands": str(instr.operands) if instr.operands is not None else "",
                    "offset": instr.offset,
                    "size": instr.size,
                }
                for instr in self.instructions
            ],
            "depth": self.depth,
            "block_type": self.block_type,
        }


@dataclass
class ControlFlowGraph:
    """Complete Control-Flow Graph for a function."""
    func_index: int
    func_name: str
    entry_block_id: str
    blocks: List[BasicBlock] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def get_block(self, block_id: str) -> Optional[BasicBlock]:
        for b in self.blocks:
            if b.id == block_id:
                return b
        return None

    def to_dict(self) -> dict:
        return {
            "func_index": self.func_index,
            "func_name": self.func_name,
            "entry_block_id": self.entry_block_id,
            "blocks": [b.to_dict() for b in self.blocks],
            "edges": [e.to_dict() for e in self.edges],
        }
