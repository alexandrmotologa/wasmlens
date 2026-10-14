"""Exporters for Control-Flow Graphs: DOT, Mermaid, ASCII, and JSON."""

from __future__ import annotations

import json
from typing import Dict

from wasmlens.cfg.basic_block import ControlFlowGraph, EdgeType


def to_dot(cfg: ControlFlowGraph) -> str:
    """Export ControlFlowGraph to Graphviz DOT format."""
    lines = [
        f'digraph "CFG_{cfg.func_name}" {{',
        '  graph [rankdir=TB, bgcolor="transparent", fontname="Courier"];',
        '  node [shape=box, style="filled,rounded", fontname="Courier", fontsize=10, fillcolor="#1e1e2e", fontcolor="#cdd6f4", color="#313244"];',
        '  edge [fontname="Courier", fontsize=9, fontcolor="#a6adc8"];',
    ]

    for b in cfg.blocks:
        # Build node label with instructions
        instr_lines = []
        for instr in b.instructions:
            ops = f" {instr.operands}" if instr.operands is not None else ""
            instr_lines.append(f"{instr.mnemonic}{ops}")
        body_text = "\\l".join(instr_lines) + "\\l" if instr_lines else "(empty)\\l"
        label = f"{{<b>{b.id}</b> ({b.block_type})\\l|{body_text}}}"

        # Node styling based on type
        fillcolor = "#1e1e2e"
        bordercolor = "#313244"
        if b.block_type == "entry":
            bordercolor = "#a6e3a1"  # green
        elif b.block_type == "exit":
            bordercolor = "#f38ba8"  # red
        elif b.block_type == "loop_header":
            bordercolor = "#89b4fa"  # blue

        lines.append(
            f'  "{b.id}" [shape=record, fillcolor="{fillcolor}", color="{bordercolor}", label="{label}"];'
        )

    for e in cfg.edges:
        color = "#6c7086"
        style = "solid"
        if e.edge_type == EdgeType.BRANCH_TRUE:
            color = "#a6e3a1"  # green
        elif e.edge_type == EdgeType.BRANCH_FALSE:
            color = "#f38ba8"  # red
        elif e.edge_type == EdgeType.LOOP_BACK:
            color = "#89b4fa"  # blue
            style = "dashed"
        elif e.edge_type == EdgeType.RETURN:
            color = "#cba6f7"  # mauve

        label_attr = f', label="{e.label}"' if e.label else ""
        lines.append(f'  "{e.source_id}" -> "{e.target_id}" [color="{color}", style="{style}"{label_attr}];')

    lines.append("}")
    return "\n".join(lines)


def to_mermaid(cfg: ControlFlowGraph) -> str:
    """Export ControlFlowGraph to Mermaid flowchart TD format."""
    lines = ["flowchart TD"]

    for b in cfg.blocks:
        instr_lines = [f"{i.mnemonic} {i.operands or ''}".strip() for i in b.instructions[:4]]
        if len(b.instructions) > 4:
            instr_lines.append(f"... +{len(b.instructions) - 4} more")
        body_preview = "<br/>".join(instr_lines) if instr_lines else "empty"
        lines.append(f'  {b.id}["<b>{b.id}</b><br/>{body_preview}"]')

    for e in cfg.edges:
        label = f"|{e.label}|" if e.label else ""
        lines.append(f"  {e.source_id} -->{label} {e.target_id}")

    return "\n".join(lines)


def to_ascii(cfg: ControlFlowGraph) -> str:
    """Generate a clean ASCII overview of the Control-Flow Graph."""
    lines = [
        f"Control-Flow Graph for ${cfg.func_name} (Index: {cfg.func_index})",
        "=" * 50,
    ]

    # Map out outgoing edges per block
    out_edges: Dict[str, list] = {}
    for e in cfg.edges:
        out_edges.setdefault(e.source_id, []).append(e)

    for b in cfg.blocks:
        tag = f"[{b.block_type.upper()}]" if b.block_type != "normal" else ""
        lines.append(f"+--- Block {b.id} {tag} (Depth: {b.depth}) ---+")
        if b.instructions:
            for instr in b.instructions:
                ops = f" {instr.operands}" if instr.operands is not None else ""
                lines.append(f"|  0x{instr.offset:04X}: {instr.mnemonic}{ops}")
        else:
            lines.append("|  (empty)")

        edges = out_edges.get(b.id, [])
        if edges:
            lines.append("+-----------------------------------+")
            for e in edges:
                lbl = f" ({e.label})" if e.label else ""
                lines.append(f"   |--> [{e.edge_type.value}] -> {e.target_id}{lbl}")
        else:
            lines.append("+-----------------------------------+")
        lines.append("")

    return "\n".join(lines)


def to_json(cfg: ControlFlowGraph) -> str:
    """Export ControlFlowGraph to a JSON string."""
    return json.dumps(cfg.to_dict(), indent=2)
