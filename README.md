# WasmLens

Interactive WebAssembly 2.0 binary decompiler, control-flow graph (CFG) visualizer, linear memory inspector, and step-by-step bytecode emulator.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

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
- **Bytecode Emulator**: Interprets instructions with full operand stack, activation frames, call depth tracking, and step-by-step state diffing.
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
                      |  (Step Execution & Tracing) |
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

### Generate Control-Flow Graph

```bash
wasmlens cfg sample.wasm --func 0 --format mermaid
wasmlens cfg sample.wasm --func 0 --format dot -o cfg.dot
```

### Inspect Linear Memory

```bash
wasmlens mem sample.wasm --page 0 --length 256
```

### Step-by-Step Bytecode Emulation

```bash
wasmlens emu sample.wasm --func 0 --arg 5 --step
```

### Launch Interactive Web Studio

```bash
wasmlens studio --port 8080
```

## Web Studio

The web studio runs locally on top of FastAPI and delivers:
- Drag-and-drop `.wasm` binary loader.
- Interactive CFG viewer with branch and loop edge coloring.
- Synchronized disassembly and block inspector.
- 64KB linear memory page map with interactive hex gutter.
- Step-by-step emulator workbench with stack and register inspection.

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.
