"""Control-Flow Graph (CFG) builder for WebAssembly function bodies."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from wasmlens.cfg.basic_block import (
    BasicBlock,
    ControlFlowGraph,
    Edge,
    EdgeType,
)
from wasmlens.parser.types import FunctionBody, Instruction, WasmModule


class CFGBuilder:
    """Constructs basic blocks and edge connections from WebAssembly bytecode."""

    def __init__(self, module: WasmModule) -> None:
        self.module = module

    def build_cfg(self, func_idx: int) -> ControlFlowGraph:
        imported_count = self.module.imported_func_count
        if func_idx < imported_count:
            # Imported function has no body
            fn_name = self.module.get_function_name(func_idx)
            entry = BasicBlock(id="bb_0", start_offset=0, end_offset=0, block_type="entry")
            return ControlFlowGraph(
                func_index=func_idx,
                func_name=fn_name,
                entry_block_id="bb_0",
                blocks=[entry],
                edges=[],
            )

        body_idx = func_idx - imported_count
        if body_idx >= len(self.module.codes):
            raise IndexError(f"Function index {func_idx} out of bounds")

        body = self.module.codes[body_idx]
        fn_name = self.module.get_function_name(func_idx)

        return self._build_from_instructions(func_idx, fn_name, body.instructions)

    def _build_from_instructions(
        self,
        func_idx: int,
        fn_name: str,
        instructions: List[Instruction],
    ) -> ControlFlowGraph:
        if not instructions:
            entry = BasicBlock(id="bb_0", start_offset=0, end_offset=0, block_type="entry")
            return ControlFlowGraph(
                func_index=func_idx,
                func_name=fn_name,
                entry_block_id="bb_0",
                blocks=[entry],
                edges=[],
            )

        blocks: List[BasicBlock] = []
        edges: List[Edge] = []
        block_counter = 0

        def create_block(block_type: str = "normal", depth: int = 0) -> BasicBlock:
            nonlocal block_counter
            bid = f"bb_{block_counter}"
            block_counter += 1
            bb = BasicBlock(
                id=bid,
                start_offset=0,
                end_offset=0,
                depth=depth,
                block_type=block_type,
            )
            blocks.append(bb)
            return bb

        exit_block = create_block(block_type="exit", depth=0)

        # Control stack elements:
        # { "type": "block"|"loop"|"if", "target_block": BasicBlock, "end_block": BasicBlock, "else_block": ... }
        control_stack: List[dict] = []

        current_block = create_block(block_type="entry", depth=0)
        entry_block_id = current_block.id

        # Function end block
        fn_end_block = exit_block
        control_stack.append({
            "type": "function",
            "target_block": fn_end_block,
            "end_block": fn_end_block,
        })

        for i, instr in enumerate(instructions):
            m = instr.mnemonic
            current_block.instructions.append(instr)
            if not current_block.start_offset and instr.offset:
                current_block.start_offset = instr.offset
            current_block.end_offset = instr.offset + instr.size

            if m == "block":
                end_block = create_block(depth=len(control_stack))
                control_stack.append({
                    "type": "block",
                    "target_block": end_block,
                    "end_block": end_block,
                })
                # Fallthrough to block contents
                next_block = create_block(depth=len(control_stack))
                edges.append(Edge(current_block.id, next_block.id, EdgeType.FALLTHROUGH))
                current_block = next_block

            elif m == "loop":
                loop_header = create_block(block_type="loop_header", depth=len(control_stack))
                end_block = create_block(depth=len(control_stack))
                control_stack.append({
                    "type": "loop",
                    "target_block": loop_header,  # br jumps to header
                    "end_block": end_block,       # fallthrough at end goes to end_block
                })
                edges.append(Edge(current_block.id, loop_header.id, EdgeType.FALLTHROUGH))
                current_block = loop_header

            elif m == "if":
                then_block = create_block(depth=len(control_stack))
                else_block = create_block(depth=len(control_stack))
                end_block = create_block(depth=len(control_stack))
                control_stack.append({
                    "type": "if",
                    "target_block": end_block,
                    "end_block": end_block,
                    "else_block": else_block,
                    "has_else": False,
                })
                edges.append(Edge(current_block.id, then_block.id, EdgeType.BRANCH_TRUE))
                edges.append(Edge(current_block.id, else_block.id, EdgeType.BRANCH_FALSE))
                current_block = then_block

            elif m == "else":
                if control_stack and control_stack[-1]["type"] == "if":
                    frame = control_stack[-1]
                    frame["has_else"] = True
                    # Then block ends, jumps to end_block
                    edges.append(Edge(current_block.id, frame["end_block"].id, EdgeType.FALLTHROUGH))
                    current_block = frame["else_block"]

            elif m == "end":
                if control_stack:
                    frame = control_stack.pop()
                    if frame["type"] in ("block", "loop"):
                        edges.append(Edge(current_block.id, frame["end_block"].id, EdgeType.FALLTHROUGH))
                        current_block = frame["end_block"]
                    elif frame["type"] == "if":
                        if not frame.get("has_else", False):
                            # Else block was empty fallthrough directly to end
                            edges.append(Edge(frame["else_block"].id, frame["end_block"].id, EdgeType.FALLTHROUGH))
                        edges.append(Edge(current_block.id, frame["end_block"].id, EdgeType.FALLTHROUGH))
                        current_block = frame["end_block"]
                    elif frame["type"] == "function":
                        edges.append(Edge(current_block.id, exit_block.id, EdgeType.RETURN))

            elif m == "br":
                depth = instr.operands
                if depth < len(control_stack):
                    target_frame = control_stack[-(depth + 1)]
                    tgt_block = target_frame["target_block"]
                    e_type = EdgeType.LOOP_BACK if target_frame["type"] == "loop" else EdgeType.BRANCH_TRUE
                    edges.append(Edge(current_block.id, tgt_block.id, e_type))

                # After unconditional br, create new block for remaining dead/followup code
                next_block = create_block(depth=len(control_stack))
                current_block = next_block

            elif m == "br_if":
                depth = instr.operands
                if depth < len(control_stack):
                    target_frame = control_stack[-(depth + 1)]
                    tgt_block = target_frame["target_block"]
                    e_type = EdgeType.LOOP_BACK if target_frame["type"] == "loop" else EdgeType.BRANCH_TRUE
                    edges.append(Edge(current_block.id, tgt_block.id, e_type, label="true"))

                fallthrough_block = create_block(depth=len(control_stack))
                edges.append(Edge(current_block.id, fallthrough_block.id, EdgeType.BRANCH_FALSE, label="false"))
                current_block = fallthrough_block

            elif m == "br_table":
                targets, default_tgt = instr.operands
                for idx, t in enumerate(targets):
                    if t < len(control_stack):
                        t_block = control_stack[-(t + 1)]["target_block"]
                        edges.append(Edge(current_block.id, t_block.id, EdgeType.JUMP_TABLE, label=f"case {idx}"))
                if default_tgt < len(control_stack):
                    def_block = control_stack[-(default_tgt + 1)]["target_block"]
                    edges.append(Edge(current_block.id, def_block.id, EdgeType.JUMP_TABLE, label="default"))

                next_block = create_block(depth=len(control_stack))
                current_block = next_block

            elif m in ("return", "unreachable"):
                edges.append(Edge(current_block.id, exit_block.id, EdgeType.RETURN))
                next_block = create_block(depth=len(control_stack))
                current_block = next_block

        # Filter out empty intermediate blocks that have no instructions and no edges
        # Keep entry and exit blocks
        connected_ids = set()
        for e in edges:
            connected_ids.add(e.source_id)
            connected_ids.add(e.target_id)
        connected_ids.add(entry_block_id)

        valid_blocks = [
            b for b in blocks
            if b.instructions or b.id in connected_ids or b.id == exit_block.id
        ]

        return ControlFlowGraph(
            func_index=func_idx,
            func_name=fn_name,
            entry_block_id=entry_block_id,
            blocks=valid_blocks,
            edges=edges,
        )
