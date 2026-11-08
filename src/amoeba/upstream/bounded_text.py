"""Cut text to the byte bound a stored or quoted failure detail may have."""

from __future__ import annotations

from amoeba.upstream.squadron.launch import STDERR_TAIL_LIMIT_BYTES


def cut_to_bound(text: str) -> str:
    """``text`` cut to ``STDERR_TAIL_LIMIT_BYTES`` of UTF-8, never mid-character."""
    encoded = text.encode("utf-8")
    if len(encoded) <= STDERR_TAIL_LIMIT_BYTES:
        return text
    return encoded[:STDERR_TAIL_LIMIT_BYTES].decode("utf-8", errors="ignore")
