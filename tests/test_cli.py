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
