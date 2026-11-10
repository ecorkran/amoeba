"""``sq`` itself is not working (slice 223, D3)."""

from __future__ import annotations


class SquadronError(Exception):
    """Squadron gave no usable answer, or its run file cannot be used.

    "Cannot tell" is never "not mine": an operation that meets this stops with it
    (exit 3) before writing anything.
    """
