"""Unit tests for FastAPI Web Studio endpoints."""

import pytest
from fastapi.testclient import TestClient
from wasmlens.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "WasmLens" in response.text


def test_api_samples(client):
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert "factorial.wasm" in samples


def test_api_module_overview(client):
    response = client.get("/api/module")
    assert response.status_code == 200
    data = response.json()
    assert data["magic"] == "\x00asm"
    assert data["version"] == 1
    assert len(data["functions"]) >= 1


def test_api_disasm_and_decompile(client):
    disasm_res = client.get("/api/disasm/0")
    assert disasm_res.status_code == 200
    assert "func" in disasm_res.json()["wat"]

    decompile_res = client.get("/api/decompile/0")
    assert decompile_res.status_code == 200
    assert "return" in decompile_res.json()["code"]


def test_api_cfg(client):
    res = client.get("/api/cfg/0")
    assert res.status_code == 200
    data = res.json()
    assert len(data["blocks"]) >= 1
    assert "metrics" in data
    assert data["metrics"]["cyclomatic_complexity"] >= 1


def test_api_memory(client):
    client.post("/api/load-sample/memory_ops.wasm")
    pages_res = client.get("/api/memory/pages")
    assert pages_res.status_code == 200
    assert len(pages_res.json()["pages"]) >= 1

    hex_res = client.get("/api/memory/hex?page=0&offset=0&length=32")
    assert hex_res.status_code == 200
    assert len(hex_res.json()["lines"]) >= 1


def test_api_emulator_stepping(client):
    client.post("/api/load-sample/factorial.wasm")
    inv_res = client.post("/api/emulator/invoke", json={"func_index": 0, "args": [3]})
    assert inv_res.status_code == 200
    assert inv_res.json()["status"] == "ready"

    step_res = client.post("/api/emulator/step")
    assert step_res.status_code == 200
    data = step_res.json()
    assert data["step_number"] == 1
    assert "instruction" in data


def test_api_breakpoints_and_watchpoints(client):
    client.post("/api/load-sample/factorial.wasm")
    client.post("/api/emulator/invoke", json={"func_index": 0, "args": [3]})

    bp_res = client.post("/api/emulator/breakpoint", json={"func_index": 0, "pc": 4, "enabled": True})
    assert bp_res.status_code == 200
    assert len(bp_res.json()["breakpoints"]) == 1

    list_bp = client.get("/api/emulator/breakpoints")
    assert len(list_bp.json()["breakpoints"]) == 1

    wp_res = client.post("/api/emulator/watchpoint", json={"address": 16, "mode": "write", "enabled": True})
    assert wp_res.status_code == 200
    assert "0x000010" in wp_res.json()["write_watchpoints"]


def test_api_step_back_and_continue(client):
    client.post("/api/load-sample/factorial.wasm")
    client.post("/api/emulator/invoke", json={"func_index": 0, "args": [3]})

    # Step forward 2 times
    client.post("/api/emulator/step")
    client.post("/api/emulator/step")

    # Step backward
    back_res = client.post("/api/emulator/step-back")
    assert back_res.status_code == 200
    assert back_res.json()["status"] == "rewound"

    # Set breakpoint and continue
    client.post("/api/emulator/breakpoint", json={"func_index": 0, "pc": 4, "enabled": True})
    cont_res = client.post("/api/emulator/continue")
    assert cont_res.status_code == 200
    assert "Breakpoint" in cont_res.json()["stop_reason"]


def test_api_patch_and_download(client):
    client.post("/api/load-sample/factorial.wasm")
    patch_res = client.post(
        "/api/patch",
        json={"func_index": 0, "pc": 0, "action": "const", "value": 10},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "success"

    # Verify download
    down_res = client.get("/api/download")
    assert down_res.status_code == 200
    assert down_res.headers["content-type"] == "application/wasm"
    assert len(down_res.content) > 0


def test_api_bloat_and_dataflow(client):
    client.post("/api/load-sample/factorial.wasm")

    bloat_res = client.get("/api/profiler/bloat")
    assert bloat_res.status_code == 200
    assert "treemap_data" in bloat_res.json()

    df_res = client.get("/api/analysis/dataflow/0")
    assert df_res.status_code == 200
    assert df_res.json()["max_stack_depth"] >= 1


def test_api_export_report_and_header(client):
    client.post("/api/load-sample/factorial.wasm")

    rep_res = client.get("/api/export/report")
    assert rep_res.status_code == 200
    assert "<!DOCTYPE html>" in rep_res.text

    hdr_res = client.get("/api/export/header")
    assert hdr_res.status_code == 200
    assert "#ifndef" in hdr_res.text
