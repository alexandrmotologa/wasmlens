"""Binary bloat analyzer and section size profiler (Twiggy-style)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from wasmlens.parser.types import ExternalKind, SectionId, WasmModule


@dataclass
class SectionBloat:
    """Byte attribution for a single Wasm binary section."""
    id: int
    name: str
    size: int
    percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FunctionBloat:
    """Byte attribution for an individual compiled function body."""
    func_index: int
    name: str
    size: int
    instruction_count: int
    percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DataSegmentBloat:
    """Byte attribution for a linear memory data segment."""
    index: int
    size: int
    percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BloatReport:
    """Complete binary space consumption profile."""
    total_size: int
    header_size: int
    sections: List[SectionBloat]
    functions: List[FunctionBloat]
    data_segments: List[DataSegmentBloat]
    treemap_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_size": self.total_size,
            "header_size": self.header_size,
            "sections": [s.to_dict() for s in self.sections],
            "functions": [f.to_dict() for f in self.functions],
            "data_segments": [d.to_dict() for d in self.data_segments],
            "treemap_data": self.treemap_data,
        }


def analyze_bloat(module: WasmModule, raw_bytes: Optional[bytes] = None) -> BloatReport:
    """Compute detailed size attribution across all module sections and functions."""
    header_size = 8  # 4 bytes magic + 4 bytes version
    calculated_total = header_size

    sections_bloat: List[SectionBloat] = []
    for s in module.sections:
        # Include section id (1 byte) + LEB128 size overhead (at least 1 byte) + payload size
        sec_size = s.size + 2
        calculated_total += sec_size

    total_size = len(raw_bytes) if raw_bytes is not None else max(calculated_total, 8)
    if total_size == 0:
        total_size = 1

    # Section breakdown
    for s in module.sections:
        sec_name = s.name if s.name else s.id.name.lower()
        pct = (s.size / total_size) * 100.0
        sections_bloat.append(
            SectionBloat(
                id=s.id.value,
                name=sec_name,
                size=s.size,
                percentage=round(pct, 2),
            )
        )

    # Function breakdown (Code section)
    functions_bloat: List[FunctionBloat] = []
    imported_count = module.imported_func_count
    for i, body in enumerate(module.codes):
        f_idx = imported_count + i
        f_name = module.get_function_name(f_idx)
        # Approximate function body size in bytes from instructions or code length
        fn_size = max(body.size, len(body.instructions))
        pct = (fn_size / total_size) * 100.0
        functions_bloat.append(
            FunctionBloat(
                func_index=f_idx,
                name=f_name,
                size=fn_size,
                instruction_count=len(body.instructions),
                percentage=round(pct, 2),
            )
        )

    # Sort functions by size descending
    functions_bloat.sort(key=lambda f: f.size, reverse=True)

    # Data segments breakdown
    data_bloat: List[DataSegmentBloat] = []
    for i, d in enumerate(module.datas):
        d_size = len(d.data)
        pct = (d_size / total_size) * 100.0
        data_bloat.append(
            DataSegmentBloat(
                index=i,
                size=d_size,
                percentage=round(pct, 2),
            )
        )

    # Hierarchical Treemap structure
    treemap_children = []

    # Add header
    treemap_children.append({"name": "Wasm Header", "value": header_size, "category": "header"})

    for s in sections_bloat:
        sec_node: Dict[str, Any] = {
            "name": f"Section {s.name}",
            "value": s.size,
            "category": s.name,
        }
        if s.name == "code" and functions_bloat:
            sec_node["children"] = [
                {
                    "name": f"${f.name} (func {f.func_index})",
                    "value": f.size,
                    "category": "function",
                    "instruction_count": f.instruction_count,
                }
                for f in functions_bloat
            ]
        elif s.name == "data" and data_bloat:
            sec_node["children"] = [
                {
                    "name": f"data_segment_{d.index}",
                    "value": d.size,
                    "category": "data",
                }
                for d in data_bloat
            ]
        treemap_children.append(sec_node)

    treemap_root = {
        "name": "wasm_module",
        "value": total_size,
        "children": treemap_children,
    }

    return BloatReport(
        total_size=total_size,
        header_size=header_size,
        sections=sections_bloat,
        functions=functions_bloat,
        data_segments=data_bloat,
        treemap_data=treemap_root,
    )
