"""FastAPI backend server for WasmLens interactive Web Studio."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wasmlens.analysis.dataflow import analyze_dataflow
from wasmlens.cfg.analyzer import CFGAnalyzer
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.decompiler.reconstructor import Decompiler
from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
)
from wasmlens.emulator.vm import WasmVM
from wasmlens.export.header import generate_c_header
from wasmlens.export.report import generate_html_report
from wasmlens.memory.hexdump import hexdump_lines
from wasmlens.memory.inspector import MemoryInspector
from wasmlens.memory.search import find_bytes, find_i32, find_string
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.types import ExternalKind, WasmModule
from wasmlens.patcher.patcher import PatchError, WasmPatcher
from wasmlens.profiler.bloat import analyze_bloat

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
STATIC_DIR = Path(__file__).parent / "static"

# Global session state holding the currently active module and VM
current_module: Optional[WasmModule] = None
current_vm: Optional[WasmVM] = None
active_wasm_bytes: Optional[bytes] = None


class InvokeRequest(BaseModel):
    func_index: int
    args: List[int | float] = []


class MemorySearchRequest(BaseModel):
    type: str  # "string", "hex", "i32"
    query: str


class PatchRequest(BaseModel):
    func_index: int
    pc: int
    action: str  # "nop" or "const"
    value: Optional[int | float] = None


class BreakpointRequest(BaseModel):
    func_index: int
    pc: int
    enabled: bool = True


class WatchpointRequest(BaseModel):
    address: int
    mode: str = "write"  # "write", "read", "both"
    enabled: bool = True


def load_initial_module() -> None:
    """Load default or environment-specified WASM module on startup."""
    global current_module, current_vm, active_wasm_bytes
    init_path = os.environ.get("WASMLENS_INITIAL_FILE")
    if init_path and Path(init_path).exists():
        target = Path(init_path)
    else:
        target = SAMPLES_DIR / "factorial.wasm"

    if target.exists():
        with open(target, "rb") as f:
            active_wasm_bytes = f.read()
        current_module = parse_wasm(active_wasm_bytes)
        current_vm = WasmVM(current_module)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    load_initial_module()

    app = FastAPI(
        title="WasmLens Studio",
        description="Interactive WebAssembly 2.0 binary decompiler, CFG visualizer, memory inspector, and debugger",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_file = STATIC_DIR / "index.html"
        if not index_file.exists():
            return "<html><body><h1>WasmLens Studio UI Loading...</h1></body></html>"
        return index_file.read_text(encoding="utf-8")

    @app.get("/api/samples")
    def list_samples() -> List[str]:
        if not SAMPLES_DIR.exists():
            return []
        return [f.name for f in SAMPLES_DIR.glob("*.wasm")]

    @app.post("/api/load-sample/{sample_name}")
    def load_sample(sample_name: str):
        global current_module, current_vm, active_wasm_bytes
        sample_path = SAMPLES_DIR / sample_name
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Sample not found")

        active_wasm_bytes = sample_path.read_bytes()
        current_module = parse_wasm(active_wasm_bytes)
        current_vm = WasmVM(current_module)
        return get_module_overview()

    @app.post("/api/upload")
    async def upload_wasm(file: UploadFile = File(...)):
        global current_module, current_vm, active_wasm_bytes
        data = await file.read()
        try:
            mod = parse_wasm(data)
            active_wasm_bytes = data
            current_module = mod
            current_vm = WasmVM(mod)
            return get_module_overview()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse WASM binary: {e}")

    @app.get("/api/module")
    def get_module_overview() -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")

        exports_by_func = {
            e.index: e.name
            for e in current_module.exports
            if e.kind == ExternalKind.FUNCTION
        }

        functions_list = []
        for f_idx in range(current_module.total_func_count):
            sig = current_module.get_function_type(f_idx)
            fn_name = current_module.get_function_name(f_idx)
            functions_list.append({
                "index": f_idx,
                "name": fn_name,
                "signature": sig.to_wat(),
                "params": [p.to_wat() for p in sig.params],
                "results": [r.to_wat() for r in sig.results],
                "exported_as": exports_by_func.get(f_idx),
                "is_imported": f_idx < current_module.imported_func_count,
            })

        sections_list = [
            {
                "id": s.id.value,
                "name": s.name if s.name else s.id.name.lower(),
                "size": s.size,
                "offset": s.offset,
                "payload_offset": s.payload_offset,
            }
            for s in current_module.sections
        ]

        return {
            "magic": current_module.magic.decode("latin1", errors="replace"),
            "version": current_module.version,
            "byte_size": len(active_wasm_bytes) if active_wasm_bytes else 0,
            "functions": functions_list,
            "sections": sections_list,
            "types_count": len(current_module.types),
            "memories_count": len(current_module.memories),
            "tables_count": len(current_module.tables),
            "globals_count": len(current_module.globals),
            "datas_count": len(current_module.datas),
        }

    @app.get("/api/disasm/{func_index}")
    def get_disasm(func_index: int) -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        wat = disassemble_function(current_module, func_index)
        return {"func_index": func_index, "wat": wat}

    @app.get("/api/decompile/{func_index}")
    def get_decompile(func_index: int) -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        decompiler = Decompiler(current_module)
        c_code = decompiler.decompile_function(func_index)
        return {"func_index": func_index, "code": c_code}

    @app.get("/api/cfg/{func_index}")
    def get_cfg(func_index: int) -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        builder = CFGBuilder(current_module)
        graph = builder.build_cfg(func_index)
        analyzer = CFGAnalyzer(graph)
        metrics = analyzer.analyze()

        cfg_dict = graph.to_dict()
        cfg_dict["metrics"] = {
            "block_count": metrics.block_count,
            "edge_count": metrics.edge_count,
            "cyclomatic_complexity": metrics.cyclomatic_complexity,
            "natural_loops_count": len(metrics.natural_loops),
            "dead_blocks_count": len(metrics.dead_blocks),
        }
        return cfg_dict

    @app.get("/api/memory/pages")
    def get_memory_pages() -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        inspector = MemoryInspector(current_module, current_vm.memory if current_vm else None)
        pages = inspector.get_pages()
        return {
            "min_pages": inspector.min_pages,
            "max_pages": inspector.max_pages,
            "total_size": len(inspector.buffer),
            "pages": [p.to_dict() for p in pages],
        }

    @app.get("/api/memory/hex")
    def get_memory_hex(page: int = 0, offset: int = 0, length: int = 256) -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        inspector = MemoryInspector(current_module, current_vm.memory if current_vm else None)
        start_addr = page * 65536 + offset
        chunk = inspector.read_bytes(start_addr, length)
        lines = hexdump_lines(chunk, base_address=start_addr)
        return {
            "start_address": start_addr,
            "length": len(chunk),
            "lines": [
                {
                    "address": f"0x{l.address:06X}",
                    "hex_left": l.hex_left,
                    "hex_right": l.hex_right,
                    "ascii": l.ascii_text,
                    "is_zero": l.is_zero_line,
                }
                for l in lines
            ],
        }

    @app.post("/api/memory/search")
    def search_memory(req: MemorySearchRequest) -> dict:
        if current_vm is None:
            raise HTTPException(status_code=400, detail="No active VM")

        buffer = current_vm.memory
        matches: List[int] = []

        if req.type == "string":
            matches = find_string(buffer, req.query)
        elif req.type == "hex":
            clean_hex = req.query.replace(" ", "").replace("0x", "")
            try:
                pattern = bytes.fromhex(clean_hex)
                matches = find_bytes(buffer, pattern)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid hex string")
        elif req.type == "i32":
            try:
                val = int(req.query)
                matches = find_i32(buffer, val)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid integer")

        return {"query": req.query, "matches": [f"0x{m:06X}" for m in matches[:50]], "total": len(matches)}

    # Emulator Endpoints
    @app.post("/api/emulator/invoke")
    def emulator_invoke(req: InvokeRequest) -> dict:
        global current_vm
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")

        current_vm = WasmVM(current_module)
        current_vm.invoke(req.func_index, req.args)
        return {
            "status": "ready",
            "func_index": req.func_index,
            "args": req.args,
            "stack": current_vm.stack.snapshot(),
            "locals": current_vm.call_stack[-1].snapshot_locals() if current_vm.call_stack else [],
        }

    @app.post("/api/emulator/step")
    def emulator_step() -> dict:
        if current_vm is None or not current_vm.is_running:
            return {"is_halted": True, "step_number": current_vm.step_counter if current_vm else 0}

        trace = current_vm.step()
        return {
            "step_number": trace.step_number,
            "func_index": trace.func_index,
            "func_name": trace.func_name,
            "pc": trace.pc,
            "instruction": f"{trace.instruction_mnemonic} {trace.instruction_operands}".strip(),
            "mnemonic": trace.instruction_mnemonic,
            "operands": trace.instruction_operands,
            "offset": f"0x{trace.instruction_offset:04X}",
            "stack_before": trace.stack_before,
            "stack_after": trace.stack_after,
            "locals": trace.locals_snapshot,
            "memory_diff": (
                {
                    "address": f"0x{trace.memory_diff.address:06X}",
                    "size": trace.memory_diff.size,
                    "hex": trace.memory_diff.new_bytes.hex().upper(),
                }
                if trace.memory_diff
                else None
            ),
            "is_halted": trace.is_halted,
            "hit_breakpoint": trace.hit_breakpoint,
            "hit_watchpoint": trace.hit_watchpoint,
        }

    @app.post("/api/emulator/step-back")
    def emulator_step_back() -> dict:
        if current_vm is None:
            raise HTTPException(status_code=400, detail="No active VM")

        trace = current_vm.step_backward()
        if trace is None:
            return {"status": "no_history", "step_number": current_vm.step_counter}

        return {
            "status": "rewound",
            "step_number": trace.step_number,
            "func_index": trace.func_index,
            "func_name": trace.func_name,
            "pc": trace.pc,
            "instruction": f"{trace.instruction_mnemonic} {trace.instruction_operands}".strip(),
            "stack": trace.stack_after,
            "locals": trace.locals_snapshot,
            "is_halted": trace.is_halted,
        }

    @app.post("/api/emulator/continue")
    def emulator_continue() -> dict:
        if current_vm is None or not current_vm.is_running:
            return {"is_halted": True, "stop_reason": "halted"}

        is_halted, reason = current_vm.run_until_break(max_steps=5000)
        return {
            "is_halted": is_halted,
            "stop_reason": reason,
            "step_number": current_vm.step_counter,
            "pc": current_vm.call_stack[-1].pc if current_vm.call_stack else 0,
            "stack": current_vm.stack.snapshot(),
            "locals": current_vm.call_stack[-1].snapshot_locals() if current_vm.call_stack else [],
        }

    @app.post("/api/emulator/run")
    def emulator_run() -> dict:
        if current_vm is None or not current_vm.is_running:
            return {"is_halted": True, "results": []}

        traces = current_vm.trace_execution(max_steps=5000)
        results = []
        while not current_vm.stack.is_empty():
            results.insert(0, current_vm.stack.pop().value)

        return {
            "is_halted": True,
            "step_count": current_vm.step_counter,
            "trace_count": len(traces),
            "results": results,
        }

    @app.post("/api/emulator/breakpoint")
    def toggle_breakpoint(req: BreakpointRequest) -> dict:
        if current_vm is None:
            raise HTTPException(status_code=400, detail="No active VM")

        if req.enabled:
            current_vm.add_breakpoint(req.func_index, req.pc)
        else:
            current_vm.remove_breakpoint(req.func_index, req.pc)

        return {"breakpoints": [{"func_index": f, "pc": p} for f, p in current_vm.breakpoints]}

    @app.get("/api/emulator/breakpoints")
    def list_breakpoints() -> dict:
        if current_vm is None:
            return {"breakpoints": []}
        return {"breakpoints": [{"func_index": f, "pc": p} for f, p in sorted(current_vm.breakpoints)]}

    @app.post("/api/emulator/watchpoint")
    def toggle_watchpoint(req: WatchpointRequest) -> dict:
        if current_vm is None:
            raise HTTPException(status_code=400, detail="No active VM")

        if req.enabled:
            on_read = req.mode in ("read", "both")
            on_write = req.mode in ("write", "both")
            current_vm.add_watchpoint(req.address, on_read=on_read, on_write=on_write)
        else:
            current_vm.remove_watchpoint(req.address)

        return {
            "read_watchpoints": [f"0x{a:06X}" for a in sorted(current_vm.read_watchpoints)],
            "write_watchpoints": [f"0x{a:06X}" for a in sorted(current_vm.write_watchpoints)],
        }

    @app.get("/api/emulator/watchpoints")
    def list_watchpoints() -> dict:
        if current_vm is None:
            return {"read_watchpoints": [], "write_watchpoints": []}
        return {
            "read_watchpoints": [f"0x{a:06X}" for a in sorted(current_vm.read_watchpoints)],
            "write_watchpoints": [f"0x{a:06X}" for a in sorted(current_vm.write_watchpoints)],
        }

    # Patcher Endpoint
    @app.post("/api/patch")
    def patch_binary(req: PatchRequest) -> dict:
        global current_module, current_vm, active_wasm_bytes
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")

        patcher = WasmPatcher(current_module)
        try:
            if req.action == "nop":
                patcher.nop_instruction(req.func_index, req.pc)
            elif req.action == "const" and req.value is not None:
                patcher.patch_constant(req.func_index, req.pc, req.value)
            else:
                raise HTTPException(status_code=400, detail="Invalid patch action or missing value")

            new_bytes = patcher.emit_binary()
            active_wasm_bytes = new_bytes
            current_module = parse_wasm(new_bytes)
            current_vm = WasmVM(current_module)

            return {
                "status": "success",
                "message": f"Successfully patched func {req.func_index} at pc {req.pc}",
                "byte_size": len(new_bytes),
            }
        except PatchError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Binary Download Endpoint
    @app.get("/api/download")
    def download_wasm() -> Response:
        if active_wasm_bytes is None:
            raise HTTPException(status_code=400, detail="No module available for download")
        return Response(
            content=active_wasm_bytes,
            media_type="application/wasm",
            headers={"Content-Disposition": "attachment; filename=module.wasm"},
        )

    # Profiler Bloat Endpoint
    @app.get("/api/profiler/bloat")
    def get_bloat() -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        report = analyze_bloat(current_module, active_wasm_bytes)
        return report.to_dict()

    # Data-Flow Analysis Endpoint
    @app.get("/api/analysis/dataflow/{func_index}")
    def get_dataflow(func_index: int) -> dict:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        result = analyze_dataflow(current_module, func_index)
        return result.to_dict()

    # Exporters
    @app.get("/api/export/report", response_class=HTMLResponse)
    def export_report() -> str:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        return generate_html_report(current_module)

    @app.get("/api/export/header", response_class=PlainTextResponse)
    def export_header() -> str:
        if current_module is None:
            raise HTTPException(status_code=400, detail="No module loaded")
        return generate_c_header(current_module)

    return app
