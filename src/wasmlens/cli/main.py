"""WasmLens Command Line Interface (CLI) powered by Typer and Rich."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from wasmlens.cfg.analyzer import CFGAnalyzer
from wasmlens.cfg.builder import CFGBuilder
from wasmlens.cfg.export import to_ascii, to_dot, to_json, to_mermaid
from wasmlens.decompiler.reconstructor import Decompiler
from wasmlens.disassembler.wat_formatter import (
    disassemble_function,
    disassemble_module,
)
from wasmlens.emulator.vm import WasmVM
from wasmlens.memory.hexdump import format_hexdump
from wasmlens.memory.inspector import MemoryInspector
from wasmlens.parser.module import parse_wasm
from wasmlens.parser.types import ExternalKind

app = typer.Typer(
    name="wasmlens",
    help="Interactive WebAssembly 2.0 binary decompiler, CFG visualizer, and memory inspector.",
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

    # Complexity overview
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
    max_steps: int = typer.Option(5000, "--max-steps", help="Maximum execution step threshold"),
) -> None:
    """Step-by-step bytecode emulator and runtime debugger."""
    module = parse_wasm(wasm_file)
    vm = WasmVM(module)
    fn_name = module.get_function_name(func)

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
