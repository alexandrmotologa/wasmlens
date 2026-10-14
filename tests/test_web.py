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
