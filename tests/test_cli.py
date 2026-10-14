"""Unit tests for Typer CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
from wasmlens.cli.main import app

runner = CliRunner()


def test_cli_info():
    res = runner.invoke(app, ["info", "src/wasmlens/samples/factorial.wasm"])
    assert res.exit_code == 0
    assert "WasmLens Binary Inspector" in res.stdout
    assert "factorial.wasm" in res.stdout
    assert "Binary Sections" in res.stdout


def test_cli_disasm():
    res = runner.invoke(app, ["disasm", "src/wasmlens/samples/factorial.wasm"])
    assert res.exit_code == 0
    assert "func $factorial" in res.stdout
    assert "br_if 1" in res.stdout


def test_cli_decompile():
    res = runner.invoke(app, ["decompile", "src/wasmlens/samples/factorial.wasm", "--func", "0"])
    assert res.exit_code == 0
    assert "factorial" in res.stdout
    assert "while (1)" in res.stdout


def test_cli_cfg():
    res = runner.invoke(app, ["cfg", "src/wasmlens/samples/factorial.wasm", "--format", "ascii"])
    assert res.exit_code == 0
    assert "Control-Flow Graph for $factorial" in res.stdout

    res_dot = runner.invoke(app, ["cfg", "src/wasmlens/samples/factorial.wasm", "--format", "dot"])
    assert res_dot.exit_code == 0
    assert "digraph" in res_dot.stdout


def test_cli_mem():
    res = runner.invoke(app, ["mem", "src/wasmlens/samples/memory_ops.wasm", "--length", "64"])
    assert res.exit_code == 0
    assert "Linear Memory Overview" in res.stdout
    assert "WasmLens" in res.stdout
    assert "2026" in res.stdout


def test_cli_emu():
    res = runner.invoke(app, ["emu", "src/wasmlens/samples/factorial.wasm", "--arg", "5"])
    assert res.exit_code == 0
    assert "Return Value: [120]" in res.stdout

    res_step = runner.invoke(app, ["emu", "src/wasmlens/samples/factorial.wasm", "--arg", "3", "--step"])
    assert res_step.exit_code == 0
    assert "Execution Trace" in res_step.stdout

    # Test breakpoint
    res_bp = runner.invoke(app, ["emu", "src/wasmlens/samples/factorial.wasm", "--arg", "3", "--break-at", "2"])
    assert res_bp.exit_code == 0
    assert "Breakpoint" in res_bp.stdout


def test_cli_bloat():
    res = runner.invoke(app, ["bloat", "src/wasmlens/samples/factorial.wasm"])
    assert res.exit_code == 0
    assert "Binary Bloat Profile" in res.stdout
    assert "Section Size Breakdown" in res.stdout

    res_json = runner.invoke(app, ["bloat", "src/wasmlens/samples/factorial.wasm", "--json"])
    assert res_json.exit_code == 0
    assert "treemap_data" in res_json.stdout


def test_cli_dataflow():
    res = runner.invoke(app, ["dataflow", "src/wasmlens/samples/factorial.wasm", "--func", "0"])
    assert res.exit_code == 0
    assert "Data-Flow & Stack Effect" in res.stdout
    assert "Peak Depth" in res.stdout


def test_cli_patch(tmp_path):
    out_wasm = tmp_path / "patched.wasm"
    res = runner.invoke(
        app,
        [
            "patch",
            "src/wasmlens/samples/factorial.wasm",
            "-o",
            str(out_wasm),
            "--func",
            "0",
            "--pc",
            "0",
            "--const",
            "42",
        ],
    )
    assert res.exit_code == 0
    assert "Patched binary saved to" in res.stdout
    assert out_wasm.exists()


def test_cli_report(tmp_path):
    out_html = tmp_path / "report.html"
    res = runner.invoke(app, ["report", "src/wasmlens/samples/factorial.wasm", "-o", str(out_html)])
    assert res.exit_code == 0
    assert "Standalone HTML audit report generated" in res.stdout
    assert out_html.exists()
    assert "<!DOCTYPE html>" in out_html.read_text(encoding="utf-8")


def test_cli_header(tmp_path):
    out_h = tmp_path / "module.h"
    res = runner.invoke(app, ["header", "src/wasmlens/samples/factorial.wasm", "-o", str(out_h)])
    assert res.exit_code == 0
    assert "C header exported" in res.stdout
    assert out_h.exists()
    assert "#ifndef WASMLENS_FACTORIAL_H" in out_h.read_text(encoding="utf-8")
