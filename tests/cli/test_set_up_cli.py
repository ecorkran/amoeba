"""``amoeba set_up`` as a real subprocess, with a fake ``cf`` first on ``PATH``."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.config.home import config_path, store_path
from amoeba.store.store import Store

AMOEBA = Path(sys.executable).with_name("amoeba")
RUN_TIMEOUT_SECONDS = 60
REQUEST = {"program": "demo", "members": [{"rules_paths": ["CLAUDE.md"]}]}


def _run(
    tmp_path: Path,
    *arguments: str,
    stdin: bytes | None = None,
    cf_fixture: str | None = DEFAULT_WORKTREE,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    write_fake_cf(bin_dir, cf_fixture)
    environment = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    child = contained_popen(
        [str(AMOEBA), *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=environment,
    )
    stdout, stderr = child.communicate(stdin, timeout=RUN_TIMEOUT_SECONDS)
    return subprocess.CompletedProcess(
        child.args, child.returncode, stdout.decode(), stderr.decode()
    )


def _write_config(text: str | None = None) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(
        example_config_text() if text is None else text, encoding="utf-8"
    )


def _request_file(tmp_path: Path, document: object = REQUEST) -> Path:
    path = tmp_path / "request.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(completed.stdout)
    return document


def _row_count(table: str) -> int:
    with sqlite3.connect(store_path()) as connection:
        return int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_a_valid_request_from_a_file_exits_zero_with_the_result(tmp_path: Path) -> None:
    _write_config()

    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path)))

    assert completed.returncode == EXIT_OK, completed.stderr
    assert _result(completed)["outcome"] == "applied"
    assert len(_result(completed)["program"]["members"]) == 1


def test_a_valid_request_from_stdin_exits_zero(tmp_path: Path) -> None:
    _write_config()

    completed = _run(
        tmp_path, "set_up", "--file", "-", stdin=yaml.safe_dump(REQUEST).encode()
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert _result(completed)["outcome"] == "applied"


def test_a_rerun_is_unchanged(tmp_path: Path) -> None:
    _write_config()
    request = str(_request_file(tmp_path))
    _run(tmp_path, "set_up", "--file", request)

    completed = _run(tmp_path, "set_up", "--file", request)

    assert completed.returncode == EXIT_OK
    assert _result(completed)["outcome"] == "unchanged"


def test_a_rejected_request_exits_one_with_the_result(tmp_path: Path) -> None:
    _write_config()

    completed = _run(
        tmp_path, "set_up", "--file", str(_request_file(tmp_path, {"program": "demo"}))
    )

    assert completed.returncode == EXIT_REJECTED
    result = _result(completed)
    assert result["outcome"] == "rejected"
    assert result["problems"][0]["code"] == "empty_program"


def test_a_non_mapping_document_is_rejected_as_malformed(tmp_path: Path) -> None:
    _write_config()

    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path, [1, 2])))

    assert completed.returncode == EXIT_REJECTED
    assert _result(completed)["problems"][0]["code"] == "malformed"


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (None, "cannot read"),
        (b"program: \xff\xfe\n", "not UTF-8"),
        (b"program: [unclosed\n", "not YAML"),
    ],
)
def test_an_unusable_request_exits_two_and_creates_no_store(
    tmp_path: Path, content: bytes | None, reason: str
) -> None:
    request = tmp_path / "request.yaml"
    if content is not None:
        request.write_bytes(content)

    completed = _run(tmp_path, "set_up", "--file", str(request))

    assert completed.returncode == EXIT_USAGE
    assert completed.stdout == ""
    assert f"error: RequestDocumentError: {request}: {reason}" in completed.stderr
    assert not store_path().exists()


def test_bad_arguments_exit_two(tmp_path: Path) -> None:
    assert _run(tmp_path, "set_up").returncode == EXIT_USAGE
    assert _run(tmp_path, "no_such_command").returncode == EXIT_USAGE


def test_a_missing_config_exits_three_naming_the_file(tmp_path: Path) -> None:
    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path)))

    assert completed.returncode == EXIT_ERROR
    assert f"error: ConfigError: no config at {config_path()}" in completed.stderr


def test_a_config_missing_a_key_exits_three_naming_the_key(tmp_path: Path) -> None:
    document = yaml.safe_load(example_config_text())
    del document["answer_limit"]
    _write_config(yaml.safe_dump(document))

    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path)))

    assert completed.returncode == EXIT_ERROR
    assert "answer_limit" in completed.stderr
    assert str(config_path()) in completed.stderr


def test_a_failing_cf_exits_three_and_writes_nothing(tmp_path: Path) -> None:
    _write_config()

    completed = _run(
        tmp_path, "set_up", "--file", str(_request_file(tmp_path)), cf_fixture=None
    )

    assert completed.returncode == EXIT_ERROR
    assert "error: ContextForgeError" in completed.stderr
    assert _row_count("programs") == 0
    assert _row_count("members") == 0


def test_a_store_stamped_higher_exits_three(tmp_path: Path) -> None:
    _write_config()
    Store.open(store_path()).close()
    with sqlite3.connect(store_path()) as connection:
        connection.execute("UPDATE schema_meta SET version = 99")
    connection.close()

    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path)))

    assert completed.returncode == EXIT_ERROR
    assert "error: StoreSchemaError" in completed.stderr


def test_a_relative_home_exits_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMOEBA_HOME", "relative/home")

    completed = _run(tmp_path, "set_up", "--file", str(_request_file(tmp_path)))

    assert completed.returncode == EXIT_ERROR
    assert "error: AmoebaHomeError" in completed.stderr
