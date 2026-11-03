"""The answering pipeline start probe (slice 140, D9): validate --strict, once."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import SQ_EXECUTABLE, ProcessSettings, StartupFailedError
from amoeba.runner.answering.pipeline_file import answering_pipeline_path
from amoeba.runner.probes import probe_answering_pipeline

SQ_TIMEOUT = 7.5


class StubSq:
    """A ``subprocess.run`` stand-in that records its calls and answers a script."""

    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        raises: BaseException | None = None,
    ) -> None:
        self._answer = subprocess.CompletedProcess[str]([], returncode, stdout, stderr)
        self._raises = raises
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self.cwd_existed_during_call = False

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, kwargs))
        self.cwd_existed_during_call = Path(kwargs["cwd"]).is_dir()
        if self._raises is not None:
            raise self._raises
        return self._answer


def _settings() -> ProcessSettings:
    return ProcessSettings(sq_timeout_seconds=SQ_TIMEOUT)


def test_answering_probe_passes_on_exit_zero() -> None:
    stub = StubSq(stdout="Pipeline 'answering' is valid.\n")
    probe_answering_pipeline(_settings(), stub)
    assert len(stub.calls) == 1


def test_answering_probe_call_shape() -> None:
    stub = StubSq()
    probe_answering_pipeline(_settings(), stub)
    argv, kwargs = stub.calls[0]
    assert argv == [
        SQ_EXECUTABLE,
        "run",
        str(answering_pipeline_path()),
        "--validate",
        "--strict",
    ]
    assert kwargs["timeout"] == SQ_TIMEOUT
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert stub.cwd_existed_during_call
    cwd = Path(kwargs["cwd"])
    assert cwd != Path.cwd()
    assert not cwd.exists()  # the temporary directory is gone after the call


def test_answering_probe_fails_on_non_zero_exit() -> None:
    stub = StubSq(
        returncode=1, stdout="Validation errors for 'answering':\n  unknown key"
    )
    with pytest.raises(StartupFailedError) as raised:
        probe_answering_pipeline(_settings(), stub)
    message = str(raised.value)
    assert f"{SQ_EXECUTABLE} run" in message
    assert "--validate" in message
    assert "exited 1" in message
    assert "unknown key" in message


def test_answering_probe_quotes_stderr_when_stdout_is_empty() -> None:
    stub = StubSq(returncode=2, stderr="boom on stderr")
    with pytest.raises(StartupFailedError, match="boom on stderr"):
        probe_answering_pipeline(_settings(), stub)


def test_answering_probe_fails_on_timeout() -> None:
    stub = StubSq(
        raises=subprocess.TimeoutExpired(cmd=SQ_EXECUTABLE, timeout=SQ_TIMEOUT)
    )
    with pytest.raises(StartupFailedError, match=f"timed out after {SQ_TIMEOUT}s"):
        probe_answering_pipeline(_settings(), stub)


def test_answering_probe_fails_when_sq_is_missing() -> None:
    stub = StubSq(raises=FileNotFoundError(2, "No such file or directory"))
    with pytest.raises(StartupFailedError, match=f"{SQ_EXECUTABLE}.*could not run"):
        probe_answering_pipeline(_settings(), stub)
