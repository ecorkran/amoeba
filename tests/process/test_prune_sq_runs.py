"""``prune_sq_runs`` against a stub ``sq``: every failure leaves runs and exits 14.

Each run is an outcome document in the stub's state directory, which is what
``sq runs wait`` prints; Amoeba reads nothing else (slice 120, D6/D8). The stores
are under ``tmp_path``; ``HOME`` points at a scratch directory for the stub only.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from contract.standin import (
    STATUS_COMPLETED,
    STATUS_PAUSED,
    write_outcome,
    write_run_file,
)
from sq_run_fixtures import sq_run_parameters
from sq_stub import (
    LOG_ENV,
    MODE_ENV,
    REFUSE_ENV,
    STUB_STATE_RELATIVE,
    StubMode,
    write_sq_stub,
)

from amoeba.cli.main import ExitCode
from amoeba.cli.prune import prune_sq_runs
from amoeba.store import (
    CommandKind,
    JournalOutcome,
    NodeKind,
    SQReference,
    Store,
    StoreError,
    project_store_path,
)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=365)
RUN_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "sq_runs" / "run-20261015-p5-8a59ee89.json"
)
PROJECT = "alpha"
CANDIDATE_A, CANDIDATE_B = (
    "run-20260101-review-aaaaaaaa",
    "run-20260101-review-bbbbbbbb",
)
HELD = "run-20260101-review-cccccccc"
UNOWNED = "run-20260101-review-dddddddd"
SHORT_TIMEOUT_SECONDS = 0.5
LONG_TIMEOUT_SECONDS = 30.0


class Rig:
    """Stores, outcome documents, and a stub ``sq``, all under ``tmp_path``."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.supervisor = tmp_path / "supervisor"
        self.supervisor.mkdir()
        self.home = tmp_path / "home"
        self.state_dir = self.home / STUB_STATE_RELATIVE
        # Squadron's own run-state files. Nothing reads them any more; they are
        # left saying the opposite of the stub so a read would show.
        self.runs_dir = self.home / ".config" / "squadron" / "runs"
        self.runs_dir.mkdir(parents=True)
        self.bin_dir = write_sq_stub(tmp_path / "bin")
        self.log = tmp_path / "sq-calls.log"
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("PATH", f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv(LOG_ENV, str(self.log))
        self.monkeypatch = monkeypatch
        self._seed()

    def _seed(self) -> None:
        """alpha owns two prunable runs and one a live node names; one is unowned."""
        path = project_store_path(self.supervisor, PROJECT)
        with Store.open(path) as store:
            gate = store.create_node(project_id=PROJECT, kind=NodeKind.GATE, title="g")
            for run_id in (CANDIDATE_A, CANDIDATE_B, HELD):
                entry = store.journal_issue(
                    gate.id,
                    kind=CommandKind.SQ_RUN,
                    parameters=sq_run_parameters({"pipeline": "review", "params": {}}),
                )
                store.journal_resolve(
                    entry.id,
                    outcome=JournalOutcome.COMPLETED,
                    result={"run_id": run_id},
                )
            store.create_node(
                project_id=PROJECT,
                kind=NodeKind.GATE,
                title="live",
                sq=SQReference(run_id=HELD),
            )
        for run_id in (CANDIDATE_A, CANDIDATE_B, HELD, UNOWNED):
            write_outcome(
                self.home,
                run_id=run_id,
                started_at=OLD,
                updated_at=OLD,
                status=STATUS_PAUSED,
            )
            write_run_file(
                self.runs_dir,
                RUN_FIXTURE,
                run_id=run_id,
                params={},
                started_at=OLD,
                updated_at=OLD,
                status=STATUS_COMPLETED,
            )

    def mode(self, mode: StubMode, *, refuse: str | None = None) -> None:
        self.monkeypatch.setenv(MODE_ENV, mode.value)
        if refuse is not None:
            self.monkeypatch.setenv(REFUSE_ENV, refuse)

    def prune(
        self, *, confirm: bool, timeout_seconds: float = LONG_TIMEOUT_SECONDS
    ) -> ExitCode:
        return prune_sq_runs(
            store_dir=self.supervisor,
            confirm=confirm,
            timeout_seconds=timeout_seconds,
            poll_timeout_seconds=LONG_TIMEOUT_SECONDS,
            now=NOW,
        )

    def present(self) -> set[str]:
        return {path.stem for path in self.state_dir.glob("*.json")}

    def stub_calls(self) -> list[str]:
        """The ``runs prune`` calls only: ``runs wait`` polls are not deletions."""
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [line for line in lines if line.startswith("runs prune")]


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    return Rig(tmp_path, monkeypatch)


ALL_RUNS = {CANDIDATE_A, CANDIDATE_B, HELD, UNOWNED}


def test_a_preview_lists_the_candidates_and_never_calls_sq(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.mode(StubMode.DELETE)

    assert rig.prune(confirm=False) is ExitCode.OK

    out = capsys.readouterr().out
    assert CANDIDATE_A in out and CANDIDATE_B in out
    assert HELD not in out and UNOWNED not in out
    assert "2 run(s) to prune; 1 owned paused run(s) kept" in out
    assert rig.stub_calls() == []
    assert rig.present() == ALL_RUNS


def test_yes_prunes_exactly_the_candidates(rig: Rig) -> None:
    rig.mode(StubMode.DELETE)

    assert rig.prune(confirm=True) is ExitCode.OK

    assert rig.present() == {HELD, UNOWNED}
    [call] = rig.stub_calls()
    assert call == f"runs prune {CANDIDATE_A} {CANDIDATE_B} --yes"


def test_a_run_already_gone_still_counts_as_removed(rig: Rig) -> None:
    """sq exits 1 for it, but the goal state is reached."""
    rig.mode(StubMode.DELETE_THEN_EXIT_ONE)

    assert rig.prune(confirm=True) is ExitCode.OK
    assert rig.present() == {HELD, UNOWNED}


def test_a_run_sq_refuses_is_reported_and_kept(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.mode(StubMode.REFUSE_ONE, refuse=CANDIDATE_B)

    assert rig.prune(confirm=True) is ExitCode.PRUNE_INCOMPLETE

    assert rig.present() == {CANDIDATE_B, HELD, UNOWNED}
    assert f"still present: {CANDIDATE_B}" in capsys.readouterr().err


def test_a_failing_sq_deletes_nothing_and_lists_every_candidate(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.mode(StubMode.FAIL)

    assert rig.prune(confirm=True) is ExitCode.PRUNE_INCOMPLETE

    assert rig.present() == ALL_RUNS
    err = capsys.readouterr().err
    assert f"still present: {CANDIDATE_A}" in err
    assert f"still present: {CANDIDATE_B}" in err
    assert "exited 1" in err


def test_a_sq_that_times_out_is_incomplete(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    rig.mode(StubMode.SLEEP)

    assert (
        rig.prune(confirm=True, timeout_seconds=SHORT_TIMEOUT_SECONDS)
        is ExitCode.PRUNE_INCOMPLETE
    )

    assert rig.present() == ALL_RUNS
    assert "did not finish" in capsys.readouterr().err


def test_a_missing_sq_checks_nothing_and_amoeba_deletes_nothing(
    rig: Rig, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No run can be checked, so none is chosen; every owned run is named."""
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    rig.monkeypatch.setenv("PATH", str(empty))

    assert rig.prune(confirm=True) is ExitCode.OK

    assert rig.present() == ALL_RUNS
    err = capsys.readouterr().err
    for owned_run in (CANDIDATE_A, CANDIDATE_B, HELD):
        assert f"could not check: {owned_run}" in err
    assert "not found on PATH" in err
    assert UNOWNED not in err


def test_an_unreadable_project_store_refuses_before_sq_is_called(rig: Rig) -> None:
    rig.mode(StubMode.DELETE)
    (rig.supervisor / "broken.sqlite3").write_bytes(b"this is not a database")

    with pytest.raises(StoreError):
        rig.prune(confirm=True)

    assert rig.stub_calls() == []
    assert rig.present() == ALL_RUNS


def test_a_poll_failure_is_named_on_stderr_and_never_chosen(
    rig: Rig, capsys: pytest.CaptureFixture[str]
) -> None:
    (rig.state_dir / f"{CANDIDATE_A}.json").write_text("{not json", encoding="utf-8")
    rig.mode(StubMode.DELETE)

    assert rig.prune(confirm=True) is ExitCode.OK

    assert capsys.readouterr().err.count(f"could not check: {CANDIDATE_A}") == 1
    assert CANDIDATE_A in rig.present()
    assert CANDIDATE_B not in rig.present()
    [call] = rig.stub_calls()
    assert call.startswith("runs prune ") and CANDIDATE_A not in call


def test_prune_reads_no_run_state_file(rig: Rig) -> None:
    """D8: the runs directory says the opposite (completed), the stub says paused.

    A run-file read would find nothing to prune; the result follows the stub's
    outcome documents.
    """
    assert all(
        '"status": "completed"' in path.read_text(encoding="utf-8")
        for path in rig.runs_dir.glob("*.json")
    )
    rig.mode(StubMode.DELETE)

    assert rig.prune(confirm=True) is ExitCode.OK

    assert rig.present() == {HELD, UNOWNED}
