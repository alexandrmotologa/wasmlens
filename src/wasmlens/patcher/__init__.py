"""WebAssembly binary patching and modification engine."""

from wasmlens.patcher.patcher import PatchError, WasmPatcher

__all__ = ["WasmPatcher", "PatchError"]
