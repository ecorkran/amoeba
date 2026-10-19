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
from amoeba.store.paths import STORE_DIR_ENV_VAR

#: How far past the shutdown grace a SIGTERM'd server may take to exit.
_EXIT_MARGIN_SECONDS = 3.0


@pytest.fixture
def supervisor(tmp_path: Path) -> Path:
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


def _environment(supervisor: Path, token: str | None) -> dict[str, str]:
    environment = cli_environment(supervisor)
    environment.pop(TOKEN_ENV_VAR, None)
    if token is not None:
        environment[TOKEN_ENV_VAR] = token
    return environment


def _unreadable_copy(source: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "unreadable-key.pem"
    copy.write_bytes(source.read_bytes())
    copy.chmod(0)
    return copy


def _refusal_cases(
    tls: TlsFiles, tmp_path: Path
) -> list[tuple[str, list[str], str | None, str]]:
    """(case id, extra arguments, token, expected rule)."""
    off_loopback = ["--host", "0.0.0.0"]
    cert = ["--tls-cert", str(tls.certfile)]
    return [
        ("no-token", off_loopback, None, "token_required"),
        ("no-tls", off_loopback, TEST_TOKEN, "tls_required"),
        ("short-token", off_loopback, "s" * (MIN_TOKEN_LENGTH - 1), "token_too_short"),
        (
            "missing-cert",
            [
                *off_loopback,
                "--tls-cert",
                str(tmp_path / "nope.pem"),
                "--tls-key",
                str(tls.keyfile),
            ],
            TEST_TOKEN,
            "tls_unusable",
        ),
        (
            "unreadable-key",
            [
                *off_loopback,
                *cert,
                "--tls-key",
                str(_unreadable_copy(tls.keyfile, tmp_path)),
            ],
            TEST_TOKEN,
            "tls_unusable",
        ),
        (
            "mismatched-key",
            [*off_loopback, *cert, "--tls-key", str(tls.other_keyfile)],
            TEST_TOKEN,
            "tls_unusable",
        ),
    ]


@pytest.mark.parametrize(
    "case",
    range(6),
    ids=[
        "no-token",
        "no-tls",
        "short-token",
        "missing-cert",
        "unreadable-key",
        "mismatched-key",
    ],
)
def test_an_unsafe_bind_exits_13_naming_the_rule(
    supervisor: Path, tls_files: TlsFiles, tmp_path: Path, case: int
) -> None:
    _, arguments, token, rule = _refusal_cases(tls_files, tmp_path)[case]

    result = run_cli(
        ["serve", *arguments], supervisor, environment=_environment(supervisor, token)
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
        env={**os.environ, STORE_DIR_ENV_VAR: str(supervisor)},
        timeout=30,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "False"
