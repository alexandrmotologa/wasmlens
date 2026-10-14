"""Control-Flow Graph analysis: dominators, loops, reachability, and complexity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

import networkx as nx

from wasmlens.cfg.basic_block import ControlFlowGraph, EdgeType


@dataclass
class NaturalLoop:
    """Natural loop representation detected in the CFG."""
    header_id: str
    latch_id: str
    nodes: Set[str] = field(default_factory=set)


@dataclass
class CFGAnalysisResult:
    """Summary of structural CFG properties."""
    block_count: int
    edge_count: int
    cyclomatic_complexity: int
    immediate_dominators: Dict[str, str]
    natural_loops: List[NaturalLoop]
    reachable_blocks: Set[str]
    dead_blocks: Set[str]


class CFGAnalyzer:
    """Analyzes structural properties of a ControlFlowGraph."""

    def __init__(self, cfg: ControlFlowGraph) -> None:
        self.cfg = cfg
        self.graph = nx.DiGraph()
        for b in cfg.blocks:
            self.graph.add_node(b.id, block_type=b.block_type)
        for e in cfg.edges:
            self.graph.add_edge(e.source_id, e.target_id, type=e.edge_type.value)

    def analyze(self) -> CFGAnalysisResult:
        entry = self.cfg.entry_block_id
        all_blocks = {b.id for b in self.cfg.blocks}

        # Reachability
        if entry in self.graph:
            reachable = nx.descendants(self.graph, entry) | {entry}
        else:
            reachable = set()
        dead = all_blocks - reachable

        # Dominators on reachable subgraph
        subgraph = self.graph.subgraph(reachable).copy()
        try:
            idom = nx.immediate_dominators(subgraph, entry) if reachable else {}
        except Exception:
            idom = {}

        # Natural loop detection (back-edges u -> v where v dominates u)
        # Dominator tree check: v dominates u if v is an ancestor of u in idom tree
        natural_loops: List[NaturalLoop] = []
        for u, v, data in subgraph.edges(data=True):
            if self._dominates(v, u, idom):
                # Back-edge found! Find loop nodes
                loop_nodes = self._find_loop_nodes(v, u, subgraph)
                natural_loops.append(NaturalLoop(header_id=v, latch_id=u, nodes=loop_nodes))

        # Cyclomatic complexity: E - N + 2
        e_count = len(subgraph.edges)
        n_count = len(subgraph.nodes)
        cc = max(1, e_count - n_count + 2)

        return CFGAnalysisResult(
            block_count=len(self.cfg.blocks),
            edge_count=len(self.cfg.edges),
            cyclomatic_complexity=cc,
            immediate_dominators=idom,
            natural_loops=natural_loops,
            reachable_blocks=reachable,
            dead_blocks=dead,
        )

    def _dominates(self, v: str, u: str, idom: Dict[str, str]) -> bool:
        """Check if node v dominates node u using the immediate dominator tree."""
        if v == u:
            return True
        curr = u
        visited = set()
        while curr in idom and curr != idom[curr] and curr not in visited:
            visited.add(curr)
            curr = idom[curr]
            if curr == v:
                return True
        return False

    def _find_loop_nodes(self, header: str, latch: str, graph: nx.DiGraph) -> Set[str]:
        """Find all nodes in the natural loop defined by back-edge latch -> header."""
        loop_nodes: Set[str] = {header, latch}
        stack = [latch]
        while stack:
            curr = stack.pop()
            for pred in graph.predecessors(curr):
                if pred not in loop_nodes:
                    loop_nodes.add(pred)
                    stack.append(pred)
        return loop_nodes
