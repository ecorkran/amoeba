"""The bind policy: every row of the LLD's D3 table, and every TLS failure."""

from __future__ import annotations

from pathlib import Path

import pytest
from serve_harness import TlsFiles

from amoeba.serve.policy import (
    RefusalRule,
    ServeRefusedError,
    check_bind,
    is_loopback,
)
from amoeba.serve.settings import MIN_TOKEN_LENGTH, ServeSettings

LOOPBACK = "127.0.0.1"
OTHER = "0.0.0.0"
#: Test values only: long enough, and one character short.
GOOD_TOKEN = "t" * MIN_TOKEN_LENGTH
SHORT_TOKEN = "s" * (MIN_TOKEN_LENGTH - 1)


@pytest.mark.parametrize(
    "host", ["localhost", "LocalHost", "127.0.0.1", "127.1.2.3", "::1"]
)
def test_loopback_hosts(host: str) -> None:
    assert is_loopback(host)


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "::", "example.com", "192.168.1.1", "[::1]", "localhost.example"],
)
def test_non_loopback_hosts(host: str) -> None:
    assert not is_loopback(host)


def _settings(host: str, tls: TlsFiles, which: str) -> ServeSettings:
    """``which``: "none", "both", "cert" (cert only), or "key" (key only)."""
    certfile = tls.certfile if which in ("both", "cert") else None
    keyfile = tls.keyfile if which in ("both", "key") else None
    return ServeSettings(host=host, tls_certfile=certfile, tls_keyfile=keyfile)


#: (host, token, TLS files, expected refusal or None for "serves").
_TABLE: list[tuple[str, str | None, str, RefusalRule | None]] = [
    # D3 row 1: loopback, any token, neither or both TLS files → serves.
    (LOOPBACK, None, "none", None),
    (LOOPBACK, GOOD_TOKEN, "none", None),
    (LOOPBACK, None, "both", None),
    (LOOPBACK, GOOD_TOKEN, "both", None),
    # D3 row 2: other host, token, both TLS files → serves over HTTPS.
    (OTHER, GOOD_TOKEN, "both", None),
    # D3 row 3: other host, no token, any TLS → token_required.
    (OTHER, None, "none", RefusalRule.TOKEN_REQUIRED),
    (OTHER, None, "both", RefusalRule.TOKEN_REQUIRED),
    (OTHER, None, "cert", RefusalRule.TOKEN_REQUIRED),
    # D3 row 4: other host, token, a TLS file missing → tls_required.
    (OTHER, GOOD_TOKEN, "none", RefusalRule.TLS_REQUIRED),
    (OTHER, GOOD_TOKEN, "cert", RefusalRule.TLS_REQUIRED),
    (OTHER, GOOD_TOKEN, "key", RefusalRule.TLS_REQUIRED),
    # D3 row 5: a short token, any bind → token_too_short.
    (LOOPBACK, SHORT_TOKEN, "none", RefusalRule.TOKEN_TOO_SHORT),
    (OTHER, SHORT_TOKEN, "both", RefusalRule.TOKEN_TOO_SHORT),
    (OTHER, SHORT_TOKEN, "none", RefusalRule.TOKEN_TOO_SHORT),
    # D3 row 6: loopback, exactly one TLS file → tls_required.
    (LOOPBACK, None, "cert", RefusalRule.TLS_REQUIRED),
    (LOOPBACK, GOOD_TOKEN, "key", RefusalRule.TLS_REQUIRED),
]


@pytest.mark.parametrize(("host", "token", "which", "expected"), _TABLE)
def test_d3_table(
    tls_files: TlsFiles,
    host: str,
    token: str | None,
    which: str,
    expected: RefusalRule | None,
) -> None:
    settings = _settings(host, tls_files, which)
    if expected is None:
        check_bind(settings, token)
        return
    with pytest.raises(ServeRefusedError) as refused:
        check_bind(settings, token)
    assert refused.value.rule is expected
    assert expected.value in str(refused.value)


#: (cert, key, the path the detail must name), each as a name for a file the
#: test provides: cert, key, other_key, missing, directory.
_UNUSABLE = [
    pytest.param("missing", "key", "missing", id="no-cert"),
    pytest.param("cert", "missing", "missing", id="no-key"),
    pytest.param("directory", "key", "directory", id="dir-cert"),
    pytest.param("cert", "other_key", "other_key", id="mismatch"),
]


@pytest.mark.parametrize(("cert_name", "key_name", "named_name"), _UNUSABLE)
@pytest.mark.parametrize("host", [LOOPBACK, OTHER])
def test_tls_unusable(
    tls_files: TlsFiles,
    tmp_path: Path,
    cert_name: str,
    key_name: str,
    named_name: str,
    host: str,
) -> None:
    files = {
        "cert": tls_files.certfile,
        "key": tls_files.keyfile,
        "other_key": tls_files.other_keyfile,
        "missing": tmp_path / "missing.pem",
        "directory": tmp_path,
    }
    certfile, keyfile, named = files[cert_name], files[key_name], files[named_name]
    settings = ServeSettings(host=host, tls_certfile=certfile, tls_keyfile=keyfile)

    with pytest.raises(ServeRefusedError) as refused:
        check_bind(settings, GOOD_TOKEN)

    assert refused.value.rule is RefusalRule.TLS_UNUSABLE
    assert str(named) in refused.value.detail


def test_a_short_token_refusal_does_not_contain_the_token() -> None:
    token = "secret-but-short-" + "x" * 5

    with pytest.raises(ServeRefusedError) as refused:
        check_bind(ServeSettings(), token)

    assert token not in str(refused.value)
    assert token not in refused.value.detail
