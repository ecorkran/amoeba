"""Every subcommand moves legacy state before its own work (slice 228, D2, 2.7).

``HOME`` is a throwaway directory with ``AMOEBA_HOME`` unset, so the legacy home is
``<HOME>/.config/amoeba`` and the state home ``<HOME>/.local/state/amoeba``. Each
operation is replaced by a stub that records whether the move had happened when it
was called, then fails with a typed error the CLI maps to exit 3.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from store.relocate_support import seed_store
from user_configs import example_config_text

from amoeba.cli import main as cli
from amoeba.config.home import HOME_VARIABLE
from amoeba.upstream.squadron.errors import SquadronError

STUBBED_OPERATIONS = (
    ("set_up", ["set_up", "--file"]),
    ("handle_pause", ["handle_pause", "run-1"]),
    ("answer", ["answer", "run-1", "--text", "yes"]),
    ("status", ["status"]),
    ("decisions", ["decisions"]),
    ("mark_read", ["mark_read", "--through", "0"]),
)


@pytest.mark.parametrize(
    ("operation", "arguments"),
    STUBBED_OPERATIONS,
    ids=[o for o, _ in STUBBED_OPERATIONS],
)
def test_the_move_happens_before_the_commands_own_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operation: str,
    arguments: list[str],
) -> None:
    monkeypatch.delenv(HOME_VARIABLE)
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy = tmp_path / ".config" / "amoeba"
    legacy_store = seed_store(legacy)
    (legacy / "config.yaml").write_text(example_config_text(), encoding="utf-8")
    state_store = tmp_path / ".local" / "state" / "amoeba" / "amoeba.sqlite3"
    request = tmp_path / "request.yaml"
    request.write_text("program: trial\n", encoding="utf-8")
    seen: list[tuple[bool, bool]] = []

    def stub(*unused: object, **also_unused: object) -> None:
        seen.append((state_store.exists(), legacy_store.exists()))
        raise SquadronError("stub")

    monkeypatch.setattr(cli, operation, stub)
    argv = [*arguments, str(request)] if operation == "set_up" else arguments

    exit_code = cli.main(argv)

    assert exit_code == cli.EXIT_ERROR
    assert seen == [(True, False)]
