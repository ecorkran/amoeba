"""A structural check that a module does no I/O: its imports and calls, not its text."""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

#: Modules whose import means the module can reach the file system or a process.
IO_MODULES = frozenset({"subprocess", "pathlib", "os", "shutil", "io", "tempfile"})
#: Calls that read or write a file whatever object they are on.
IO_CALLS = frozenset({"open", "read_text", "write_text", "read_bytes", "write_bytes"})


def io_use(module: ModuleType) -> list[str]:
    """What in ``module`` imports an I/O module or calls an I/O function."""
    found: list[str] = []
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] in IO_MODULES]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in IO_MODULES:
                found.append(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            name = func.attr if isinstance(func, ast.Attribute) else name
            if name in IO_CALLS:
                found.append(f"{name}()")
    return found
