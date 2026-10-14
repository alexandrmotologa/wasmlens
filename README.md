<p align="center">
  <img src="docs/images/logo.png?raw=true" alt="WasmLens Logo" width="130" style="border-radius: 24px;" />
</p>

<h1 align="center">WasmLens</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <img src="https://img.shields.io/badge/Wasm-2.0-blueviolet.svg" alt="WebAssembly 2.0">
  <img src="https://img.shields.io/badge/tests-56%20passed-success.svg" alt="Tests: 56 passed">
  <img src="https://img.shields.io/badge/coverage-80%25-brightgreen.svg" alt="Coverage: 80%">
</p>

<p align="center">
  <strong>Interactive WebAssembly 2.0 binary decompiler, control-flow graph (CFG) visualizer, linear memory inspector, and time-travel debugger.</strong>
</p>

<p align="center">
  <img src="docs/images/wasmlens_demo.gif?raw=true" alt="WasmLens Interactive Studio Demo" width="900" />
</p>

---

## Overview

WasmLens parses compiled WebAssembly binaries directly from raw bytes, decomposes instructions into basic blocks, renders control-flow graphs, inspects 64KB linear memory page layouts, and provides a step-by-step execution runtime.

It uses an authentic WebAssembly 2.0 binary section parser and LEB128 decoder without external C/Rust binary wrappers.

## Core Capabilities

- **Binary Section Parsing**: Decodes all 13 standard WebAssembly 2.0 sections, vector/SIMD operations, and custom Name sections.
- **LEB128 Decoder**: Zero-copy stream reader for unsigned and signed variable-length integers with boundary validation.
- **Disassembler & Decompiler**: Converts raw bytecode to formatted WebAssembly Text (WAT) and structured expression trees.
- **Control-Flow Graph (CFG)**: Partitions instruction streams into basic blocks, detects loops and branches, and exports to DOT, Mermaid, or interactive browser graphs.
- **Linear Memory Inspector**: Maps memory allocations in 64KB pages, overlays active and passive data segments, and displays colored hex dumps.
- **Bytecode Emulator & Time-Travel**: Interprets instructions with full operand stack, activation frames, call depth tracking, breakpoints, watchpoints, and step-backward rewind.
- **Binary Mutation & Patching**: Replaces immediate constants and inserts NOP instructions directly into binary byte streams.
- **Binary Bloat Profiler**: Twiggy-style byte attribution across sections, compiled function bodies, and data segments.
- **Static Data-Flow Analyzer**: Simulates stack height transformations and tracks local variable def-use chains.
- **Terminal CLI & Web Studio**: Provides Rich CLI commands and a local FastAPI studio with interactive visualization.

## Architecture

```
                      +-----------------------------+
                      |   .wasm Binary / Byte Stream|
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |    LEB128 & Binary Reader   |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Wasm 2.0 Section Parser    |
                      |  (Types, Code, Data, etc.)  |
                      +--------------+--------------+
                                     |
            +------------------------+------------------------+
            |                        |                        |
            v                        v                        v
  +------------------+     +------------------+     +------------------+
  | Disassembler &   |     | CFG Engine &     |     | Linear Memory &  |
  | Decompiler (WAT) |     | Block Analyzer   |     | Page Inspector   |
  +--------+---------+     +--------+---------+     +--------+---------+
           |                        |                        |
           +------------------------+------------------------+
                                    |
                                    v
                      +-----------------------------+
                      |  Bytecode Emulator & VM     |
                      |  (Breakpoints & Rewind)     |
                      +--------------+--------------+
                                     |
                         +-----------+-----------+
                         |                       |
                         v                       v
               +-------------------+   +-------------------+
               |  Rich Typer CLI   |   | FastAPI Studio UI |
               +-------------------+   +-------------------+
```

## Installation

```bash
git clone https://github.com/alexandrmotologa/wasmlens.git
cd wasmlens
pip install -e ".[dev]"
```

## CLI Usage

### Inspect Module Sections

```bash
wasmlens info sample.wasm
```

### Disassemble to WAT

```bash
wasmlens disasm sample.wasm
wasmlens disasm sample.wasm --func 0
```

### Decompile to Structured C

```bash
wasmlens decompile sample.wasm --func 0
```

### Generate Control-Flow Graph

```bash
wasmlens cfg sample.wasm --func 0 --format mermaid
wasmlens cfg sample.wasm --func 0 --format dot -o cfg.dot
```

### Inspect Linear Memory

```bash
wasmlens mem sample.wasm --page 0 --length 256
```

### Step-by-Step Bytecode Emulation & Debugging

```bash
wasmlens emu sample.wasm --func 0 --arg 5 --step
wasmlens emu sample.wasm --func 0 --arg 5 --break-at 4 --watch 16
```

### Binary Mutation & Patching

```bash
wasmlens patch sample.wasm -o patched.wasm --func 0 --pc 0 --const 42
wasmlens patch sample.wasm -o patched.wasm --func 0 --pc 3 --nop
```

### Binary Bloat & Size Profiling

```bash
wasmlens bloat sample.wasm --top 10
wasmlens bloat sample.wasm --json
```

### Data-Flow & Stack Simulation

```bash
wasmlens dataflow sample.wasm --func 0
```

### Export Standalone HTML Report & C Header

```bash
wasmlens report sample.wasm -o audit.html
wasmlens header sample.wasm -o module.h
```

### Launch Interactive Web Studio

```bash
wasmlens studio --port 8080
```

## Web Studio & Visual Interface

The web studio runs locally on top of FastAPI and delivers:
- Drag-and-drop `.wasm` binary loader.
- Interactive CFG viewer with branch and loop edge coloring.
- Synchronized disassembly and block inspector.
- 64KB linear memory page map with interactive hex gutter.
- Step-by-step emulator workbench with stack, register inspection, and time-travel rewind.
- Breakpoint and memory watchpoint trap manager.
- Twiggy-style binary bloat space breakdown.
- Static data-flow and stack-effect simulator with local variable def-use tracking.
- In-browser bytecode patcher and instant `.wasm` re-download.

### Control-Flow Graph View
<p align="center">
  <img src="docs/images/wasmlens_cfg.png?raw=true" alt="WasmLens Control-Flow Graph" width="900" />
</p>

### Decompiler & WAT Disassembly
<p align="center">
  <img src="docs/images/wasmlens_decompiler.png?raw=true" alt="WasmLens Decompiler and WAT View" width="900" />
</p>

### 64KB Linear Memory Inspector & Hex Gutter
<p align="center">
  <img src="docs/images/wasmlens_memory.png?raw=true" alt="WasmLens Linear Memory Inspector" width="900" />
</p>

### Step Emulator VM & Debugger Traps
<p align="center">
  <img src="docs/images/wasmlens_emulator.png?raw=true" alt="WasmLens Step Emulator VM" width="900" />
</p>

### Binary Bloat Profiler
<p align="center">
  <img src="docs/images/wasmlens_bloat.png?raw=true" alt="WasmLens Binary Bloat Profiler" width="900" />
</p>

### Static Data-Flow & Stack Simulation
<p align="center">
  <img src="docs/images/wasmlens_dataflow.png?raw=true" alt="WasmLens Data-Flow Simulation" width="900" />
</p>

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.
