"""Static data-flow analyzer and stack-effect simulator for WebAssembly 2.0."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from wasmlens.parser.types import FunctionBody, FunctionType, Instruction, WasmModule


@dataclass
class InstructionDataflow:
    """Stack depth transformation and variable def-use attribution for an instruction."""
    pc: int
    mnemonic: str
    operands: str
    stack_pops: int
    stack_pushes: int
    stack_depth_in: int
    stack_depth_out: int
    reads_locals: List[int]
    writes_locals: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DataflowAnalysisResult:
    """Data-flow analysis summary for a function."""
    func_index: int
    func_name: str
    max_stack_depth: int
    instructions: List[InstructionDataflow]
    local_def_use: Dict[int, Dict[str, List[int]]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_index": self.func_index,
            "func_name": self.func_name,
            "max_stack_depth": self.max_stack_depth,
            "instructions": [i.to_dict() for i in self.instructions],
            "local_def_use": self.local_def_use,
        }


def get_instruction_stack_effect(
    instr: Instruction, module: Optional[WasmModule] = None
) -> Tuple[int, int]:
    """Calculate (pops, pushes) for any WebAssembly instruction."""
    m = instr.mnemonic

    # 1. Constants
    if m.endswith(".const"):
        return (0, 1)

    # 2. Variable access
    if m == "local.get":
        return (0, 1)
    if m == "local.set":
        return (1, 0)
    if m == "local.tee":
        return (1, 1)
    if m == "global.get":
        return (0, 1)
    if m == "global.set":
        return (1, 0)

    # 3. Memory
    if ".load" in m:
        return (1, 1)  # pops address, pushes value
    if ".store" in m:
        return (2, 0)  # pops address, pops value
    if m in ("memory.size",):
        return (0, 1)
    if m in ("memory.grow",):
        return (1, 1)

    # 4. Unary operations
    if m.endswith(".eqz") or m.endswith(".clz") or m.endswith(".ctz") or m.endswith(".popcnt"):
        return (1, 1)

    # 5. Binary arithmetic & comparisons
    binary_suffixes = (
        ".add", ".sub", ".mul", ".div_s", ".div_u", ".rem_s", ".rem_u",
        ".and", ".or", ".xor", ".shl", ".shr_s", ".shr_u", ".rotl", ".rotr",
        ".eq", ".ne", ".lt_s", ".lt_u", ".gt_s", ".gt_u", ".le_s", ".le_u", ".ge_s", ".ge_u",
    )
    if any(m.endswith(sfx) for sfx in binary_suffixes):
        return (2, 1)

    # 6. Drop / Select
    if m == "drop":
        return (1, 0)
    if m == "select":
        return (3, 1)

    # 7. Control Flow
    if m == "if":
        return (1, 0)
    if m == "br_if":
        return (1, 0)
    if m in ("block", "loop", "else", "end", "nop", "unreachable", "br"):
        return (0, 0)

    # 8. Function Calls
    if m == "call" and module is not None and isinstance(instr.operands, int):
        target_fn = instr.operands
        try:
            sig = module.get_function_type(target_fn)
            return (len(sig.params), len(sig.results))
        except Exception:
            return (0, 0)

    if m == "return":
        return (0, 0)

    return (0, 0)


def analyze_dataflow(
    module: WasmModule, func_index: int
) -> DataflowAnalysisResult:
    """Perform static data-flow and stack-effect simulation on a function."""
    imported_count = module.imported_func_count
    if func_index < imported_count:
        sig = module.get_function_type(func_index)
        return DataflowAnalysisResult(
            func_index=func_index,
            func_name=module.get_function_name(func_index),
            max_stack_depth=0,
            instructions=[],
            local_def_use={},
        )

    body_idx = func_index - imported_count
    body = module.codes[body_idx]
    sig = module.get_function_type(func_index)
    func_name = module.get_function_name(func_index)

    current_depth = 0
    max_depth = 0
    steps: List[InstructionDataflow] = []
    local_def_use: Dict[int, Dict[str, List[int]]] = {}

    # Initialize total locals count (params + locals)
    total_locals = len(sig.params) + sum(l.count for l in body.locals)
    for idx in range(total_locals):
        local_def_use[idx] = {"defs": [], "uses": []}
        if idx < len(sig.params):
            # Arguments are initially defined at entry
            local_def_use[idx]["defs"].append(-1)

    for pc, instr in enumerate(body.instructions):
        pops, pushes = get_instruction_stack_effect(instr, module)
        depth_in = current_depth
        depth_out = max(0, current_depth - pops) + pushes
        if depth_out > max_depth:
            max_depth = depth_out
        current_depth = depth_out

        reads: List[int] = []
        writes: List[int] = []

        if instr.mnemonic == "local.get" and isinstance(instr.operands, int):
            idx = instr.operands
            reads.append(idx)
            if idx in local_def_use:
                local_def_use[idx]["uses"].append(pc)
        elif instr.mnemonic == "local.set" and isinstance(instr.operands, int):
            idx = instr.operands
            writes.append(idx)
            if idx in local_def_use:
                local_def_use[idx]["defs"].append(pc)
        elif instr.mnemonic == "local.tee" and isinstance(instr.operands, int):
            idx = instr.operands
            writes.append(idx)
            if idx in local_def_use:
                local_def_use[idx]["defs"].append(pc)

        steps.append(
            InstructionDataflow(
                pc=pc,
                mnemonic=instr.mnemonic,
                operands=str(instr.operands) if instr.operands is not None else "",
                stack_pops=pops,
                stack_pushes=pushes,
                stack_depth_in=depth_in,
                stack_depth_out=depth_out,
                reads_locals=reads,
                writes_locals=writes,
            )
        )

    return DataflowAnalysisResult(
        func_index=func_index,
        func_name=func_name,
        max_stack_depth=max_depth,
        instructions=steps,
        local_def_use=local_def_use,
    )
