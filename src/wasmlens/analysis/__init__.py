"""Static data-flow and stack-effect simulation engine."""

from wasmlens.analysis.dataflow import (
    DataflowAnalysisResult,
    InstructionDataflow,
    analyze_dataflow,
    get_instruction_stack_effect,
)

__all__ = [
    "analyze_dataflow",
    "get_instruction_stack_effect",
    "DataflowAnalysisResult",
    "InstructionDataflow",
]
