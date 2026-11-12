"""Why a read-side operation rejected its request (slice 224, D5, D7, D8).

One vocabulary for ``status``, ``decisions`` and ``mark_read``: each uses the codes
that apply to it. The CLI exits 1 for a rejected result.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ValidationError

from amoeba.store.programs import list_programs
from amoeba.store.store import Transaction


class RejectCode(StrEnum):
    """The closed set of rejection reasons."""

    UNKNOWN_PROGRAM = "unknown_program"
    MALFORMED = "malformed"
    BEYOND_LAST_RECORD = "beyond_last_record"


def validation_problems(error: ValidationError) -> tuple[str, ...]:
    """One line per pydantic error: the field path, then the message."""
    return tuple(
        f"{'.'.join(str(part) for part in problem['loc']) or 'document'}: "
        f"{problem['msg']}"
        for problem in error.errors()
    )


def unknown_program_problem(transaction: Transaction, program: str) -> str | None:
    """A message listing the known ids when ``program`` is not one, else ``None``."""
    known = [entry.program_id for entry in list_programs(transaction)]
    if program in known:
        return None
    listed = ", ".join(known) if known else "none registered"
    return f"unknown program {program!r}; known programs: {listed}"
