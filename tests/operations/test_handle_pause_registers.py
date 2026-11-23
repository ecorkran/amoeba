"""``handle_pause`` in a project that is in no program (slice 261, 9.12): the pause
registers it, the new member's id is not the Context Forge id, and every ``cf -p`` the
pause makes carries the checkout's Context Forge id."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from user_configs import user_config

from amoeba.operations.handle_pause import HandlePauseOutcome
from amoeba.operations.set_up_models import SetUpOutcome
from operations.handle_rig import PROJECT_ID, world
from operations.rm_placed import rm


def test_a_pause_registers_the_project_and_asks_cf_only_about_checkout_ids(
    tmp_path: Path,
) -> None:
    roomy = user_config().model_copy(update={"passages_max_chars": 500_000})
    with world(tmp_path, params={"slice": "132"}, config=roomy) as w:
        recorded: list[list[str]] = []
        inner = w.deps.cf_run

        def watching(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(list(argv))
            return inner(argv, **kwargs)

        w.deps = replace(w.deps, cf_run=watching)
        removed = rm(
            w.store,
            w.config,
            {"members": [PROJECT_ID]},
            directory=w.directory,
            run=inner,
        )
        assert removed.outcome is SetUpOutcome.APPLIED
        recorded.clear()

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        project_ids = {argv[argv.index("-p") + 1] for argv in recorded if "-p" in argv}
        assert project_ids == {PROJECT_ID}
        with w.store.read() as transaction:
            active = [
                row[0]
                for row in transaction.execute(
                    "SELECT project_id FROM members WHERE removed_at IS NULL"
                ).fetchall()
            ]
        assert len(active) == 1
        assert active[0] != PROJECT_ID
