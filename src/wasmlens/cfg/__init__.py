"""Control-Flow Graph package for WebAssembly modules."""

from wasmlens.cfg.analyzer import CFGAnalysisResult, CFGAnalyzer, NaturalLoop
from wasmlens.cfg.basic_block import (
    BasicBlock,
    ControlFlowGraph,
    Edge,
    EdgeType,
)
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.cfg.export import to_ascii, to_dot, to_json, to_mermaid

__all__ = [
    "BasicBlock",
    "ControlFlowGraph",
    "Edge",
    "EdgeType",
    "CFGBuilder",
    "CFGAnalyzer",
    "CFGAnalysisResult",
    "NaturalLoop",
    "to_dot",
    "to_mermaid",
    "to_ascii",
    "to_json",
]
