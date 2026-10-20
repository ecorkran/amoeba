"""``amoeba serve`` through real subprocesses: refusals, HTTPS, bind, shutdown."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2
import pytest
from cli_harness import (
    BackgroundCli,
    await_listening,
    cli_environment,
    free_port,
    run_cli,
    start_serve,
)
from serve_harness import TEST_TOKEN, TlsFiles

from amoeba.cli.main import ExitCode
from amoeba.serve.settings import MIN_TOKEN_LENGTH, TOKEN_ENV_VAR, ServeSettings
from amoeba.store import Store

#: How far past the shutdown grace a SIGTERM'd server may take to exit.
_EXIT_MARGIN_SECONDS = 3.0


@pytest.fixture
def supervisor(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


def _environment(supervisor: Path, token: str | None) -> dict[str, str]:
    environment = cli_environment(supervisor)  # never carries a token
    if token is not None:
        environment[TOKEN_ENV_VAR] = token
    return environment


_OFF_LOOPBACK = ["--host", "0.0.0.0"]

#: (extra arguments, token, expected rule). ``{name}`` in an argument is a file
#: the test provides: cert, key, other_key, unreadable_key, missing.
_REFUSALS = [
    pytest.param(_OFF_LOOPBACK, None, "token_required", id="no-token"),
    pytest.param(_OFF_LOOPBACK, TEST_TOKEN, "tls_required", id="no-tls"),
    pytest.param(
        _OFF_LOOPBACK,
        "s" * (MIN_TOKEN_LENGTH - 1),
        "token_too_short",
        id="short-token",
    ),
    pytest.param(
        [*_OFF_LOOPBACK, "--tls-cert", "{missing}", "--tls-key", "{key}"],
        TEST_TOKEN,
        "tls_unusable",
        id="missing-cert",
    ),
    pytest.param(
        [*_OFF_LOOPBACK, "--tls-cert", "{cert}", "--tls-key", "{unreadable_key}"],
        TEST_TOKEN,
        "tls_unusable",
        id="unreadable-key",
    ),
    pytest.param(
        [*_OFF_LOOPBACK, "--tls-cert", "{cert}", "--tls-key", "{other_key}"],
        TEST_TOKEN,
        "tls_unusable",
        id="mismatched-key",
    ),
]


def _unreadable_copy(source: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "unreadable-key.pem"
    copy.write_bytes(source.read_bytes())
    copy.chmod(0)
    return copy


@pytest.mark.parametrize(("arguments", "token", "rule"), _REFUSALS)
def test_an_unsafe_bind_exits_13_naming_the_rule(
    supervisor: Path,
    tls_files: TlsFiles,
    tmp_path: Path,
    arguments: list[str],
    token: str | None,
    rule: str,
) -> None:
    files = {
        "cert": tls_files.certfile,
        "key": tls_files.keyfile,
        "other_key": tls_files.other_keyfile,
        "unreadable_key": _unreadable_copy(tls_files.keyfile, tmp_path),
        "missing": tmp_path / "nope.pem",
    }
    resolved = [argument.format(**files) for argument in arguments]

    result = run_cli(
        ["serve", *resolved], supervisor, environment=_environment(supervisor, token)
    )

    assert result.returncode == ExitCode.SERVE_REFUSED
    assert rule in result.stderr
    if token is not None:
        assert token not in result.stdout + result.stderr


def _stop(process: BackgroundCli) -> tuple[int, str]:
    os.kill(process.pid, signal.SIGTERM)
    output = process.output()
    return output.returncode, output.stdout + output.stderr


def test_https_with_a_token_serves_and_never_logs_it(
    supervisor: Path, tls_files: TlsFiles
) -> None:
    port = free_port()
    process = start_serve(
        supervisor,
        [
            "--port",
            str(port),
            "--tls-cert",
            str(tls_files.certfile),
            "--tls-key",
            str(tls_files.keyfile),
        ],
        _environment(supervisor, TEST_TOKEN),
    )
    try:
        await_listening(port, process)
        url = f"https://127.0.0.1:{port}/v1/listings/projects"
        with httpx2.Client(verify=False, timeout=5.0) as client:
            without = client.get(url)
            wrong = client.get(url, headers={"Authorization": "Bearer " + "f" * 48})
            correct = client.get(url, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        returncode, output = _stop(process)
    finally:
        process.cleanup()

    assert (without.status_code, wrong.status_code, correct.status_code) == (
        401,
        401,
        200,
    )
    assert correct.json()["rows"] == []
    assert returncode == -signal.SIGTERM  # uvicorn re-raises it after shutdown
    assert "GET /v1/listings/projects" in output  # uvicorn's access log is on
    assert TEST_TOKEN not in output


def test_a_port_already_in_use_exits_1(supervisor: Path) -> None:
    with socket.socket() as occupier:
        occupier.bind(("127.0.0.1", 0))
        occupier.listen()
        port = occupier.getsockname()[1]

        result = run_cli(
            ["serve", "--port", str(port)],
            supervisor,
            environment=_environment(supervisor, None),
        )

    assert result.returncode == ExitCode.FAILURE


def test_sigterm_with_a_stream_open_exits_within_the_grace(supervisor: Path) -> None:
    with Store.open(supervisor / "demo.sqlite3"):
        pass
    port = free_port()
    process = start_serve(
        supervisor, ["--port", str(port)], _environment(supervisor, None)
    )
    stream: socket.socket | None = None
    try:
        await_listening(port, process)
        stream = socket.create_connection(("127.0.0.1", port))
        stream.sendall(
            b"GET /v1/projects/demo/feed HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        )
        assert b"200" in stream.recv(64)
        started = time.monotonic()
        returncode, _ = _stop(process)
        elapsed = time.monotonic() - started
    finally:
        if stream is not None:
            stream.close()
        process.cleanup()

    assert returncode == -signal.SIGTERM  # uvicorn re-raises it after shutdown
    assert elapsed < ServeSettings().shutdown_grace_seconds + _EXIT_MARGIN_SECONDS


def test_other_commands_never_load_uvicorn(supervisor: Path) -> None:
    script = (
        "import sys\n"
        "from amoeba.cli.main import main\n"
        "main(['inspect', 'projects'])\n"
        "print('uvicorn' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor),
        timeout=30,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "False"
