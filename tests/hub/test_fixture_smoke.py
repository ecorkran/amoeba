"""The two-machine fixture starts, joins both clients and stops cleanly (15.1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hub_fixture import FIRST, SECOND, two_machine_hub


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_the_fixture_starts_joins_both_clients_stops_and_leaves_no_process(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        assert hub.process is not None
        pid = hub.process.pid
        assert sorted(hub.clients) == [FIRST, SECOND]
        decisions = hub.clients[FIRST].run("decisions", "-j")
        assert decisions.code == 0, decisions.err

    assert not _alive(pid)


@pytest.mark.parametrize("program", ["cf", "sq"])
def test_the_hub_path_holds_neither_cf_nor_sq(program: str) -> None:
    import shutil

    from hub_fixture import safe_path

    assert shutil.which(program, path=safe_path()) is None
