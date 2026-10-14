# WasmLens Architecture Specification

This document details the internal design, data flow, and invariants of the WasmLens pipeline.

## 1. Binary Parsing Pipeline

The WebAssembly binary decoding adheres strictly to the WebAssembly 2.0 core specification.

### 1.1 Binary Header
Every valid WebAssembly module begins with an 8-byte preamble:
- Magic bytes: `\x00asm` (0x00, 0x61, 0x73, 0x6D)
- Binary version: `\x01\x00\x00\x00` (Version 1 / Core 2.0)

### 1.2 LEB128 Reader
WebAssembly encodes integer lengths, indices, and immediate constants using Variable-Length LEB128:
- `unsigned LEB128 (u32, u64)`: Used for section sizes, type vector lengths, local counts, indices.
- `signed LEB128 (i32, i64)`: Used for signed immediate constants in numeric instructions (`i32.const`, `i64.const`).

### 1.3 Section Identifiers
Sections appear in the following standard order:
- 0: Custom (Names, source maps)
- 1: Type (Function signatures: parameters and results)
- 2: Import (Imported functions, tables, memories, globals)
- 3: Function (Type indices of internally declared functions)
- 4: Table (Table definitions and limits)
- 5: Memory (Linear memory definitions and 64KB page limits)
- 6: Global (Global definitions with type, mutability, and initialization expressions)
- 7: Export (Exported declarations accessible by the host)
- 8: Start (Optional entry point function index executed on initialization)
- 9: Element (Segments initializing table elements)
- 10: Code (Function bodies containing local variable counts and instruction streams)
- 11: Data (Data segments initializing linear memory)
- 12: DataCount (Count of data segments used by bulk memory operations)

---

## 2. Control-Flow Graph (CFG) Construction

The CFG engine turns linear bytecode sequences into a directed graph of Basic Blocks:

### 2.1 Basic Block Partitioning
A block boundary (leader) is created at:
1. The first instruction of each function body.
2. The target of any branch instruction (`br`, `br_if`, `br_table`).
3. The instruction immediately following an unconditional control transfer (`br`, `return`, `unreachable`).
4. Structured block boundaries (`block`, `loop`, `if`, `else`, `end`).

### 2.2 Edge Classification
Edges between basic blocks are labeled with specific semantics:
- `fallthrough`: Sequential progression between consecutive blocks.
- `branch_true`: Conditional branch taken when top of stack is non-zero.
- `branch_false`: Conditional branch fallthrough when condition is zero.
- `loop_back`: Back-edge targeting the entry of a `loop` structure.
- `jump_table`: Edge originating from a `br_table` jump vector index.

---

## 3. Linear Memory Model

WebAssembly linear memory consists of contiguous bytes allocated in 64KB (65,536 bytes) pages.

### 3.1 Page Inspection
WasmLens tracks:
- Initial and maximum page allocations.
- Active data segments placed at specific byte offsets at initialization.
- Passive segments ready for `memory.init` copying.
- Hexadecimal representation with ASCII gutter and memory boundary annotations.

---

## 4. Bytecode Emulator Runtime

The emulator implements a complete Wasm 2.0 evaluation loop:
- **Operand Stack**: Push and pop operations for i32, i64, f32, f64.
- **Activation Frame**: Holds function arguments, local variables, and return program counter.
- **Label Stack**: Tracks structured control flow targets (`block`, `loop`, `if`).
- **Linear Memory Buffer**: Sized bytearray reflecting simulated memory.
- **State Tracer**: Captures step snapshots for replay in the terminal debugger and Web Studio.
