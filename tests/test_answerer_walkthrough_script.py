"""The walkthrough setup script's refusals, failure reports and written config.

`git`, `cf` and `amoeba` are stubs on a private PATH, so no real tool, `sq` or model
runs (slice 145, D6).
"""

from __future__ import annotations

import importlib.util
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from amoeba.runner.project_config import load_project_config

SCRIPT = Path(__file__).parent.parent / "scripts" / "answerer_walkthrough.py"
LIVE = {
    "AMOEBA_LIVE_ANSWER_MODEL": "answer-alias",
    "AMOEBA_LIVE_CHECK_MODEL": "check-alias",
    "AMOEBA_LIVE_MAX_COST_USD": "0.5",
}
LOG_LINE = 'echo "${0##*/} $*" >> "$STUB_LOG"'
PROJECT_JSON = '{"id": "project_stub_1", "name": "scratch"}'


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("answerer_walkthrough", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


script = _load_script()

StubMaker = Callable[..., dict[str, str]]


@pytest.fixture
def stubs(tmp_path: Path) -> StubMaker:
    """Write stub `git`, `cf` and `amoeba`; return the environment that finds them."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"

    def make(
        *, cf_get: str = PROJECT_JSON, git_exit: int = 0, git_stderr: str = ""
    ) -> dict[str, str]:
        bodies = {
            "git": f"{LOG_LINE}\necho '{git_stderr}' >&2\nexit {git_exit}",
            "cf": f"{LOG_LINE}\n[ \"$1\" = get ] && echo '{cf_get}'\nexit 0",
            "amoeba": f"{LOG_LINE}\nexit 0",
        }
        for name, body in bodies.items():
            stub = bin_dir / name
            stub.write_text(f"#!/bin/sh\n{body}\n")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return {"PATH": str(bin_dir), "STUB_LOG": str(log), **LIVE}

    return make


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    path = tmp_path / "keys.env"
    path.write_text("PLACEHOLDER_KEY=not-a-real-key\n")
    return path


def test_an_existing_directory_is_refused_by_name(
    tmp_path: Path, env_file: Path, stubs: StubMaker
) -> None:
    target = tmp_path / "walk"
    target.mkdir()

    with pytest.raises(SystemExit, match=str(target)):
        script.setup(target, env_file, stubs())

    assert list(target.iterdir()) == []


def test_a_missing_env_file_is_refused_by_name(
    tmp_path: Path, stubs: StubMaker
) -> None:
    missing = tmp_path / "nope.env"

    with pytest.raises(SystemExit, match="nope.env"):
        script.setup(tmp_path / "walk", missing, stubs())

    assert not (tmp_path / "walk").exists()


@pytest.mark.parametrize("name", sorted(LIVE))
@pytest.mark.parametrize("value", [None, "", "   "])
def test_each_unset_live_variable_is_refused_by_name(
    tmp_path: Path,
    env_file: Path,
    stubs: StubMaker,
    name: str,
    value: str | None,
) -> None:
    environ = stubs()
    if value is None:
        del environ[name]
    else:
        environ[name] = value

    with pytest.raises(SystemExit, match=name):
        script.setup(tmp_path / "walk", env_file, environ)

    assert not (tmp_path / "walk").exists()


@pytest.mark.parametrize("cost", ["lots", "0", "-1", "nan"])
def test_a_cost_cap_that_is_not_above_zero_is_refused(
    tmp_path: Path, env_file: Path, stubs: StubMaker, cost: str
) -> None:
    environ = {**stubs(), "AMOEBA_LIVE_MAX_COST_USD": cost}

    with pytest.raises(SystemExit, match="AMOEBA_LIVE_MAX_COST_USD"):
        script.setup(tmp_path / "walk", env_file, environ)

    assert not (tmp_path / "walk").exists()


@pytest.mark.parametrize("cf_get", ["", "not json", "{}", '{"id": ""}', '["id"]'])
def test_a_cf_get_without_a_project_id_stops_naming_the_step(
    tmp_path: Path, env_file: Path, stubs: StubMaker, cf_get: str
) -> None:
    target = tmp_path / "walk"

    with pytest.raises(SystemExit, match="cf get"):
        script.setup(target, env_file, stubs(cf_get=cf_get))

    assert target.is_dir()  # left in place, partly built


def test_a_failing_subprocess_reports_step_command_and_stderr(
    tmp_path: Path, env_file: Path, stubs: StubMaker
) -> None:
    target = tmp_path / "walk"

    with pytest.raises(SystemExit) as stopped:
        script.setup(target, env_file, stubs(git_exit=3, git_stderr="disk on fire"))

    message = str(stopped.value)
    assert "git init" in message
    assert "git init -q -b main" in message
    assert "disk on fire" in message
    assert str(target.resolve()) in message
    assert target.is_dir()


def test_setup_builds_the_directory_and_submits_the_project(
    tmp_path: Path, env_file: Path, stubs: StubMaker, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "walk"
    environ = stubs()

    script.setup(target, env_file, environ)

    calls = Path(environ["STUB_LOG"]).read_text().splitlines()
    assert "cf init --lite --name scratch" in calls
    assert (
        "amoeba submit link-cf-project --project scratch --by walkthrough "
        "--cf-project-id project_stub_1"
    ) in calls
    assert (target / "checkout" / "CLAUDE.md").is_file()
    assert (target / "checkout" / ".env").read_text() == env_file.read_text()
    printed = capsys.readouterr().out
    assert f"export AMOEBA_STORE_DIR={(target / 'store').resolve()}" in printed
    assert f"export CONTEXT_FORGE_DATA_DIR={(target / 'cf').resolve()}" in printed
    assert "amoeba start --project-config" in printed
    assert "not-a-real-key" not in printed


def test_the_written_config_loads_with_the_live_values_literally(
    tmp_path: Path,
) -> None:
    layout = script.Layout(tmp_path)
    live = script.LiveSettings("answer-alias", "check-alias", "0.5")

    script.write_config(layout, live)

    config = load_project_config(layout.config)
    answerer = config.for_project("scratch").answerer
    assert config.for_project("scratch").pipeline == "p4"
    assert answerer is not None
    assert answerer.answer_model == "answer-alias"
    assert answerer.check_model == "check-alias"
    assert answerer.max_cost_usd == 0.5
    assert answerer.answer_limit == 1
    assert answerer.reserved_terms == ("push", "merge", "release", "DROP")
    assert "$" not in layout.config.read_text()
