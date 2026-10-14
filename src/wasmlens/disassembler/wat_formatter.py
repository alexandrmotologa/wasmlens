"""WebAssembly Text format (WAT) disassembler."""

from __future__ import annotations

from typing import List, Optional

from wasmlens.parser.types import (
    ExternalKind,
    FunctionBody,
    Instruction,
    ValueType,
    WasmModule,
)


def format_instruction(instr: Instruction, indent_level: int = 0) -> str:
    """Format an instruction with appropriate indentation and operands."""
    indent = "  " * indent_level
    mnemonic = instr.mnemonic

    if instr.operands is None:
        return f"{indent}{mnemonic}"

    if mnemonic in ("block", "loop", "if"):
        # block type
        bt = instr.operands
        if bt == ValueType.EMPTY_BLOCK:
            return f"{indent}{mnemonic}"
        elif isinstance(bt, ValueType):
            return f"{indent}{mnemonic} (result {bt.to_wat()})"
        else:
            return f"{indent}{mnemonic} (type {bt})"

    if mnemonic == "br_table":
        targets, default_tgt = instr.operands
        t_str = " ".join(str(t) for t in targets)
        return f"{indent}br_table {t_str} {default_tgt}"

    if mnemonic == "call_indirect":
        type_idx, table_idx = instr.operands
        return f"{indent}call_indirect (type {type_idx})"

    if mnemonic.startswith(("i32.load", "i64.load", "f32.load", "f64.load", "i32.store", "i64.store", "f32.store", "f64.store")):
        align, offset = instr.operands
        parts = [mnemonic]
        if offset != 0:
            parts.append(f"offset={offset}")
        if align != 0:
            parts.append(f"align={align}")
        return f"{indent}{' '.join(parts)}"

    if isinstance(instr.operands, (list, tuple)):
        ops = " ".join(str(o) for o in instr.operands)
        return f"{indent}{mnemonic} {ops}"

    return f"{indent}{mnemonic} {instr.operands}"


def disassemble_function(module: WasmModule, func_idx: int) -> str:
    """Disassemble a single function into structured WAT representation."""
    imported_count = module.imported_func_count
    if func_idx < imported_count:
        # Imported function
        imp = [i for i in module.imports if i.kind == ExternalKind.FUNCTION][func_idx]
        sig = module.types[imp.desc].to_wat()
        return f'(import "{imp.module}" "{imp.name}" (func ${module.get_function_name(func_idx)} {sig}))'

    body_idx = func_idx - imported_count
    if body_idx >= len(module.codes):
        raise IndexError(f"Function index {func_idx} out of range")

    body = module.codes[body_idx]
    fn_name = module.get_function_name(func_idx)
    sig = module.get_function_type(func_idx)

    lines: List[str] = []
    # Header: (func $name (param ...) (result ...)
    sig_str = sig.to_wat()
    header_parts = [f"(func ${fn_name}"]
    if sig_str:
        header_parts.append(sig_str)
    lines.append(" ".join(header_parts))

    # Locals
    for loc in body.locals:
        for _ in range(loc.count):
            lines.append(f"  (local {loc.valtype.to_wat()})")

    # Body instructions with structured block indentation
    depth = 1
    for instr in body.instructions:
        # Decrement before printing for 'else' or closing 'end'
        if instr.mnemonic in ("end", "else"):
            depth = max(1, depth - 1)

        lines.append(format_instruction(instr, indent_level=depth))

        # Increment after printing opening constructs
        if instr.mnemonic in ("block", "loop", "if", "else"):
            depth += 1

    lines.append(")")
    return "\n".join(lines)


def disassemble_module(module: WasmModule) -> str:
    """Disassemble an entire WasmModule into readable WAT representation."""
    lines: List[str] = ["(module"]

    # Types
    for i, t in enumerate(module.types):
        lines.append(f"  (type $t{i} (func {t.to_wat()}))")

    # Imports
    for imp in module.imports:
        if imp.kind == ExternalKind.FUNCTION:
            sig = module.types[imp.desc].to_wat()
            lines.append(f'  (import "{imp.module}" "{imp.name}" (func (type {imp.desc}) {sig}))')
        elif imp.kind == ExternalKind.MEMORY:
            lines.append(f'  (import "{imp.module}" "{imp.name}" (memory {imp.desc.limits.to_wat()}))')
        elif imp.kind == ExternalKind.TABLE:
            lines.append(f'  (import "{imp.module}" "{imp.name}" (table {imp.desc.limits.to_wat()} {imp.desc.element_type.to_wat()}))')
        elif imp.kind == ExternalKind.GLOBAL:
            mut_prefix = "mut " if imp.desc.mutable else ""
            lines.append(f'  (import "{imp.module}" "{imp.name}" (global ({mut_prefix}{imp.desc.valtype.to_wat()})))')

    # Tables
    for tbl in module.tables:
        lines.append(f"  (table {tbl.limits.to_wat()} {tbl.element_type.to_wat()})")

    # Memories
    for mem in module.memories:
        lines.append(f"  (memory {mem.limits.to_wat()})")

    # Globals
    for g in module.globals:
        mut_prefix = "mut " if g.type.mutable else ""
        init_str = " ".join(i.mnemonic + (f" {i.operands}" if i.operands is not None else "") for i in g.init_expr)
        lines.append(f"  (global ({mut_prefix}{g.type.valtype.to_wat()}) ({init_str}))")

    # Exports
    for exp in module.exports:
        kind_name = {
            ExternalKind.FUNCTION: "func",
            ExternalKind.TABLE: "table",
            ExternalKind.MEMORY: "memory",
            ExternalKind.GLOBAL: "global",
        }.get(exp.kind, "unknown")
        lines.append(f'  (export "{exp.name}" ({kind_name} {exp.index}))')

    # Functions
    for i in range(module.imported_func_count, module.total_func_count):
        fn_text = disassemble_function(module, i)
        indented_fn = "\n".join("  " + line for line in fn_text.splitlines())
        lines.append(indented_fn)

    # Data segments
    for d in module.datas:
        preview = repr(d.data[:32])[1:]
        if len(d.data) > 32:
            preview = preview[:-1] + "...'"
        if d.is_passive:
            lines.append(f"  (data (bytes {preview}))")
        else:
            lines.append(f"  (data (i32.const offset) {preview})")

    lines.append(")")
    return "\n".join(lines)
