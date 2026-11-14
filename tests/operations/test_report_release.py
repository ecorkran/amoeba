"""``report_release``: each row of the D2 table, the member rule, no write on a
rejection (slice 227, D2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.release_support import (
    FULL_HASH,
    OTHER_HASH,
    OTHER_PROVIDER,
    PROVIDER,
    START,
    seed_members,
)

from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import (
    ReportOutcome,
    ReportReleaseResult,
)
from amoeba.store import releases
from amoeba.store.models import Release
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from operations.release_support import (
    CF_DOWN_DIR,
    NOT_A_PROJECT_DIR,
    NOT_IN_PROGRAM_DIR,
    OTHER_DIR,
    PROVIDER_DIR,
    SettableClock,
    release_deps,
    release_rows,
)

TOUCHED = ["cli", "store"]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return release_deps(tmp_path, clock)


def _document(
    mode: str = "report",
    *,
    commit: str = FULL_HASH,
    version: str | None = None,
    changed: str | None = "what changed",
    touched: list[str] | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {"mode": mode, "commit": commit}
    if mode != "withdraw":
        document["changed"] = changed
        document["touched"] = TOUCHED if touched is None else touched
    if version is not None:
        document["version"] = version
    return document


def _call(
    store: Store, deps: Deps, document: object, directory: Path = PROVIDER_DIR
) -> ReportReleaseResult:
    return report_release(store, document, directory=directory, deps=deps)


def _stored(store: Store, commit: str = FULL_HASH, member: str = PROVIDER) -> Release:
    with store.read() as transaction:
        found = releases.release_for_commit(transaction, member, commit)
    assert found is not None
    return found


def _absent(store: Store, commit: str = FULL_HASH) -> bool:
    with store.read() as transaction:
        return releases.release_for_commit(transaction, PROVIDER, commit) is None


# --- report mode: one test per D2 row ---------------------------------------


def test_a_new_commit_is_recorded_without_a_version(store: Store, deps: Deps) -> None:
    result = _call(store, deps, _document())
    assert result.outcome is ReportOutcome.RECORDED
    assert result.member == PROVIDER
    assert result.problems == ()
    stored = _stored(store)
    assert (stored.version, stored.versioned_at) == (None, None)
    assert stored.reported_at == START
    assert (stored.changed, stored.touched) == ("what changed", ("cli", "store"))
    assert result.report is not None
    assert result.report.seq == stored.seq
    assert result.report.reported_at == encode_timestamp(START)


def test_a_new_commit_with_a_version_is_recorded_versioned(
    store: Store, deps: Deps
) -> None:
    result = _call(store, deps, _document(version="tag-one"))
    assert result.outcome is ReportOutcome.RECORDED
    stored = _stored(store)
    assert (stored.version, stored.versioned_at) == ("tag-one", START)


def test_a_version_on_a_versionless_commit_versions_it_and_replaces_the_text(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, _document())
    first = _stored(store)
    clock.now = START + timedelta(hours=3)
    result = _call(
        store,
        deps,
        _document(version="tag-one", changed="release text", touched=["db"]),
    )
    assert result.outcome is ReportOutcome.VERSIONED
    stored = _stored(store)
    assert (stored.version, stored.versioned_at) == ("tag-one", clock.now)
    assert (stored.changed, stored.touched) == ("release text", ("db",))
    assert (stored.reported_at, stored.seq) == (first.reported_at, first.seq)


def test_a_different_version_on_a_versioned_commit_versions_it_again(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, _document(version="tag-one"))
    first = _stored(store)
    clock.now = START + timedelta(hours=3)
    result = _call(store, deps, _document(version="tag-two", changed="later"))
    assert result.outcome is ReportOutcome.VERSIONED
    stored = _stored(store)
    assert (stored.version, stored.versioned_at) == ("tag-two", clock.now)
    assert stored.changed == "later"
    assert (stored.reported_at, stored.seq) == (first.reported_at, first.seq)


def test_a_rephrased_repeat_is_unchanged_and_returns_the_stored_report(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, _document())
    clock.now = START + timedelta(hours=3)
    result = _call(store, deps, _document(changed="other words", touched=["x"]))
    assert result.outcome is ReportOutcome.UNCHANGED
    stored = _stored(store)
    assert (stored.changed, stored.touched) == ("what changed", ("cli", "store"))
    assert stored.reported_at == START
    assert result.report is not None
    assert result.report.changed == "what changed"


def test_a_repeat_with_the_same_version_is_unchanged(store: Store, deps: Deps) -> None:
    _call(store, deps, _document(version="tag-one"))
    result = _call(store, deps, _document(version="tag-one", changed="again"))
    assert result.outcome is ReportOutcome.UNCHANGED
    assert _stored(store).changed == "what changed"


def test_a_repeat_without_a_version_on_a_versioned_commit_is_unchanged(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, _document(version="tag-one"))
    result = _call(store, deps, _document())
    assert result.outcome is ReportOutcome.UNCHANGED
    assert _stored(store).version == "tag-one"


# --- correct ----------------------------------------------------------------


def test_correct_with_no_stored_report_is_rejected_and_writes_nothing(
    store: Store, deps: Deps
) -> None:
    result = _call(store, deps, _document("correct"))
    assert result.outcome is ReportOutcome.REJECTED
    assert result.report is None
    assert result.member == PROVIDER
    assert [problem.code for problem in result.problems] == [RejectCode.NOT_REPORTED]
    assert release_rows(store) == []


def test_correct_replaces_the_text_and_moves_reported_at(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _call(store, deps, _document())
    clock.now = START + timedelta(hours=5)
    result = _call(
        store, deps, _document("correct", changed="fixed", touched=["fixed"])
    )
    assert result.outcome is ReportOutcome.CORRECTED
    stored = _stored(store)
    assert (stored.changed, stored.touched) == ("fixed", ("fixed",))
    assert stored.reported_at == clock.now
    assert result.report is not None
    assert result.report.changed == "fixed"


# --- withdraw ---------------------------------------------------------------


def test_withdraw_with_no_stored_report_is_rejected(store: Store, deps: Deps) -> None:
    result = _call(store, deps, _document("withdraw"))
    assert result.outcome is ReportOutcome.REJECTED
    assert [problem.code for problem in result.problems] == [RejectCode.NOT_REPORTED]
    assert release_rows(store) == []


def test_withdraw_deletes_the_row_and_a_new_report_gets_a_new_seq(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, _document())
    first_seq = _stored(store).seq
    result = _call(store, deps, _document("withdraw"))
    assert result.outcome is ReportOutcome.WITHDRAWN
    assert result.report is None
    assert _absent(store)
    again = _call(store, deps, _document())
    assert again.outcome is ReportOutcome.RECORDED
    assert _stored(store).seq > first_seq


# --- members, rejections, failures ------------------------------------------


def test_the_same_commit_reported_by_two_members_gives_two_reports(
    store: Store, deps: Deps
) -> None:
    mine = _call(store, deps, _document(changed="mine"))
    theirs = _call(store, deps, _document(changed="theirs"), OTHER_DIR)
    assert (mine.outcome, theirs.outcome) == (
        ReportOutcome.RECORDED,
        ReportOutcome.RECORDED,
    )
    assert _stored(store, member=PROVIDER).changed == "mine"
    assert _stored(store, member=OTHER_PROVIDER).changed == "theirs"


def test_withdrawing_one_members_report_leaves_the_others(
    store: Store, deps: Deps
) -> None:
    _call(store, deps, _document())
    _call(store, deps, _document(), OTHER_DIR)
    _call(store, deps, _document("withdraw"))
    assert _absent(store)
    assert _stored(store, member=OTHER_PROVIDER).changed == "what changed"


def test_a_malformed_document_is_rejected_with_the_detail_and_writes_nothing(
    store: Store, deps: Deps
) -> None:
    result = _call(store, deps, _document(commit=OTHER_HASH[:7]))
    assert result.outcome is ReportOutcome.REJECTED
    assert result.member is None
    assert [problem.code for problem in result.problems] == [RejectCode.MALFORMED]
    assert "git rev-parse" in result.problems[0].detail
    assert release_rows(store) == []


def test_a_document_that_is_not_an_object_is_malformed(
    store: Store, deps: Deps
) -> None:
    result = _call(store, deps, ["not", "an", "object"])
    assert result.outcome is ReportOutcome.REJECTED
    assert result.problems[0].code is RejectCode.MALFORMED


def test_a_project_in_no_program_is_not_a_member(store: Store, deps: Deps) -> None:
    result = _call(store, deps, _document(), NOT_IN_PROGRAM_DIR)
    assert result.outcome is ReportOutcome.REJECTED
    assert result.member is None
    (problem,) = result.problems
    assert problem.code is RejectCode.NOT_A_MEMBER
    assert "Context Forge project is in no program" in problem.detail
    assert release_rows(store) == []


def test_a_directory_in_no_project_is_not_a_member(store: Store, deps: Deps) -> None:
    result = _call(store, deps, _document(), NOT_A_PROJECT_DIR)
    (problem,) = result.problems
    assert problem.code is RejectCode.NOT_A_MEMBER
    assert "directory is in no Context Forge project" in problem.detail
    assert release_rows(store) == []


def test_a_cf_failure_raises_and_writes_nothing(store: Store, deps: Deps) -> None:
    with pytest.raises(ContextForgeError):
        _call(store, deps, _document(), CF_DOWN_DIR)
    assert release_rows(store) == []
