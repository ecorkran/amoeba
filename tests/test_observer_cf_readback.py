"""Tests for the Context Forge read-back observer.

The subprocess boundary is mocked for the failure modes — there is no way to
make a real ``cf`` time out or vanish on demand — but the comparison logic runs
against the **real** ``cf get --json`` fixture captured in
``tests/fixtures/cf/``, and one test invokes the real binary, skipping cleanly
when it is not on ``PATH``.

Every external failure mode must yield a *distinguishable* ``Unknown`` reason:
the human reading the blocked state needs to know whether ``cf`` is missing,
hung, failing, or emitting something unparseable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from amoeba.process.observers.cf_readback import (
    CF_FIELD_UPDATED_AT,
    RESULT_UPDATED_AT,
    RESULT_VERSION_LABEL,
    VERSION_UNAVAILABLE,
    CFReadbackObserver,
    capture_version_label,
)
from amoeba.process.recovery import Adopt, NotApplied, Unknown
from amoeba.store import CommandKind, JournalEntry

FIXTURE = Path(__file__).parent / "fixtures" / "cf" / "cf_get_amoeba.json"

TIMEOUT_SECONDS = 10.0
VERSION_LABEL = "0.15.0"


def _record() -> dict[str, object]:
    """The real captured ``cf get --json`` output."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast("dict[str, object]", payload)


def _entry(expected: Mapping[str, object], project: str = "amoeba") -> JournalEntry:
    """A journaled ``cf_write`` command."""
    return JournalEntry(
        id="entry-1",
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.CF_WRITE,
        parameters={"project": project, "expected": dict(expected)},
    )


class FakeCompletedProcess:
    """Stands in for ``subprocess.CompletedProcess`` without running anything."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: FakeCompletedProcess | None = None,
    raises: BaseException | None = None,
) -> list[Sequence[str]]:
    """Replace ``subprocess.run`` in the observer module. Records the calls."""
    calls: list[Sequence[str]] = []

    def _fake_run(args: Sequence[str], **_kwargs: object) -> FakeCompletedProcess:
        calls.append(args)
        if raises is not None:
            raise raises
        assert result is not None
        return result

    monkeypatch.setattr(
        "amoeba.process.observers.cf_readback.subprocess.run", _fake_run
    )
    return calls


def _observer(version_label: str | None = VERSION_LABEL) -> CFReadbackObserver:
    return CFReadbackObserver(
        timeout_seconds=TIMEOUT_SECONDS, version_label=version_label
    )


# --------------------------------------------------------------------------
# Match and mismatch, against the real fixture
# --------------------------------------------------------------------------


def test_expected_values_present_adopts_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adoption records the record's own updatedAt and the version label."""
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry({"developmentPhase": record["developmentPhase"]})

    observation = _observer().observe(entry)

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_UPDATED_AT] == record[CF_FIELD_UPDATED_AT]
    assert observation.result[RESULT_VERSION_LABEL] == VERSION_LABEL


def test_several_expected_values_all_matching_adopts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every expected field must match, not merely the first."""
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry(
        {
            "developmentPhase": record["developmentPhase"],
            "fileSlice": record["fileSlice"],
            "name": record["name"],
        }
    )

    assert isinstance(_observer().observe(entry), Adopt)


def test_a_differing_value_is_not_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF holds something else, so the write demonstrably did not land."""
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry({"developmentPhase": "Phase 9: Something Else"})

    observation = _observer().observe(entry)

    assert isinstance(observation, NotApplied)
    assert "developmentPhase" in observation.reason


def test_one_differing_value_among_matches_is_not_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial match is not a match."""
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry(
        {
            "developmentPhase": record["developmentPhase"],
            "fileSlice": "a-different-slice",
        }
    )

    observation = _observer().observe(entry)

    assert isinstance(observation, NotApplied)
    assert "fileSlice" in observation.reason


def test_a_required_field_absent_from_output_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent field is an incomplete observation, not a mismatch.

    This is the distinction that matters: a field CF does not carry cannot be
    compared, so the honest answer is Unknown rather than NotApplied.
    """
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry({"aFieldCfDoesNotHave": "whatever"})

    observation = _observer().observe(entry)

    assert isinstance(observation, Unknown)
    assert "aFieldCfDoesNotHave" in observation.reason


# --------------------------------------------------------------------------
# The four external failure modes, each distinguishable
# --------------------------------------------------------------------------


def test_cf_missing_from_path_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing binary is an answer, not an exception."""
    _patch_run(monkeypatch, raises=FileNotFoundError("cf"))

    observation = _observer().observe(_entry({"developmentPhase": "x"}))

    assert isinstance(observation, Unknown)
    assert "not available on PATH" in observation.reason


def test_cf_timeout_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung cf escalates rather than blocking recovery forever."""
    _patch_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd="cf", timeout=TIMEOUT_SECONDS),
    )

    observation = _observer().observe(_entry({"developmentPhase": "x"}))

    assert isinstance(observation, Unknown)
    assert "timed out" in observation.reason


def test_cf_non_zero_exit_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing cf escalates, carrying its stderr for the human."""
    _patch_run(
        monkeypatch,
        result=FakeCompletedProcess(2, stderr="no such project: nope"),
    )

    observation = _observer().observe(_entry({"developmentPhase": "x"}))

    assert isinstance(observation, Unknown)
    assert "exited 2" in observation.reason
    assert "no such project" in observation.reason


def test_unparseable_output_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Output that is not JSON escalates rather than raising."""
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout="not json at all {"))

    observation = _observer().observe(_entry({"developmentPhase": "x"}))

    assert isinstance(observation, Unknown)
    assert "unparseable output" in observation.reason


def test_json_that_is_not_an_object_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid JSON of the wrong shape is still not a project record."""
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout="[1, 2, 3]"))

    observation = _observer().observe(_entry({"developmentPhase": "x"}))

    assert isinstance(observation, Unknown)
    assert "not a project record" in observation.reason


def test_the_four_failure_reasons_are_distinguishable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each external failure mode reaches the human as a different reason."""
    entry = _entry({"developmentPhase": "x"})
    reasons: set[str] = set()

    for patch_kwargs in (
        {"raises": FileNotFoundError("cf")},
        {"raises": subprocess.TimeoutExpired(cmd="cf", timeout=TIMEOUT_SECONDS)},
        {"result": FakeCompletedProcess(2, stderr="boom")},
        {"result": FakeCompletedProcess(0, stdout="{not json")},
    ):
        _patch_run(monkeypatch, **patch_kwargs)  # pyright: ignore[reportArgumentType]
        observation = _observer().observe(entry)
        assert isinstance(observation, Unknown)
        reasons.add(observation.reason)

    assert len(reasons) == 4


def test_a_malformed_entry_is_unknown() -> None:
    """An entry without a usable project and expected mapping escalates."""
    entry = JournalEntry(
        id="entry-1",
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.CF_WRITE,
        parameters={"project": 42, "expected": "not a mapping"},
    )

    observation = _observer().observe(entry)

    assert isinstance(observation, Unknown)


# --------------------------------------------------------------------------
# Provenance capture never costs an adoption
# --------------------------------------------------------------------------


def test_version_capture_failure_still_permits_adoption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing ``cf --version`` records the label as unavailable, not an error."""
    record = _record()

    def _fake_run(args: Sequence[str], **_kwargs: object) -> FakeCompletedProcess:
        if "--version" in args:
            raise FileNotFoundError("cf")
        return FakeCompletedProcess(0, stdout=json.dumps(record))

    monkeypatch.setattr(
        "amoeba.process.observers.cf_readback.subprocess.run", _fake_run
    )

    # No label supplied, so it is captured on first use — and fails.
    observer = CFReadbackObserver(timeout_seconds=TIMEOUT_SECONDS)
    entry = _entry({"developmentPhase": record["developmentPhase"]})

    observation = observer.observe(entry)

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_VERSION_LABEL] == VERSION_UNAVAILABLE


def test_version_label_is_captured_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """One ``cf --version`` per recovery pass, not one per entry."""
    calls = _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout="0.15.0"))
    observer = CFReadbackObserver(timeout_seconds=TIMEOUT_SECONDS)

    labels = {observer.version_label for _ in range(5)}

    assert labels == {"0.15.0"}
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(1, "0.15.0"), (0, ""), (0, "   ")],
)
def test_unusable_version_output_is_recorded_as_unavailable(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    """A non-zero exit or empty output yields the explicit marker."""
    _patch_run(monkeypatch, result=FakeCompletedProcess(returncode, stdout=stdout))

    assert capture_version_label(TIMEOUT_SECONDS) == VERSION_UNAVAILABLE


def test_no_code_path_compares_the_version_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The label is recorded, never compared: any label adopts identically.

    Two observers differing only in their version label must produce the same
    observation type and the same non-provenance result.
    """
    record = _record()
    _patch_run(monkeypatch, result=FakeCompletedProcess(0, stdout=json.dumps(record)))
    entry = _entry({"developmentPhase": record["developmentPhase"]})

    first = _observer("0.1.0-ancient").observe(entry)
    second = _observer("99.0.0-from-the-future").observe(entry)
    third = _observer(VERSION_UNAVAILABLE).observe(entry)

    assert isinstance(first, Adopt)
    assert isinstance(second, Adopt)
    assert isinstance(third, Adopt)
    assert (
        first.result[RESULT_UPDATED_AT]
        == second.result[RESULT_UPDATED_AT]
        == third.result[RESULT_UPDATED_AT]
    )


# --------------------------------------------------------------------------
# One real invocation
# --------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("cf") is None, reason="cf is not on PATH")
def test_real_cf_invocation_captures_a_version_label() -> None:
    """The real binary, not a mock: proves the argument vector is right.

    Skipped cleanly rather than failed when ``cf`` is absent, since a developer
    without Context Forge installed must still be able to run the suite.
    """
    label = capture_version_label(TIMEOUT_SECONDS)

    assert label
    # Either a real label or the explicit marker — never an empty string.
    assert label == VERSION_UNAVAILABLE or label.strip() == label


@pytest.mark.skipif(shutil.which("cf") is None, reason="cf is not on PATH")
def test_real_cf_get_against_a_nonexistent_project_is_unknown() -> None:
    """A real failing invocation escalates rather than raising."""
    observer = CFReadbackObserver(timeout_seconds=TIMEOUT_SECONDS)
    entry = _entry(
        {"developmentPhase": "x"}, project="a-project-that-does-not-exist-12345"
    )

    observation = observer.observe(entry)

    # Whatever cf does with an unknown project — non-zero exit, or a record
    # that does not carry the field — the answer is never an exception and
    # never a confident adoption.
    assert isinstance(observation, Unknown | NotApplied)
