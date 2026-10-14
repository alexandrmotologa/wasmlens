"""WasmLens Command Line Interface (CLI) powered by Typer and Rich."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from wasmlens.analysis.dataflow import analyze_dataflow
from wasmlens.cfg.analyzer import CFGAnalyzer
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.cfg.export import to_ascii, to_dot, to_json, to_mermaid
from wasmlens.decompiler.reconstructor import Decompiler
from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
)
from wasmlens.emulator.vm import WasmVM
from wasmlens.export.header import generate_c_header
from wasmlens.export.report import generate_html_report
from wasmlens.memory.hexdump import format_hexdump
from wasmlens.memory.inspector import MemoryInspector
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.types import ExternalKind
from wasmlens.patcher.patcher import WasmPatcher
from wasmlens.profiler.bloat import analyze_bloat

app = typer.Typer(
    name="wasmlens",
    help="Interactive WebAssembly 2.0 binary decompiler, CFG visualizer, memory inspector, and debugger.",
    add_completion=False,
)
console = Console()


@app.command()
def info(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
) -> None:
    """Display binary metadata, section table, and exported functions."""
    if not wasm_file.exists():
        console.print(f"[red]Error:[/red] File {wasm_file} does not exist.")
        raise typer.Exit(code=1)

    module = parse_wasm(wasm_file)
    file_size = wasm_file.stat().st_size

    console.print(
        Panel(
            f"[bold cyan]WasmLens Binary Inspector[/bold cyan]\n"
            f"File: [yellow]{wasm_file.name}[/yellow] ({file_size:,} bytes)\n"
            f"Magic: [green]{module.magic.decode('latin1', errors='replace')}[/green] | Version: [green]{module.version}[/green]",
            border_style="cyan",
        )
    )

    # Sections table
    sec_table = Table(title="Binary Sections", border_style="dim")
    sec_table.add_column("ID", justify="center", style="cyan")
    sec_table.add_column("Section Name", style="bold")
    sec_table.add_column("Size (Bytes)", justify="right")
    sec_table.add_column("Payload Offset", justify="right", style="dim")

    for s in module.sections:
        name = s.name if s.name else s.id.name.lower()
        sec_table.add_row(str(s.id.value), name, f"{s.size:,}", f"0x{s.payload_offset:04X}")

    console.print(sec_table)

    # Functions & Exports table
    fn_table = Table(title="Functions & Exports", border_style="dim")
    fn_table.add_column("Index", justify="center", style="cyan")
    fn_table.add_column("Name", style="bold")
    fn_table.add_column("Signature", style="green")
    fn_table.add_column("Exported As", style="yellow")

    exports_by_func = {
        e.index: e.name
        for e in module.exports
        if e.kind == ExternalKind.FUNCTION
    }

    for f_idx in range(module.total_func_count):
        name = module.get_function_name(f_idx)
        sig = module.get_function_type(f_idx).to_wat()
        exported = exports_by_func.get(f_idx, "-")
        fn_table.add_row(str(f_idx), name, sig or "(void)", exported)

    console.print(fn_table)


@app.command()
def disasm(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    func: Optional[int] = typer.Option(None, "--func", "-f", help="Function index to disassemble"),
) -> None:
    """Disassemble WebAssembly bytecode into structured WAT format."""
    module = parse_wasm(wasm_file)
    if func is not None:
        wat_text = disassemble_function(module, func)
    else:
        wat_text = disassemble_module(module)

    syntax = Syntax(wat_text, "lisp", theme="monokai", line_numbers=True)
    console.print(syntax)


@app.command()
def decompile(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    func: int = typer.Option(0, "--func", "-f", help="Function index to decompile"),
) -> None:
    """Decompile a function into high-level C-like structured pseudocode."""
    module = parse_wasm(wasm_file)
    decompiler = Decompiler(module)
    c_code = decompiler.decompile_function(func)

    syntax = Syntax(c_code, "c", theme="monokai", line_numbers=True)
    console.print(
        Panel(syntax, title=f"Decompiled ${module.get_function_name(func)}", border_style="green")
    )


@app.command()
def cfg(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    func: int = typer.Option(0, "--func", "-f", help="Function index"),
    format: str = typer.Option("ascii", "--format", "-m", help="Format: ascii, mermaid, dot, json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save output to file"),
) -> None:
    """Generate and display the Control-Flow Graph (CFG) for a function."""
    module = parse_wasm(wasm_file)
    builder = CFGBuilder(module)
    graph = builder.build_cfg(func)

    fmt = format.lower()
    if fmt == "dot":
        content = to_dot(graph)
    elif fmt == "mermaid":
        content = to_mermaid(graph)
    elif fmt == "json":
        content = to_json(graph)
    elif fmt == "ascii":
        content = to_ascii(graph)
    else:
        console.print(f"[red]Error:[/red] Unsupported format '{format}'. Choose from ascii, mermaid, dot, json.")
        raise typer.Exit(code=1)

    if output is not None:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]CFG saved to:[/green] {output}")
    else:
        if fmt == "dot":
            console.print(Syntax(content, "dot", theme="monokai"))
        elif fmt == "mermaid":
            console.print(Syntax(content, "markdown", theme="monokai"))
        elif fmt == "json":
            console.print(Syntax(content, "json", theme="monokai"))
        else:
            console.print(content)

    analyzer = CFGAnalyzer(graph)
    res = analyzer.analyze()
    console.print(
        f"[dim]Blocks: {res.block_count} | Edges: {res.edge_count} | Cyclomatic Complexity: {res.cyclomatic_complexity} | Natural Loops: {len(res.natural_loops)}[/dim]"
    )


@app.command()
def mem(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    page: int = typer.Option(0, "--page", "-p", help="Page index (0..N)"),
    offset: int = typer.Option(0, "--offset", help="Byte offset inside memory"),
    length: int = typer.Option(256, "--length", "-l", help="Number of bytes to dump"),
) -> None:
    """Inspect 64KB linear memory page layout and formatted hex dump."""
    module = parse_wasm(wasm_file)
    inspector = MemoryInspector(module)

    pages = inspector.get_pages()
    console.print(
        Panel(
            f"Linear Memory Configuration\n"
            f"Declared Pages: Min={inspector.min_pages}, Max={inspector.max_pages}\n"
            f"Total Allocated: {len(inspector.buffer):,} bytes across {len(pages)} pages",
            title="Linear Memory Overview",
            border_style="magenta",
        )
    )

    start_addr = page * 65536 + offset
    chunk = inspector.read_bytes(start_addr, length)
    dump_text = format_hexdump(chunk, base_address=start_addr, collapse_zeroes=False)

    console.print(Panel(dump_text, title=f"Hexdump @ 0x{start_addr:06X} ({length} bytes)", border_style="dim"))


@app.command()
def emu(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    func: int = typer.Option(0, "--func", "-f", help="Function index to invoke"),
    args: List[int] = typer.Option([], "--arg", "-a", help="Function arguments"),
    step: bool = typer.Option(False, "--step", "-s", help="Enable step-by-step trace mode"),
    break_at: Optional[int] = typer.Option(None, "--break-at", "-b", help="Stop at PC breakpoint"),
    watch: Optional[int] = typer.Option(None, "--watch", help="Memory address to watch for writes"),
    max_steps: int = typer.Option(5000, "--max-steps", help="Maximum execution step threshold"),
) -> None:
    """Step-by-step bytecode emulator and runtime debugger."""
    module = parse_wasm(wasm_file)
    vm = WasmVM(module)
    fn_name = module.get_function_name(func)

    if break_at is not None:
        vm.add_breakpoint(func, break_at)
        console.print(f"[dim]Breakpoint configured at func {func} pc {break_at}[/dim]")

    if watch is not None:
        vm.add_watchpoint(watch, on_read=False, on_write=True)
        console.print(f"[dim]Watchpoint configured at memory address 0x{watch:06X}[/dim]")

    console.print(f"[bold cyan]Invoking ${fn_name} with args {args}...[/bold cyan]")
    vm.invoke(func, args)

    if step:
        table = Table(title="Execution Trace", border_style="dim")
        table.add_column("Step", justify="center", style="cyan")
        table.add_column("PC", justify="right", style="yellow")
        table.add_column("Instruction", style="bold")
        table.add_column("Stack", style="green")
        table.add_column("Locals", style="dim")

        traces = vm.trace_execution(max_steps=max_steps)
        for t in traces:
            stack_str = " ".join(f"{s['type']}({s['value']})" for s in t.stack_after)
            locals_str = " ".join(f"${l['index']}={l['value']}" for l in t.locals_snapshot)
            instr_str = f"{t.instruction_mnemonic} {t.instruction_operands}".strip()
            table.add_row(
                str(t.step_number),
                f"0x{t.pc:02X}",
                instr_str,
                stack_str or "[]",
                locals_str or "[]",
            )
        console.print(table)
        results = []
        while not vm.stack.is_empty():
            results.insert(0, vm.stack.pop().value)
    elif break_at is not None or watch is not None:
        is_halted, reason = vm.run_until_break(max_steps=max_steps)
        console.print(f"[yellow]Debugger stopped:[/yellow] {reason} at step {vm.step_counter}")
        results = [v.value for v in vm.stack._stack]
    else:
        results = vm.run_to_completion(max_steps=max_steps)

    console.print(
        Panel(
            f"Execution finished in [bold yellow]{vm.step_counter}[/bold yellow] steps.\n"
            f"Return Value: [bold green]{results}[/bold green]",
            title="Result",
            border_style="green",
        )
    )


@app.command()
def patch(
    wasm_file: Path = typer.Argument(..., help="Path to input WebAssembly binary (.wasm)"),
    output: Path = typer.Option(..., "--output", "-o", help="Target path for patched binary"),
    func: int = typer.Option(0, "--func", "-f", help="Function index to patch"),
    pc: int = typer.Option(..., "--pc", help="Instruction index (PC) to modify"),
    const_val: Optional[int] = typer.Option(None, "--const", "-c", help="Replace constant value"),
    nop: bool = typer.Option(False, "--nop", help="Replace instruction with NOP"),
) -> None:
    """Patch bytecode instruction or immediate constant and serialize valid binary."""
    patcher = WasmPatcher(wasm_file)
    if nop:
        patcher.nop_instruction(func, pc)
        console.print(f"[green]NOPed instruction at func {func} pc {pc}[/green]")
    elif const_val is not None:
        patcher.patch_constant(func, pc, const_val)
        console.print(f"[green]Patched constant at func {func} pc {pc} -> {const_val}[/green]")
    else:
        console.print("[red]Error: Specify either --const <value> or --nop[/red]")
        raise typer.Exit(code=1)

    patcher.save(output)
    console.print(f"[bold cyan]Patched binary saved to:[/bold cyan] {output} ({output.stat().st_size:,} bytes)")


@app.command()
def bloat(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    top: int = typer.Option(10, "--top", "-n", help="Number of largest functions to display"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON format"),
) -> None:
    """Analyze binary bloat and section size attribution (Twiggy-style)."""
    raw_bytes = wasm_file.read_bytes()
    module = parse_wasm(raw_bytes)
    report = analyze_bloat(module, raw_bytes)

    if as_json:
        console.print(json.dumps(report.to_dict(), indent=2))
        return

    console.print(
        Panel(
            f"Binary: [yellow]{wasm_file.name}[/yellow] | Total Size: [green]{report.total_size:,}[/green] bytes\n"
            f"Sections: {len(report.sections)} | Compiled Functions: {len(report.functions)}",
            title="Binary Bloat Profile",
            border_style="cyan",
        )
    )

    # Sections table
    sec_table = Table(title="Section Size Breakdown", border_style="dim")
    sec_table.add_column("Section", style="bold")
    sec_table.add_column("Size (Bytes)", justify="right")
    sec_table.add_column("Ratio (%)", justify="right", style="cyan")

    for s in report.sections:
        sec_table.add_row(s.name, f"{s.size:,}", f"{s.percentage:.1f}%")
    console.print(sec_table)

    # Top functions
    if report.functions:
        fn_table = Table(title=f"Top {min(top, len(report.functions))} Largest Functions", border_style="dim")
        fn_table.add_column("Index", justify="center", style="cyan")
        fn_table.add_column("Function Name", style="bold")
        fn_table.add_column("Instructions", justify="right")
        fn_table.add_column("Size (Bytes)", justify="right")
        fn_table.add_column("Ratio (%)", justify="right", style="green")

        for f in report.functions[:top]:
            fn_table.add_row(str(f.func_index), f"${f.name}", str(f.instruction_count), f"{f.size:,}", f"{f.percentage:.1f}%")
        console.print(fn_table)


@app.command()
def dataflow(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    func: int = typer.Option(0, "--func", "-f", help="Function index to analyze"),
) -> None:
    """Perform static data-flow and stack-effect simulation on a function."""
    module = parse_wasm(wasm_file)
    result = analyze_dataflow(module, func)

    table = Table(
        title=f"Data-Flow & Stack Effect: ${result.func_name} (Peak Depth: {result.max_stack_depth})",
        border_style="dim",
    )
    table.add_column("PC", justify="right", style="yellow")
    table.add_column("Mnemonic", style="bold")
    table.add_column("Operands", style="dim")
    table.add_column("Pops", justify="center")
    table.add_column("Pushes", justify="center")
    table.add_column("Depth In", justify="right", style="cyan")
    table.add_column("Depth Out", justify="right", style="green")
    table.add_column("Local Reads", style="dim")
    table.add_column("Local Writes", style="dim")

    for step in result.instructions:
        table.add_row(
            f"0x{step.pc:02X}",
            step.mnemonic,
            step.operands,
            str(step.stack_pops),
            str(step.stack_pushes),
            str(step.stack_depth_in),
            str(step.stack_depth_out),
            str(step.reads_locals) if step.reads_locals else "-",
            str(step.writes_locals) if step.writes_locals else "-",
        )
    console.print(table)


@app.command()
def report(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    output: Path = typer.Option(Path("report.html"), "--output", "-o", help="Output HTML file path"),
) -> None:
    """Generate a self-contained standalone HTML audit report."""
    module = parse_wasm(wasm_file)
    html_content = generate_html_report(module, title=f"WasmLens Report: {wasm_file.name}")
    output.write_text(html_content, encoding="utf-8")
    console.print(f"[bold green]Standalone HTML audit report generated:[/bold green] {output.resolve()}")


@app.command()
def header(
    wasm_file: Path = typer.Argument(..., help="Path to WebAssembly binary (.wasm)"),
    output: Path = typer.Option(Path("module.h"), "--output", "-o", help="Output C header file path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Module C identifier name"),
) -> None:
    """Export WebAssembly function prototypes to standard C/C++ header (.h)."""
    module = parse_wasm(wasm_file)
    mod_name = name or wasm_file.stem
    c_header = generate_c_header(module, module_name=mod_name)
    output.write_text(c_header, encoding="utf-8")
    console.print(f"[bold green]C header exported:[/bold green] {output.resolve()}")


@app.command()
def studio(
    wasm_file: Optional[Path] = typer.Option(None, "--wasm", "-w", help="Initial WASM file to inspect"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind to"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
) -> None:
    """Launch the interactive Web Studio in your browser."""
    import uvicorn
    from wasmlens.web.app import create_app

    if wasm_file:
        os.environ["WASMLENS_INITIAL_FILE"] = str(wasm_file.resolve())

    console.print(f"[bold cyan]Starting WasmLens Studio at http://{host}:{port}...[/bold cyan]")
    app_instance = create_app()
    uvicorn.run(app_instance, host=host, port=port)


if __name__ == "__main__":
    app()
