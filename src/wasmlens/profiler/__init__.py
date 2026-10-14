"""Binary size attribution and section bloat profiler."""

from wasmlens.profiler.bloat import (
    BloatReport,
    DataSegmentBloat,
    FunctionBloat,
    SectionBloat,
    analyze_bloat,
)

__all__ = [
    "analyze_bloat",
    "BloatReport",
    "SectionBloat",
    "FunctionBloat",
    "DataSegmentBloat",
]
