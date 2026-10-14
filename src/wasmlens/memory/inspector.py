"""Linear memory page inspector and segment layout analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from wasmlens.parser.types import DataSegment, MemoryType, WasmModule

WASM_PAGE_SIZE = 65536  # 64 KiB


@dataclass
class MemoryRegion:
    """Designated slice of memory."""
    name: str
    start: int
    end: int
    segment_index: Optional[int] = None
    description: str = ""

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass
class MemoryPage:
    """A 64KiB WebAssembly memory page."""
    index: int
    start_address: int
    end_address: int
    regions: List[MemoryRegion] = field(default_factory=list)

    @property
    def allocated_bytes(self) -> int:
        return sum(r.size for r in self.regions)

    @property
    def utilization_pct(self) -> float:
        return round((self.allocated_bytes / WASM_PAGE_SIZE) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_address": self.start_address,
            "end_address": self.end_address,
            "allocated_bytes": self.allocated_bytes,
            "utilization_pct": self.utilization_pct,
            "regions": [
                {
                    "name": r.name,
                    "start": r.start,
                    "end": r.end,
                    "size": r.size,
                    "segment_index": r.segment_index,
                    "description": r.description,
                }
                for r in self.regions
            ],
        }


class MemoryInspector:
    """Inspects linear memory pages, active data segments, and memory bounds."""

    def __init__(self, module: WasmModule, initial_memory: Optional[bytearray] = None) -> None:
        self.module = module
        self.memory_type: Optional[MemoryType] = module.memories[0] if module.memories else None

        # Sizing in 64KB pages
        if self.memory_type:
            self.min_pages = self.memory_type.limits.min
            self.max_pages = self.memory_type.limits.max
        else:
            self.min_pages = 0
            self.max_pages = 0

        self.total_size = self.min_pages * WASM_PAGE_SIZE

        # Initialize linear memory buffer
        if initial_memory is not None:
            self.buffer = initial_memory
        else:
            self.buffer = bytearray(self.total_size)
            self._apply_active_segments()

    def _apply_active_segments(self) -> None:
        """Apply active data segments to memory buffer."""
        for seg in self.module.datas:
            if not seg.is_passive and seg.offset_expr:
                offset = self._eval_offset(seg.offset_expr)
                end = offset + len(seg.data)
                if end > len(self.buffer):
                    # Expand buffer if needed
                    self.buffer.extend(b"\x00" * (end - len(self.buffer)))
                self.buffer[offset:end] = seg.data

    def _eval_offset(self, expr: List[any]) -> int:
        """Evaluate constant offset expression."""
        for instr in expr:
            if instr.mnemonic in ("i32.const", "i64.const"):
                return int(instr.operands)
        return 0

    def get_pages(self) -> List[MemoryPage]:
        """Generate structured metadata for each 64KB memory page."""
        page_count = max(self.min_pages, (len(self.buffer) + WASM_PAGE_SIZE - 1) // WASM_PAGE_SIZE or 1)
        pages: List[MemoryPage] = []

        for p_idx in range(page_count):
            p_start = p_idx * WASM_PAGE_SIZE
            p_end = p_start + WASM_PAGE_SIZE
            page = MemoryPage(index=p_idx, start_address=p_start, end_address=p_end)

            # Map active segments intersecting this page
            for seg in self.module.datas:
                if not seg.is_passive and seg.offset_expr:
                    s_off = self._eval_offset(seg.offset_expr)
                    s_end = s_off + len(seg.data)
                    # Intersection check
                    inter_start = max(p_start, s_off)
                    inter_end = min(p_end, s_end)
                    if inter_start < inter_end:
                        page.regions.append(
                            MemoryRegion(
                                name=f"data_seg_{seg.index}",
                                start=inter_start,
                                end=inter_end,
                                segment_index=seg.index,
                                description=f"Data segment {seg.index} payload",
                            )
                        )

            pages.append(page)
        return pages

    def check_out_of_bounds_segments(self) -> List[Tuple[int, int, int]]:
        """Identify data segments exceeding declared min memory bounds.

        Returns:
            List of (segment_index, offset, required_bytes)
        """
        violations = []
        bound = self.min_pages * WASM_PAGE_SIZE
        for seg in self.module.datas:
            if not seg.is_passive and seg.offset_expr:
                off = self._eval_offset(seg.offset_expr)
                end = off + len(seg.data)
                if end > bound:
                    violations.append((seg.index, off, end))
        return violations

    def read_bytes(self, offset: int, length: int) -> bytes:
        if offset < 0 or offset >= len(self.buffer):
            return b""
        end = min(len(self.buffer), offset + length)
        return bytes(self.buffer[offset:end])
