"""Tests for the Squadron runs-directory observer, against real run files.

The fixtures in ``tests/fixtures/sq_runs/`` are byte-real upstream output, not
hand-written approximations — see that directory's README. Where a test needs a
specific shape (an unparseable file, a run started too early), it *derives* it
from a real file rather than inventing one from scratch, so the parser is
always meeting the format it meets in production.

Every escalation path matters as much as the adoption path: the only route to
``Adopt`` is exactly one candidate passing all four of D5's conditions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from amoeba.process.observers.sq_runs import (
    RESULT_RUN_ID,
    RESULT_SCHEMA_VERSION,
    SquadronRunsObserver,
    parse_run_file,
    scan_runs_directory,
)
from amoeba.process.recovery import Adopt, Unknown
from amoeba.store import CommandKind, JournalEntry

FIXTURES = Path(__file__).parent / "fixtures" / "sq_runs"

#: The real fixtures, by the case each one covers.
COMPLETED_P5 = "run-20260411-p5-93bf1c90.json"
FAILED_TEST_REVIEW = "run-20260411-test-review-a50207b1.json"
PAUSED_REVIEW = "run-20260505-review-a697ad3d.json"
COMPLETED_EMPTY_PARAMS = "run-20260801-loop-smoke-b095fb0d.json"

CLOCK_TOLERANCE_SECONDS = 5.0


def _as_payload(value: object) -> dict[str, object]:
    """Narrow a decoded JSON value to a string-keyed mapping.

    ``json.loads`` is typed as returning ``Any``, so every fixture read is
    narrowed through here rather than at each call site. The cast is checked:
    the ``isinstance`` guard runs first, and JSON objects always have string
    keys.
    """
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _load(name: str) -> dict[str, object]:
    """Read one real fixture as a mutable payload, for deriving variants."""
    return _as_payload(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _params_of(payload: Mapping[str, object]) -> dict[str, object]:
    """The ``params`` mapping of a fixture payload."""
    return _as_payload(payload["params"])


def _runs_dir(tmp_path: Path, payloads: Mapping[str, object]) -> Path:
    """Build a throwaway runs directory from named payloads."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    for name, payload in payloads.items():
        (runs_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    return runs_dir


def _entry(
    *,
    pipeline: str,
    params: Mapping[str, object],
    issued_at: datetime,
    entry_id: str = "entry-1",
) -> JournalEntry:
    """A journaled ``sq_run`` command to match against."""
    return JournalEntry(
        id=entry_id,
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.SQ_RUN,
        parameters={"pipeline": pipeline, "params": dict(params)},
        issued_at=issued_at,
    )


def _entry_for(
    name: str, *, before_start: timedelta = timedelta(minutes=1)
) -> JournalEntry:
    """An entry that should match the named real fixture.

    Issued shortly *before* the run started, which is the real ordering: the
    journal entry is committed, then the command is issued.
    """
    payload = _load(name)
    started_at = datetime.fromisoformat(str(payload["started_at"]))
    return _entry(
        pipeline=str(payload["pipeline"]),
        params=_params_of(payload),
        issued_at=started_at - before_start,
    )


def _observer(
    runs_dir: Path, *, claimed: Mapping[str, str] | None = None
) -> SquadronRunsObserver:
    return SquadronRunsObserver(
        runs_dir,
        clock_tolerance_seconds=CLOCK_TOLERANCE_SECONDS,
        claimed_run_ids=claimed,
    )


# --------------------------------------------------------------------------
# Parsing the real files
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [COMPLETED_P5, FAILED_TEST_REVIEW, PAUSED_REVIEW, COMPLETED_EMPTY_PARAMS],
)
def test_every_real_fixture_parses(name: str) -> None:
    """Including the paused and failed runs the LLD requires."""
    run = parse_run_file(FIXTURES / name)

    assert run is not None
    assert run.run_id
    assert run.pipeline
    assert run.status


def test_the_required_statuses_are_present_in_the_fixtures() -> None:
    """The fixture set covers paused and failed, not only the happy path."""
    scan = scan_runs_directory(FIXTURES)

    statuses = {run.status for run in scan.runs}
    assert "paused" in statuses
    assert "failed" in statuses
    assert scan.unparseable == ()
    assert scan.unreadable is False


def test_an_added_unknown_field_still_parses(tmp_path: Path) -> None:
    """Upstream adding a field must not break recovery."""
    payload = _load(COMPLETED_P5)
    payload["a_field_squadron_added_later"] = {"nested": True}
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: payload})

    run = parse_run_file(runs_dir / COMPLETED_P5)

    assert run is not None
    assert run.run_id == payload["run_id"]


@pytest.mark.parametrize(
    "missing_field",
    ["schema_version", "run_id", "pipeline", "params", "started_at", "status"],
)
def test_a_missing_required_field_is_a_parse_failure_not_an_exception(
    tmp_path: Path, missing_field: str
) -> None:
    """Upstream drift degrades to a human escalation, never to an exception."""
    payload = _load(COMPLETED_P5)
    del payload[missing_field]
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: payload})

    assert parse_run_file(runs_dir / COMPLETED_P5) is None


def test_malformed_json_is_a_parse_failure(tmp_path: Path) -> None:
    """A file that is not JSON at all is counted, not raised."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "broken.json").write_text("{not json at all", encoding="utf-8")

    assert parse_run_file(runs_dir / "broken.json") is None


# --------------------------------------------------------------------------
# The four candidate conditions
# --------------------------------------------------------------------------


def test_exactly_one_match_adopts_with_run_id_and_schema_version(
    tmp_path: Path,
) -> None:
    """The only path to Adopt, carrying the run file's own schema_version."""
    payload = _load(PAUSED_REVIEW)
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})

    observation = _observer(runs_dir).observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_RUN_ID] == payload["run_id"]
    assert observation.result[RESULT_SCHEMA_VERSION] == payload["schema_version"]


def test_zero_matches_is_unknown(tmp_path: Path) -> None:
    """A journaled command with no observable run escalates."""
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: _load(COMPLETED_P5)})
    entry = _entry(
        pipeline="a-pipeline-that-never-ran",
        params={},
        issued_at=datetime(2026, 4, 11, tzinfo=UTC),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Unknown)
    assert "no squadron run matches" in observation.reason
    assert observation.candidates == ()


def test_two_matches_is_unknown_naming_the_count(tmp_path: Path) -> None:
    """Ambiguity is never guessed, and the count reaches the human."""
    first = _load(PAUSED_REVIEW)
    second = _load(PAUSED_REVIEW)
    second["run_id"] = "run-20260505-review-second00"
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: first, "run-second.json": second})

    observation = _observer(runs_dir).observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Unknown)
    assert "2 squadron runs match" in observation.reason
    assert set(observation.candidates) == {first["run_id"], second["run_id"]}


def test_subset_params_match_where_exact_equality_would_fail(
    tmp_path: Path,
) -> None:
    """Squadron merges definition defaults with overrides, so subset is required.

    The journaled params here are a strict subset of the run's persisted ones.
    Under exact-equality matching this would find zero candidates and escalate;
    under subset matching it adopts.
    """
    payload = _load(COMPLETED_P5)
    persisted = _params_of(payload)
    assert len(persisted) > 1, "fixture must carry more than one param"

    # Journal only ONE of the run's several persisted params.
    journaled_subset: dict[str, object] = {"slice": persisted["slice"]}
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: payload})
    entry = _entry(
        pipeline=str(payload["pipeline"]),
        params=journaled_subset,
        issued_at=datetime.fromisoformat(str(payload["started_at"]))
        - timedelta(minutes=1),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_RUN_ID] == payload["run_id"]


def test_a_differing_param_value_is_not_a_candidate(tmp_path: Path) -> None:
    """Subset matching compares values, not merely key presence."""
    payload = _load(COMPLETED_P5)
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: payload})
    entry = _entry(
        pipeline=str(payload["pipeline"]),
        params={"slice": "a-different-slice"},
        issued_at=datetime.fromisoformat(str(payload["started_at"]))
        - timedelta(minutes=1),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Unknown)


def test_a_run_started_before_the_tolerance_window_is_rejected(
    tmp_path: Path,
) -> None:
    """A run that began before the entry was issued cannot be this entry's run."""
    payload = _load(PAUSED_REVIEW)
    started_at = datetime.fromisoformat(str(payload["started_at"]))
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})

    # Issued well after the run started, beyond the clock tolerance.
    entry = _entry(
        pipeline=str(payload["pipeline"]),
        params=_params_of(payload),
        issued_at=started_at + timedelta(seconds=CLOCK_TOLERANCE_SECONDS + 60),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Unknown)
    assert "no squadron run matches" in observation.reason


def test_a_run_started_within_the_clock_tolerance_is_accepted(
    tmp_path: Path,
) -> None:
    """Clock skew between the two writers does not cost a false escalation."""
    payload = _load(PAUSED_REVIEW)
    started_at = datetime.fromisoformat(str(payload["started_at"]))
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})

    # Issued a moment after the run started, inside the tolerance.
    entry = _entry(
        pipeline=str(payload["pipeline"]),
        params=_params_of(payload),
        issued_at=started_at + timedelta(seconds=CLOCK_TOLERANCE_SECONDS - 1),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Adopt)


def test_a_run_already_claimed_by_another_entry_is_not_a_candidate(
    tmp_path: Path,
) -> None:
    """The fourth condition: one run is adopted by at most one entry."""
    payload = _load(PAUSED_REVIEW)
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})
    claimed = {str(payload["run_id"]): "some-other-entry"}

    observation = _observer(runs_dir, claimed=claimed).observe(
        _entry_for(PAUSED_REVIEW)
    )

    assert isinstance(observation, Unknown)
    assert "no squadron run matches" in observation.reason


def test_pipeline_matching_is_case_insensitive(tmp_path: Path) -> None:
    """Squadron lower-cases the pipeline before persisting it."""
    payload = _load(PAUSED_REVIEW)
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})

    entry = _entry(
        pipeline=str(payload["pipeline"]).upper(),
        params=_params_of(payload),
        issued_at=datetime.fromisoformat(str(payload["started_at"]))
        - timedelta(minutes=1),
    )

    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Adopt)


# --------------------------------------------------------------------------
# External failure modes
# --------------------------------------------------------------------------


def test_a_missing_runs_directory_is_unknown(tmp_path: Path) -> None:
    """An absent upstream directory escalates rather than raising."""
    observation = _observer(tmp_path / "no-such-dir").observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Unknown)
    assert "missing or unreadable" in observation.reason


def test_a_runs_directory_that_is_a_file_is_unknown(tmp_path: Path) -> None:
    """Anything that cannot be listed as a directory escalates."""
    not_a_dir = tmp_path / "runs"
    not_a_dir.write_text("not a directory", encoding="utf-8")

    observation = _observer(not_a_dir).observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Unknown)
    assert "missing or unreadable" in observation.reason


def test_an_unparseable_file_is_counted_and_named_when_unmatched(
    tmp_path: Path,
) -> None:
    """A parse failure is surfaced, never dropped into a confident answer."""
    runs_dir = _runs_dir(tmp_path, {COMPLETED_P5: _load(COMPLETED_P5)})
    (runs_dir / "corrupt.json").write_text("{broken", encoding="utf-8")

    entry = _entry(
        pipeline="nothing-matches-this",
        params={},
        issued_at=datetime(2026, 4, 11, tzinfo=UTC),
    )
    observation = _observer(runs_dir).observe(entry)

    assert isinstance(observation, Unknown)
    assert "could not be parsed" in observation.reason
    assert "corrupt.json" in observation.reason


def test_an_unparseable_file_does_not_prevent_a_clean_match_elsewhere(
    tmp_path: Path,
) -> None:
    """One bad file does not block adopting an unambiguous match."""
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: _load(PAUSED_REVIEW)})
    (runs_dir / "corrupt.json").write_text("{broken", encoding="utf-8")

    observation = _observer(runs_dir).observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Adopt)


def test_a_file_missing_a_required_field_degrades_to_unknown(
    tmp_path: Path,
) -> None:
    """Upstream drift becomes an escalation, not an exception and not a match."""
    payload = _load(PAUSED_REVIEW)
    del payload["run_id"]
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: payload})

    observation = _observer(runs_dir).observe(_entry_for(PAUSED_REVIEW))

    assert isinstance(observation, Unknown)
    assert "could not be parsed" in observation.reason


# --------------------------------------------------------------------------
# The scan happens once
# --------------------------------------------------------------------------


def test_the_directory_is_scanned_once_across_many_observations(
    tmp_path: Path,
) -> None:
    """Recovery reconciles many entries against one scan, not one scan each.

    The load tier asserts this exactly at scale; this is the unit-level proof
    that the observer reuses its scan rather than re-reading per entry.
    """
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: _load(PAUSED_REVIEW)})
    observer = _observer(runs_dir)

    first_scan = observer.scan
    for _ in range(5):
        observer.observe(_entry_for(PAUSED_REVIEW))

    assert observer.scan is first_scan


def test_a_prebuilt_scan_is_reused(tmp_path: Path) -> None:
    """Recovery passes one scan in, so every entry shares it."""
    runs_dir = _runs_dir(tmp_path, {PAUSED_REVIEW: _load(PAUSED_REVIEW)})
    scan = scan_runs_directory(runs_dir)
    observer = SquadronRunsObserver(
        runs_dir,
        clock_tolerance_seconds=CLOCK_TOLERANCE_SECONDS,
        scan=scan,
    )

    assert observer.scan is scan
    assert isinstance(observer.observe(_entry_for(PAUSED_REVIEW)), Adopt)
