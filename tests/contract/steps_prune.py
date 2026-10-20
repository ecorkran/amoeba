"""Step 12 of the lifecycle proof: pruning against the real end state (slice 110, D8).

``amoeba prune sq-runs`` is run as a subprocess with the harness environment and a
stub ``sq`` first on ``PATH``. Assertions are on *selection*, never on the
retention value: the stand-in dates its paused runs far past any retention.
"""

from __future__ import annotations

import os
import subprocess
import sys

from sq_stub import MODE_ENV, StubMode, write_sq_stub

from amoeba.store import NodeKind
from contract.harness import ProofHarness
from contract.runner_tenant import only_node
from contract.scenario import ALPHA, BETA, Step
from contract.steps import expect

#: Exit status 0, as the process contract's table documents it.
EXIT_OK = 0
COMMAND_TIMEOUT_SECONDS = 30.0
#: A preview line for a candidate has tab-separated fields; the summary does not.
FIELD_SEPARATOR = "\t"
SUMMARY = "1 run(s) to prune; 1 owned paused run(s) kept"


def _prune(
    harness: ProofHarness, extra: list[str], stub_dir: str
) -> subprocess.CompletedProcess[str]:
    environment = dict(harness.environment())
    environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
    environment[MODE_ENV] = StubMode.DELETE.value
    return subprocess.run(
        [sys.executable, "-m", "amoeba.cli.main", "prune", "sq-runs", *extra],
        env=environment,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )


def _runs_present(harness: ProofHarness) -> set[str]:
    return {path.stem for path in harness.runs_dir.glob("*.json")}


def prune_paused_runs(
    harness: ProofHarness, step: Step, external_run_id: str | None
) -> None:
    """Preview, then ``--yes``: only alpha's checkpoint run goes."""
    number = step.number
    expect(number, external_run_id is not None, "step 7 left no external run")
    with harness.read(ALPHA) as store:
        alpha_run = only_node(store, ALPHA, NodeKind.GATE).sq.run_id
    with harness.read(BETA) as store:
        beta_run = only_node(store, BETA, NodeKind.GATE).sq.run_id
    expect(number, alpha_run is not None and beta_run is not None, "no checkpoint runs")
    before = _runs_present(harness)
    expect(
        number,
        {alpha_run, beta_run, external_run_id} <= before,
        "the runs the scenario wrote are not all on disk",
    )
    stub_dir = str(write_sq_stub(harness.tmp_path / "stub-bin"))

    preview = _prune(harness, [], stub_dir)
    expect(number, preview.returncode == EXIT_OK, f"preview failed: {preview.stderr}")
    candidates = [
        line.split(FIELD_SEPARATOR)[0]
        for line in preview.stdout.splitlines()
        if FIELD_SEPARATOR in line
    ]
    expect(number, candidates == [alpha_run], f"candidates were {candidates}")
    expect(number, SUMMARY in preview.stdout, f"summary missing: {preview.stdout}")
    expect(number, _runs_present(harness) == before, "the preview deleted a file")

    pruned = _prune(harness, ["--yes"], stub_dir)
    expect(number, pruned.returncode == EXIT_OK, f"--yes failed: {pruned.stderr}")
    expect(
        number,
        _runs_present(harness) == before - {alpha_run},
        "--yes removed more or less than alpha's checkpoint run",
    )
