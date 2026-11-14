"""``changes``: what each consumer sees of its providers' reports (slice 227, D3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.release_support import (
    FULL_HASH,
    OTHER_HASH,
    OTHER_PROVIDER,
    PROGRAM,
    PROVIDER,
    START,
    THIRD_HASH,
    at,
    seed_members,
)
from store.seed import insert_member, insert_pair

from amoeba.operations.changes import changes
from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesResult,
    ChangesWarningCode,
)
from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release import report_release
from amoeba.store import releases, sql
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from operations.release_support import (
    CF_DOWN_DIR,
    GONE_PROVIDER,
    NOT_A_PROJECT_DIR,
    NOT_IN_PROGRAM_DIR,
    OTHER_DIR,
    PROVIDER_DIR,
    RELEASE_CONSUMER,
    RELEASE_CONSUMER_DIR,
    SOURCE_CONSUMER,
    SOURCE_CONSUMER_DIR,
    SettableClock,
    database_dump,
    release_deps,
    seed_pairs,
)

NAMES = {
    PROVIDER: "provider",
    OTHER_PROVIDER: "other-provider",
    SOURCE_CONSUMER: "source-consumer",
    RELEASE_CONSUMER: "release-consumer",
    GONE_PROVIDER: "gone-provider",
}
TOUCHED = ("api",)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        seed_pairs(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return release_deps(tmp_path, clock, names=dict(NAMES))


def _since(hours: int) -> dict[str, object]:
    return {"since": encode_timestamp(at(hours))}


def _call(store: Store, deps: Deps, directory: Path, hours: int = 0) -> ChangesResult:
    return changes(store, _since(hours), directory=directory, deps=deps)


def _commits(result: ChangesResult, pair: int = 0) -> tuple[str, ...]:
    return tuple(report.commit for report in result.pairs[pair].releases)


def _report(
    store: Store, commit: str, hours: int, *, version: str | None = None
) -> None:
    with store.write() as transaction:
        releases.insert_release(
            transaction,
            PROVIDER,
            commit,
            version,
            f"text {commit[:1]}",
            TOUCHED,
            at(hours),
        )


def _version(store: Store, commit: str, hours: int, version: str = "tag-one") -> None:
    with store.write() as transaction:
        releases.add_version(
            transaction, PROVIDER, commit, version, "release text", TOUCHED, at(hours)
        )


def _correct(store: Store, commit: str, hours: int) -> None:
    with store.write() as transaction:
        releases.correct_release(
            transaction, PROVIDER, commit, None, "fixed", TOUCHED, at(hours)
        )


def test_the_merge_report_reaches_only_the_from_source_consumer(
    store: Store, deps: Deps
) -> None:
    _report(store, FULL_HASH, 1)
    source = _call(store, deps, SOURCE_CONSUMER_DIR)
    release = _call(store, deps, RELEASE_CONSUMER_DIR)
    assert source.outcome is ChangesOutcome.LISTED
    assert [pair.provider.id for pair in source.pairs] == [PROVIDER]
    assert _commits(source) == (FULL_HASH,)
    assert _commits(release) == ()
    assert release.pairs[0].consumed is ConsumedMode.FROM_RELEASE


def test_after_versioning_the_from_release_consumer_sees_it_with_the_text(
    store: Store, deps: Deps
) -> None:
    _report(store, FULL_HASH, 1)
    _version(store, FULL_HASH, 5)
    result = _call(store, deps, RELEASE_CONSUMER_DIR)
    (report,) = result.pairs[0].releases
    assert (report.version, report.changed) == ("tag-one", "release text")


def test_from_source_since_between_report_and_tag_sees_nothing_earlier_sees_one(
    store: Store, deps: Deps
) -> None:
    _report(store, FULL_HASH, 1)
    _version(store, FULL_HASH, 5)
    assert _commits(_call(store, deps, SOURCE_CONSUMER_DIR, 3)) == ()
    earlier = _call(store, deps, SOURCE_CONSUMER_DIR, 0)
    assert len(earlier.pairs[0].releases) == 1
    assert earlier.pairs[0].releases[0].version == "tag-one"


def test_a_correction_is_seen_by_a_since_before_it_and_not_after(
    store: Store, deps: Deps
) -> None:
    _report(store, FULL_HASH, 1)
    _correct(store, FULL_HASH, 6)
    assert _commits(_call(store, deps, SOURCE_CONSUMER_DIR, 3)) == (FULL_HASH,)
    assert _commits(_call(store, deps, SOURCE_CONSUMER_DIR, 7)) == ()


def test_two_since_values_each_see_everything_after_their_own_point(
    store: Store, deps: Deps
) -> None:
    _report(store, FULL_HASH, 1)
    _report(store, OTHER_HASH, 4)
    _report(store, THIRD_HASH, 8)
    assert _commits(_call(store, deps, SOURCE_CONSUMER_DIR, 3)) == (
        OTHER_HASH,
        THIRD_HASH,
    )
    assert _commits(_call(store, deps, SOURCE_CONSUMER_DIR, 6)) == (THIRD_HASH,)


def test_a_pair_with_nothing_visible_is_still_listed(store: Store, deps: Deps) -> None:
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert [pair.provider.id for pair in result.pairs] == [PROVIDER]
    assert result.pairs[0].releases == ()


def test_a_providers_provider_is_never_listed(store: Store, deps: Deps) -> None:
    with store.write() as transaction:
        releases.insert_release(
            transaction, OTHER_PROVIDER, OTHER_HASH, None, "deep", TOUCHED, at(1)
        )
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert [pair.provider.id for pair in result.pairs] == [PROVIDER]
    assert _commits(result) == ()
    # The provider itself is a consumer of the other one and sees that report.
    assert _commits(_call(store, deps, PROVIDER_DIR)) == (OTHER_HASH,)


def test_a_member_with_no_providers_gets_empty_pairs(store: Store, deps: Deps) -> None:
    result = _call(store, deps, OTHER_DIR)
    assert result.outcome is ChangesOutcome.LISTED
    assert result.pairs == ()
    assert result.member is not None
    assert result.member.id == OTHER_PROVIDER


def _add_provider(store: Store, provider_id: str) -> None:
    """A new member that ``SOURCE_CONSUMER`` depends on."""
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id=provider_id,
            program_id=PROGRAM,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=START,
            updated_at=START,
        )
        insert_pair(
            transaction,
            program_id=PROGRAM,
            provider_id=provider_id,
            consumer_id=SOURCE_CONSUMER,
            consumed=ConsumedMode.FROM_SOURCE,
            registered_at=START,
            updated_at=START,
        )


def test_a_pair_whose_member_was_removed_is_not_listed(
    store: Store, deps: Deps
) -> None:
    _add_provider(store, GONE_PROVIDER)
    # Only the member row is marked removed: the active-member rule (228) alone must
    # keep the surviving pair row out of the listing.
    with store.write() as transaction:
        transaction.execute(
            sql.REMOVE_MEMBER, (encode_timestamp(START),) * 2 + (GONE_PROVIDER,)
        )
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert [pair.provider.id for pair in result.pairs] == [PROVIDER]


def test_pairs_come_in_provider_id_order_and_every_one_is_listed(
    store: Store, deps: Deps
) -> None:
    _add_provider(store, GONE_PROVIDER)
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert [pair.provider.id for pair in result.pairs] == [GONE_PROVIDER, PROVIDER]


# --- rejections and failures ------------------------------------------------


@pytest.mark.parametrize(
    "directory",
    [NOT_IN_PROGRAM_DIR, NOT_A_PROJECT_DIR],
    ids=["no-program", "no-project"],
)
def test_a_non_member_directory_is_rejected(
    store: Store, deps: Deps, directory: Path
) -> None:
    result = _call(store, deps, directory)
    assert result.outcome is ChangesOutcome.REJECTED
    assert result.member is None
    assert result.pairs == ()
    assert [problem.code for problem in result.problems] == [RejectCode.NOT_A_MEMBER]


def test_a_malformed_since_is_rejected(store: Store, deps: Deps) -> None:
    result = changes(
        store,
        {"since": "2026-11-09T12:00:00"},
        directory=SOURCE_CONSUMER_DIR,
        deps=deps,
    )
    assert result.outcome is ChangesOutcome.REJECTED
    assert [problem.code for problem in result.problems] == [RejectCode.MALFORMED]
    assert "no UTC offset" in result.problems[0].detail


def test_a_cf_names_failure_raises(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    deps = release_deps(tmp_path, clock, names=CfCallFailed("cf is down"))
    with pytest.raises(ContextForgeError, match="cf is down"):
        _call(store, deps, SOURCE_CONSUMER_DIR)


def test_a_cf_failure_finding_the_project_raises(store: Store, deps: Deps) -> None:
    with pytest.raises(ContextForgeError):
        _call(store, deps, CF_DOWN_DIR)


# --- names and warnings -----------------------------------------------------


def test_names_are_filled_in_and_there_are_no_warnings(
    store: Store, deps: Deps
) -> None:
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert result.member is not None
    assert result.member.name == "source-consumer"
    assert result.pairs[0].provider.name == "provider"
    assert result.warnings == ()


def test_a_provider_absent_from_the_names_is_listed_with_a_warning(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    names = {key: value for key, value in NAMES.items() if key != PROVIDER}
    deps = release_deps(tmp_path, clock, names=names)
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert result.outcome is ChangesOutcome.LISTED
    assert result.pairs[0].provider.id == PROVIDER
    assert result.pairs[0].provider.name is None
    (warning,) = result.warnings
    assert warning.code is ChangesWarningCode.NOT_IN_CONTEXT_FORGE
    assert PROVIDER in warning.detail


def test_the_members_own_id_absent_from_the_names_warns_once(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    names = {key: value for key, value in NAMES.items() if key != SOURCE_CONSUMER}
    deps = release_deps(tmp_path, clock, names=names)
    result = _call(store, deps, SOURCE_CONSUMER_DIR)
    assert result.member is not None
    assert result.member.name is None
    (warning,) = result.warnings
    assert SOURCE_CONSUMER in warning.detail


# --- changes writes nothing --------------------------------------------------


def test_changes_leaves_every_table_unchanged(store: Store, deps: Deps) -> None:
    _report(store, FULL_HASH, 1, version="tag-one")
    before = database_dump(store)
    _call(store, deps, SOURCE_CONSUMER_DIR)
    _call(store, deps, RELEASE_CONSUMER_DIR)
    assert before
    assert database_dump(store) == before


# --- the door from report to read ---------------------------------------------


def test_a_report_made_through_report_release_is_what_changes_lists(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    clock.now = START + timedelta(hours=2)
    report_release(
        store,
        {"commit": FULL_HASH, "changed": "merged", "touched": ["api"]},
        directory=PROVIDER_DIR,
        deps=deps,
    )
    result = _call(store, deps, SOURCE_CONSUMER_DIR, 1)
    assert [report.changed for report in result.pairs[0].releases] == ["merged"]
