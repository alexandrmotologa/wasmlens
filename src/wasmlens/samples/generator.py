"""Generator for authentic sample WebAssembly 2.0 binaries."""

import os
from pathlib import Path
from wasmlens.parser.leb128 import encode_i32, encode_u32


def create_factorial_wasm() -> bytes:
    """Generate iterative factorial wasm module: fact(n: i32) -> i32."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type 0: (i32) -> i32
    type_payload = bytes([0x01, 0x60, 0x01, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Function 0 uses Type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Export "factorial" -> func 0
    name = b"factorial"
    export_payload = bytes([0x01]) + encode_u32(len(name)) + name + bytes([0x00, 0x00])
    export_sec = bytes([0x07]) + encode_u32(len(export_payload)) + export_payload

    # Code body:
    # 1 local of type i32 (accumulator)
    # instructions:
    #   i32.const 1
    #   local.set 1
    #   block empty
    #     loop empty
    #       local.get 0
    #       i32.const 1
    #       i32.le_s
    #       br_if 1  (break to block)
    #       local.get 1
    #       local.get 0
    #       i32.mul
    #       local.set 1
    #       local.get 0
    #       i32.const 1
    #       i32.sub
    #       local.set 0
    #       br 0     (loop back)
    #     end
    #   end
    #   local.get 1
    #   end
    instructions = bytes([
        # Locals vector: 1 entry: count 1, type 0x7F (i32)
        0x01, 0x01, 0x7F,
        # i32.const 1
        0x41, 0x01,
        # local.set 1
        0x21, 0x01,
        # block (empty blocktype 0x40)
        0x02, 0x40,
        # loop (empty blocktype 0x40)
        0x03, 0x40,
        # local.get 0
        0x20, 0x00,
        # i32.const 1
        0x41, 0x01,
        # i32.le_s
        0x4C,
        # br_if 1
        0x0D, 0x01,
        # local.get 1
        0x20, 0x01,
        # local.get 0
        0x20, 0x00,
        # i32.mul
        0x6C,
        # local.set 1
        0x21, 0x01,
        # local.get 0
        0x20, 0x00,
        # i32.const 1
        0x41, 0x01,
        # i32.sub
        0x6B,
        # local.set 0
        0x21, 0x00,
        # br 0
        0x0C, 0x00,
        # end (loop)
        0x0B,
        # end (block)
        0x0B,
        # local.get 1
        0x20, 0x01,
        # end (func)
        0x0B,
    ])

    body = encode_u32(len(instructions)) + instructions
    code_payload = bytes([0x01]) + body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    # Custom name section
    fn_name = b"factorial"
    fn_entry = bytes([0x00]) + encode_u32(len(fn_name)) + fn_name
    subsec_payload = bytes([0x01]) + fn_entry
    subsec = bytes([0x01]) + encode_u32(len(subsec_payload)) + subsec_payload
    sec_name = b"name"
    custom_payload = encode_u32(len(sec_name)) + sec_name + subsec
    custom_sec = bytes([0x00]) + encode_u32(len(custom_payload)) + custom_payload

    return header + type_sec + func_sec + export_sec + code_sec + custom_sec


def create_fibonacci_wasm() -> bytes:
    """Generate recursive fibonacci wasm module: fib(n: i32) -> i32."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type 0: (i32) -> i32
    type_payload = bytes([0x01, 0x60, 0x01, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Func 0: Type 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Export "fib" -> func 0
    name = b"fib"
    export_payload = bytes([0x01]) + encode_u32(len(name)) + name + bytes([0x00, 0x00])
    export_sec = bytes([0x07]) + encode_u32(len(export_payload)) + export_payload

    # Instructions:
    #   local.get 0
    #   i32.const 2
    #   i32.lt_s
    #   if (result i32)
    #     local.get 0
    #   else
    #     local.get 0
    #     i32.const 1
    #     i32.sub
    #     call 0
    #     local.get 0
    #     i32.const 2
    #     i32.sub
    #     call 0
    #     i32.add
    #   end
    #   end
    instructions = bytes([
        0x00,        # 0 locals
        0x20, 0x00,  # local.get 0
        0x41, 0x02,  # i32.const 2
        0x48,        # i32.lt_s
        0x04, 0x7F,  # if (result i32)
        0x20, 0x00,  # local.get 0
        0x05,        # else
        0x20, 0x00,  # local.get 0
        0x41, 0x01,  # i32.const 1
        0x6B,        # i32.sub
        0x10, 0x00,  # call 0
        0x20, 0x00,  # local.get 0
        0x41, 0x02,  # i32.const 2
        0x6B,        # i32.sub
        0x10, 0x00,  # call 0
        0x6A,        # i32.add
        0x0B,        # end (if)
        0x0B,        # end (func)
    ])

    body = encode_u32(len(instructions)) + instructions
    code_payload = bytes([0x01]) + body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    # Name section
    fn_name = b"fib"
    fn_entry = bytes([0x00]) + encode_u32(len(fn_name)) + fn_name
    subsec = bytes([0x01]) + encode_u32(len(bytes([0x01]) + fn_entry)) + bytes([0x01]) + fn_entry
    sec_name = b"name"
    custom_payload = encode_u32(len(sec_name)) + sec_name + subsec
    custom_sec = bytes([0x00]) + encode_u32(len(custom_payload)) + custom_payload

    return header + type_sec + func_sec + export_sec + code_sec + custom_sec


def create_memory_ops_wasm() -> bytes:
    """Generate memory operations module with linear memory, data segments, store and load."""
    header = b"\x00asm\x01\x00\x00\x00"

    # Type 0: (i32, i32) -> i32  (store_and_load: ptr, val)
    type_payload = bytes([0x01, 0x60, 0x02, 0x7F, 0x7F, 0x01, 0x7F])
    type_sec = bytes([0x01]) + encode_u32(len(type_payload)) + type_payload

    # Func 0
    func_payload = bytes([0x01, 0x00])
    func_sec = bytes([0x03]) + encode_u32(len(func_payload)) + func_payload

    # Memory: min=1, max=2
    mem_payload = bytes([0x01, 0x01, 0x01, 0x02])
    mem_sec = bytes([0x05]) + encode_u32(len(mem_payload)) + mem_payload

    # Exports: "memory" (mem 0), "store_and_load" (func 0)
    exp_mem_name = b"memory"
    exp_mem = encode_u32(len(exp_mem_name)) + exp_mem_name + bytes([0x02, 0x00])
    exp_fn_name = b"store_and_load"
    exp_fn = encode_u32(len(exp_fn_name)) + exp_fn_name + bytes([0x00, 0x00])
    export_payload = bytes([0x02]) + exp_mem + exp_fn
    export_sec = bytes([0x07]) + encode_u32(len(export_payload)) + export_payload

    # Code:
    #   local.get 0 (ptr)
    #   local.get 1 (val)
    #   i32.store 2 0 (align=2, offset=0)
    #   local.get 0 (ptr)
    #   i32.load 2 0 (align=2, offset=0)
    #   end
    instructions = bytes([
        0x00,              # 0 locals
        0x20, 0x00,        # local.get 0
        0x20, 0x01,        # local.get 1
        0x36, 0x02, 0x00,  # i32.store 2 0
        0x20, 0x00,        # local.get 0
        0x28, 0x02, 0x00,  # i32.load 2 0
        0x0B,              # end
    ])
    body = encode_u32(len(instructions)) + instructions
    code_payload = bytes([0x01]) + body
    code_sec = bytes([0x0A]) + encode_u32(len(code_payload)) + code_payload

    # Data segment: at offset 0, banner text: "WasmLens Runtime 2026\x00"
    banner = b"WasmLens Runtime 2026\x00"
    data_payload = bytes([
        0x01,              # 1 segment
        0x00,              # flags=0 (active mem 0)
        0x41, 0x00, 0x0B,  # i32.const 0, end
    ]) + encode_u32(len(banner)) + banner
    data_sec = bytes([0x0B]) + encode_u32(len(data_payload)) + data_payload

    return header + type_sec + func_sec + mem_sec + export_sec + code_sec + data_sec


def generate_all_samples(target_dir: Path) -> None:
    """Generate all sample binaries into the target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    samples = {
        "factorial.wasm": create_factorial_wasm(),
        "fibonacci.wasm": create_fibonacci_wasm(),
        "memory_ops.wasm": create_memory_ops_wasm(),
    }
    for filename, data in samples.items():
        with open(target_dir / filename, "wb") as f:
            f.write(data)
