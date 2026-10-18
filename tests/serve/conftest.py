"""Fixtures for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from inspection_harness import SeededStore, seed_every_listing
from serve_harness import BASE_URL, ClientFactory, TlsFiles
from starlette.testclient import TestClient

from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings
from amoeba.store.paths import STORE_DIR_ENV_VAR


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


@pytest.fixture
def scratch_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch supervisor directory, also exported for any CLI the test runs."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    monkeypatch.setenv(STORE_DIR_ENV_VAR, str(directory))
    return directory


@pytest.fixture
def seeded(scratch_dir: Path) -> SeededStore:
    """The scratch directory seeded with a row for every listing."""
    return seed_every_listing(scratch_dir)


@pytest.fixture
def make_client(scratch_dir: Path) -> Iterator[ClientFactory]:
    """Build in-process clients over the scratch directory; closed at teardown."""
    clients: list[TestClient] = []

    def make(
        token: str | None = None,
        settings: ServeSettings | None = None,
        *,
        raise_server_exceptions: bool = True,
    ) -> TestClient:
        app = build_app(settings or ServeSettings(), token, scratch_dir)
        client = TestClient(
            app, base_url=BASE_URL, raise_server_exceptions=raise_server_exceptions
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
