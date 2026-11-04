"""The slice-writing pipeline start probe (slice 180, D9): validate --strict, once."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import SQ_EXECUTABLE, ProcessSettings, StartupFailedError
from amoeba.runner.probes import probe_slice_writing_pipeline
from amoeba.runner.request_run.pipeline_file import (
    IO_DIRECTORY_OPTION,
    MAX_COST_OPTION,
    PROBE_MAX_COST_USD,
    slice_writing_pipeline_path,
)

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
        self.io_directory_existed_during_call = False

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, kwargs))
        self.cwd_existed_during_call = Path(kwargs["cwd"]).is_dir()
        if IO_DIRECTORY_OPTION in argv:
            io_directory = Path(argv[argv.index(IO_DIRECTORY_OPTION) + 1])
            self.io_directory_existed_during_call = io_directory.is_dir()
        if self._raises is not None:
            raise self._raises
        return self._answer


def _settings() -> ProcessSettings:
    return ProcessSettings(sq_timeout_seconds=SQ_TIMEOUT)


def test_probe_passes_on_exit_zero() -> None:
    stub = StubSq(stdout="Pipeline 'slice-writing' is valid.\n")
    probe_slice_writing_pipeline(_settings(), stub)
    assert len(stub.calls) == 1


def test_probe_call_shape() -> None:
    stub = StubSq()
    probe_slice_writing_pipeline(_settings(), stub)
    argv, kwargs = stub.calls[0]
    io_directory = argv[argv.index(IO_DIRECTORY_OPTION) + 1]
    assert argv == [
        SQ_EXECUTABLE,
        "run",
        str(slice_writing_pipeline_path()),
        "--validate",
        "--strict",
        IO_DIRECTORY_OPTION,
        io_directory,
        MAX_COST_OPTION,
        str(PROBE_MAX_COST_USD),
    ]
    assert kwargs["timeout"] == SQ_TIMEOUT
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert stub.io_directory_existed_during_call
    assert not Path(io_directory).exists()  # temporary, gone after the call


def test_probe_runs_from_a_temporary_directory() -> None:
    stub = StubSq()
    probe_slice_writing_pipeline(_settings(), stub)
    argv, kwargs = stub.calls[0]
    cwd = Path(kwargs["cwd"])
    assert stub.cwd_existed_during_call
    assert cwd != Path.cwd()
    assert cwd != Path(argv[argv.index(IO_DIRECTORY_OPTION) + 1])
    assert not cwd.exists()


def test_probe_fails_on_non_zero_exit() -> None:
    stub = StubSq(
        returncode=1, stdout="Validation errors for 'p':\n  Unknown step type 'commit'"
    )
    with pytest.raises(StartupFailedError) as raised:
        probe_slice_writing_pipeline(_settings(), stub)
    message = str(raised.value)
    assert "slice-writing pipeline probe failed" in message
    assert f"{SQ_EXECUTABLE} run" in message
    assert "exited 1" in message
    assert "Unknown step type" in message


def test_probe_fails_on_timeout() -> None:
    stub = StubSq(
        raises=subprocess.TimeoutExpired(cmd=SQ_EXECUTABLE, timeout=SQ_TIMEOUT)
    )
    with pytest.raises(
        StartupFailedError,
        match=f"slice-writing pipeline probe failed.*timed out after {SQ_TIMEOUT}s",
    ):
        probe_slice_writing_pipeline(_settings(), stub)


def test_probe_fails_when_sq_is_missing() -> None:
    stub = StubSq(raises=FileNotFoundError(2, "No such file or directory"))
    with pytest.raises(
        StartupFailedError,
        match=f"slice-writing pipeline probe failed.*{SQ_EXECUTABLE}.*could not run",
    ):
        probe_slice_writing_pipeline(_settings(), stub)


def test_probe_reports_a_missing_pipeline_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing() -> Path:
        raise FileNotFoundError("slice-writing pipeline file is missing: /x/y.yaml")

    monkeypatch.setattr("amoeba.runner.probes.slice_writing_pipeline_path", missing)
    stub = StubSq()
    with pytest.raises(
        StartupFailedError, match="slice-writing pipeline probe failed.*y.yaml"
    ):
        probe_slice_writing_pipeline(_settings(), stub)
    assert stub.calls == []
