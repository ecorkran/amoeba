"""The join line and the certificate fingerprint (slice 260, D3)."""

from __future__ import annotations

import hashlib
import ssl

import pytest

from amoeba.wire.fingerprint import fingerprint, normalize_fingerprint
from amoeba.wire.join_line import JoinError, format_join_line, parse_join_line

TOKEN = "tok-value-for-the-test-only"
PRINT = "ab12" * 16


def test_a_line_round_trips() -> None:
    line = parse_join_line(format_join_line("hub.local:8443", PRINT, TOKEN))

    assert (line.address, line.fingerprint, line.token) == (
        "hub.local:8443",
        PRINT,
        TOKEN,
    )


def test_whitespace_and_quotes_are_stripped() -> None:
    text = f'  "hub.local:8443,{PRINT},{TOKEN}"\n'

    assert parse_join_line(text).token == TOKEN


@pytest.mark.parametrize("fields", [["a", "b"], ["a", "b", TOKEN, "d"]])
def test_the_wrong_number_of_fields_never_shows_the_token(fields: list[str]) -> None:
    with pytest.raises(JoinError) as raised:
        parse_join_line(",".join(fields))

    assert TOKEN not in str(raised.value)
    assert "<address>,<fingerprint>,<token>" in str(raised.value)


def test_a_fingerprint_with_colons_and_upper_case_is_normalized() -> None:
    typed = ":".join(PRINT[i : i + 2].upper() for i in range(0, len(PRINT), 2))

    assert normalize_fingerprint(typed) == PRINT
    assert parse_join_line(f"h:1,{typed},{TOKEN}").fingerprint == PRINT


def test_the_fingerprint_is_the_sha256_of_the_der_bytes() -> None:
    der = b"\x30\x03\x02\x01\x01"
    pem = ssl.DER_cert_to_PEM_cert(der)

    assert fingerprint(der) == hashlib.sha256(der).hexdigest()
    assert fingerprint(pem) == hashlib.sha256(der).hexdigest()
