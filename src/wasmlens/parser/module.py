"""Module parser coordinating binary reading, section dispatching, and symbol resolution."""

from __future__ import annotations

import os
from typing import Union

from wasmlens.parser.reader import BinaryReader, BinaryReaderError
from wasmlens.parser.section_parser import (
    parse_code_section,
    parse_data_section,
    parse_element_section,
    parse_export_section,
    parse_function_section,
    parse_global_section,
    parse_import_section,
    parse_memory_section,
    parse_name_section,
    parse_start_section,
    parse_table_section,
    parse_type_section,
)
from wasmlens.parser.types import (
    CustomSection,
    SectionId,
    SectionInfo,
    WasmModule,
)

WASM_MAGIC = b"\x00asm"
WASM_VERSION_1 = 1


def parse_wasm(source: Union[bytes, str, os.PathLike]) -> WasmModule:
    """Parse a WebAssembly binary from raw bytes or a file path.

    Returns:
        Fully populated WasmModule instance.
    """
    source_file = None
    if isinstance(source, (str, os.PathLike)):
        source_file = str(source)
        with open(source, "rb") as f:
            data = f.read()
    elif isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        raise TypeError(f"Expected bytes, str, or PathLike, got {type(source).__name__}")

    reader = BinaryReader(data)

    # 1. Preamble validation
    if reader.remaining < 8:
        raise BinaryReaderError("Binary is too short to be a valid WebAssembly module")

    magic = reader.read_bytes(4)
    if magic != WASM_MAGIC:
        raise BinaryReaderError(f"Invalid magic bytes: expected {WASM_MAGIC!r}, got {magic!r}")

    version_raw = reader.read_bytes(4)
    version = int.from_bytes(version_raw, byteorder="little")
    if version != WASM_VERSION_1:
        raise BinaryReaderError(f"Unsupported WebAssembly version: {version} (expected 1)")

    module = WasmModule(magic=magic, version=version, source_file=source_file)

    # 2. Iterate sections
    while reader.has_more:
        sec_start = reader.current_offset
        sec_id_byte = reader.read_byte()
        sec_size = reader.read_u32()
        payload_start = reader.current_offset

        try:
            sec_id = SectionId(sec_id_byte)
        except ValueError:
            raise BinaryReaderError(f"Unknown section ID {sec_id_byte} at offset {sec_start}")

        sec_reader = reader.sub_reader(sec_size)
        sec_info = SectionInfo(
            id=sec_id,
            size=sec_size,
            offset=sec_start,
            payload_offset=payload_start,
        )

        if sec_id == SectionId.CUSTOM:
            custom_name = sec_reader.read_name()
            custom_data = sec_reader.read_bytes(sec_reader.remaining)
            sec_info.name = custom_name
            module.custom_sections.append(
                CustomSection(name=custom_name, data=custom_data, offset=payload_start)
            )
            if custom_name == "name":
                fn_names, loc_names = parse_name_section(custom_data)
                module.function_names.update(fn_names)
                module.local_names.update(loc_names)

        elif sec_id == SectionId.TYPE:
            module.types = parse_type_section(sec_reader)

        elif sec_id == SectionId.IMPORT:
            module.imports = parse_import_section(sec_reader)

        elif sec_id == SectionId.FUNCTION:
            module.functions = parse_function_section(sec_reader)

        elif sec_id == SectionId.TABLE:
            module.tables = parse_table_section(sec_reader)

        elif sec_id == SectionId.MEMORY:
            module.memories = parse_memory_section(sec_reader)

        elif sec_id == SectionId.GLOBAL:
            module.globals = parse_global_section(sec_reader)

        elif sec_id == SectionId.EXPORT:
            module.exports = parse_export_section(sec_reader)

        elif sec_id == SectionId.START:
            module.start_func = parse_start_section(sec_reader)

        elif sec_id == SectionId.ELEMENT:
            module.elements = parse_element_section(sec_reader)

        elif sec_id == SectionId.CODE:
            module.codes = parse_code_section(
                sec_reader,
                func_type_indices=module.functions,
                imported_func_count=module.imported_func_count,
            )

        elif sec_id == SectionId.DATA:
            module.datas = parse_data_section(sec_reader)

        elif sec_id == SectionId.DATA_COUNT:
            module.data_count = sec_reader.read_u32()

        module.sections.append(sec_info)

    return module
