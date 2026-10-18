"""Fixtures for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from serve_harness import TlsFiles


def _openssl() -> str:
    found = shutil.which("openssl")
    if found is None:
        pytest.fail("openssl is not on PATH; the TLS tests need it to make a cert")
    return found


@pytest.fixture(scope="session")
def tls_files(tmp_path_factory: pytest.TempPathFactory) -> TlsFiles:
    """Written once per session into a pytest temp directory."""
    directory = tmp_path_factory.mktemp("tls")
    openssl = _openssl()
    certfile, keyfile = directory / "cert.pem", directory / "key.pem"
    other_keyfile = directory / "other-key.pem"
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes"]
        + ["-subj", "/CN=localhost", "-days", "1"]
        + ["-keyout", str(keyfile), "-out", str(certfile)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-out", str(other_keyfile)],
        check=True,
        capture_output=True,
    )
    return TlsFiles(certfile=certfile, keyfile=keyfile, other_keyfile=other_keyfile)
