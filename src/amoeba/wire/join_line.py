"""The join line: ``<address>,<fingerprint>,<token>`` (slice 260, D3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from amoeba.wire.address import split_address
from amoeba.wire.fingerprint import normalize_fingerprint

JOIN_LINE_SEPARATOR: Final = ","
#: Field names, in order; a malformed line is described by these, never by values.
JOIN_LINE_FIELDS: Final = ("address", "fingerprint", "token")


class JoinError(Exception):
    """`amoeba join` or `amoeba leave` could not do what was asked (always exit 3)."""


@dataclass(frozen=True)
class JoinLine:
    address: str
    fingerprint: str
    token: str


def format_join_line(address: str, fingerprint: str, token: str) -> str:
    """The line `amoeba hub invite` prints."""
    return JOIN_LINE_SEPARATOR.join((address, fingerprint, token))


def parse_join_line(text: str) -> JoinLine:
    """Read a join line; strips surrounding whitespace and quotes."""
    fields = text.strip().strip("\"'").strip().split(JOIN_LINE_SEPARATOR)
    if len(fields) != len(JOIN_LINE_FIELDS) or not all(f.strip() for f in fields):
        shape = JOIN_LINE_SEPARATOR.join(f"<{name}>" for name in JOIN_LINE_FIELDS)
        raise JoinError(
            f"not a join line: expected {len(JOIN_LINE_FIELDS)} fields as {shape} "
            f"with no spaces, got {len(fields)}; copy the line "
            "`amoeba hub invite <machine>` printed"
        )
    address, fingerprint, token = (field.strip() for field in fields)
    try:
        split_address(address)
    except ValueError as error:
        raise JoinError(f"the join line's address is wrong: {error}") from error
    return JoinLine(address, normalize_fingerprint(fingerprint), token)
