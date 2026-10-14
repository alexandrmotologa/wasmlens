"""Unit tests for Control-Flow Graph construction, analysis, and exports."""

from pathlib import Path

from wasmlens.cfg.analyzer import CFGAnalyzer
from wasmlens.cfg.basic_block import EdgeType
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.cfg.export import to_ascii, to_dot, to_json, to_mermaid
from wasmlens.parser.module import parse_wasm


def test_cfg_factorial_graph():
    sample_path = Path("src/wasmlens/samples/factorial.wasm")
    module = parse_wasm(sample_path)

    builder = CFGBuilder(module)
    cfg = builder.build_cfg(0)

    assert cfg.func_name == "factorial"
    assert len(cfg.blocks) >= 3
    assert len(cfg.edges) >= 3

    # Check for loop back-edge
    back_edges = [e for e in cfg.edges if e.edge_type == EdgeType.LOOP_BACK]
    assert len(back_edges) >= 1

    # Check analyzer
    analyzer = CFGAnalyzer(cfg)
    result = analyzer.analyze()
    assert result.cyclomatic_complexity >= 2
    assert len(result.natural_loops) >= 1

    # Test exporters
    dot_str = to_dot(cfg)
    assert "digraph" in dot_str
    assert "bb_0" in dot_str

    mermaid_str = to_mermaid(cfg)
    assert "flowchart TD" in mermaid_str

    ascii_str = to_ascii(cfg)
    assert "Control-Flow Graph for $factorial" in ascii_str

    json_str = to_json(cfg)
    assert '"func_name": "factorial"' in json_str
