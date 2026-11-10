"""A fake ``CfRun`` that answers ``cf list`` from the recorded plan reads.

Recordings are in ``tests/fixtures/context_forge`` (real ``cf`` 0.19.26 output).
``list initiatives`` replays ``list_initiatives_a.json``. ``list slices <n>`` replays
``list_slices_<n>.json``; an initiative with no recording gets a recorded
``error: true`` document on stderr with exit 1, which is what ``cf`` does for one
with no slice plan. ``get --json`` replays the project recording, and
``config get git.integration_branch`` answers the configured value in ``cf``'s own
document shape. Every argv is kept in ``calls``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field

from cf_fixtures import FIXTURES, failure, replay

NO_PLAN_FIXTURE = "list_slices_200_error.json"


@dataclass
class PlanCfRun:
    """Replays plan reads; ``broken`` makes every call fail with no JSON."""

    integration_branch: str
    broken: bool
    #: The recording ``cf get --json`` replays (``default_worktree`` unless a test
    #: says the directory is outside every project).
    project_fixture: str = "default_worktree"
    calls: list[list[str]] = field(default_factory=lambda: [])

    def __call__(
        self, argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if self.broken:
            return failure(argv)
        if argv[1:3] == ["list", "initiatives"]:
            return self._replay(argv, "list_initiatives_a.json")
        if argv[1:3] == ["list", "slices"]:
            name = f"list_slices_{argv[3]}.json"
            if (FIXTURES / name).exists():
                return self._replay(argv, name)
            return self._replay(argv, NO_PLAN_FIXTURE, to_stderr=True)
        if argv[1] == "get":
            return replay(argv, self.project_fixture)
        if argv[1:3] == ["config", "get"]:
            text = json.dumps({"value": self.integration_branch})
            return subprocess.CompletedProcess(list(argv), 0, text, "")
        raise AssertionError(f"unexpected cf call: {argv}")

    @staticmethod
    def _replay(
        argv: Sequence[str], name: str, *, to_stderr: bool = False
    ) -> subprocess.CompletedProcess[str]:
        text = (FIXTURES / name).read_text(encoding="utf-8")
        if to_stderr:
            return subprocess.CompletedProcess(list(argv), 1, "", text)
        return subprocess.CompletedProcess(list(argv), 0, text, "")


def plan_cf_run(*, integration_branch: str, broken: bool) -> PlanCfRun:
    return PlanCfRun(integration_branch=integration_branch, broken=broken)
