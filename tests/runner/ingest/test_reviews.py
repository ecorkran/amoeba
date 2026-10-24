"""D7: select, read, parse and attribute a run's last review.

Review text comes from the real captures in ``tests/fixtures/sq_reviews/``; only
a file's ``slice`` frontmatter is rewritten, to point it at a node the test made.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from review_fixtures import PAIR_ARTIFACT, STAMPED_REVIEW_106
from sq_stub_scripts import (
    REVIEWS_DIR,
    RunScript,
    empty_reviews,
    missing_file_review,
    null_path_review,
    single_review,
    split_review,
    with_slice,
)

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.process.review_scan import examine
from amoeba.process.version_label import VERSION_UNAVAILABLE
from amoeba.runner.ingest.reviews import (
    ReviewFiles,
    ReviewScope,
    ReviewUnknown,
    select_review_files,
)
from amoeba.store import (
    CFReference,
    DetectionOutcome,
    Node,
    NodeKind,
    ReviewWatch,
    Store,
)
from amoeba.store.review_sources import DetectedFile
from amoeba.upstream.squadron import parse_review_artifact

PROJECT = "demo"
RUN_ID = "amoeba-20261024T101500Z-0123456789ab"
SLICE_NAME = "demo-slice"
VERSION_LABEL = "squadron 0.23.7"
NOW = datetime(2026, 10, 24, tzinfo=UTC)


class Rig:
    """A store with a slice node, a checkout on disk, and a scope over both."""

    def __init__(self, store: Store, checkout: Path) -> None:
        self.store = store
        self.checkout = checkout
        self.slice_node = self.add_slice(SLICE_NAME)
        self.watches: list[ReviewWatch] = []

    def add_slice(self, slice_name: str) -> Node:
        return self.store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title=slice_name,
            cf=CFReference(project="cf", slice_name=slice_name),
        )

    def scope(
        self, node: Node | None = None, label: str = VERSION_LABEL
    ) -> ReviewScope:
        return ReviewScope(
            project_id=PROJECT,
            run_id=RUN_ID,
            checkout=self.checkout,
            slice_node_id=(node or self.slice_node).id,
            slice_nodes=self.store.nodes_for_project(PROJECT),
            watches=self.watches,
            version_label=label,
        )

    def write(self, script: RunScript) -> RunOutcomeDocument:
        for relative, text in script.files.items():
            target = self.checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return RunOutcomeDocument.model_validate(
            {
                "run_id": RUN_ID,
                "outcome": RunOutcome.COMPLETED.value,
                **script.document,
            }
        )

    def select(
        self, script: RunScript, node: Node | None = None, label: str = VERSION_LABEL
    ) -> ReviewFiles | ReviewUnknown:
        return select_review_files(self.write(script), self.scope(node, label))


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with Store.open_temporary() as store:
        yield Rig(store, checkout)


def _reviews(result: ReviewFiles | ReviewUnknown) -> ReviewFiles:
    assert isinstance(result, ReviewFiles), result
    return result


def _unknown(result: ReviewFiles | ReviewUnknown) -> ReviewUnknown:
    assert isinstance(result, ReviewUnknown), result
    return result


def test_a_single_review_is_recorded_on_the_slice_node(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files

    [review] = _reviews(rig.select(script)).reviews

    file = rig.checkout / relative
    verdict, detection = review.verdict, review.detection
    assert verdict.node_id == rig.slice_node.id
    assert verdict.sq_run_id == RUN_ID
    assert verdict.journal_entry_id is None
    assert verdict.provenance.source_path == str(file.resolve())
    assert detection.outcome is DetectionOutcome.RUNNER_ISSUED
    assert detection.record_id == verdict.id
    assert (detection.project_id, detection.path) == (PROJECT, str(file.resolve()))
    assert detection.digest == hashlib.sha256(file.read_bytes()).hexdigest()


def test_a_split_review_is_recorded_part_by_part_in_order(rig: Rig) -> None:
    script = split_review(SLICE_NAME)
    document = rig.write(script)
    assert document.reviews is not None
    parts = document.reviews[-1].paths
    assert parts is not None

    result = _reviews(select_review_files(document, rig.scope()))

    assert [r.verdict.provenance.source_path for r in result.reviews] == [
        str((rig.checkout / part).resolve()) for part in parts
    ]
    assert len({r.verdict.id for r in result.reviews}) == 2


@pytest.mark.parametrize("script", [empty_reviews()], ids=["empty list"])
def test_an_empty_list_records_nothing(rig: Rig, script: RunScript) -> None:
    assert rig.select(script) == ReviewFiles(())


def test_a_document_with_no_reviews_key_records_nothing(rig: Rig) -> None:
    document = RunOutcomeDocument.model_validate(
        {"run_id": RUN_ID, "outcome": "completed"}
    )

    assert select_review_files(document, rig.scope()) == ReviewFiles(())


def test_only_the_last_entry_is_recorded(rig: Rig) -> None:
    first, last = single_review(SLICE_NAME), split_review(SLICE_NAME)
    entries = [
        *cast("list[object]", first.document["reviews"]),
        *cast("list[object]", last.document["reviews"]),
    ]
    document = rig.write(RunScript({**first.files, **last.files}, {"reviews": entries}))

    result = _reviews(select_review_files(document, rig.scope()))

    assert len(result.reviews) == 2


def test_a_null_path_and_paths_makes_the_review_unknown(rig: Rig) -> None:
    unknown = _unknown(rig.select(null_path_review()))

    assert unknown.path is None
    assert "neither path nor paths" in unknown.reason


def test_a_listed_file_that_is_missing_makes_the_review_unknown(rig: Rig) -> None:
    unknown = _unknown(rig.select(missing_file_review()))

    assert unknown.path is not None and "never-written" in unknown.path
    assert "missing" in unknown.reason


def test_an_unreadable_file_makes_the_review_unknown(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files
    (rig.checkout / relative).mkdir(parents=True)  # a directory cannot be read

    unknown = _unknown(
        select_review_files(rig.write(RunScript({}, script.document)), rig.scope())
    )

    assert "unreadable" in unknown.reason


def test_an_unparseable_file_makes_the_review_unknown(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files

    unknown = _unknown(
        rig.select(RunScript({relative: "not a review\n"}, script.document))
    )

    assert "does not parse" in unknown.reason


def test_a_review_with_no_slice_is_unknown(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files
    sliceless = re.sub(r"^slice:.*\n", "", script.files[relative], flags=re.MULTILINE)

    unknown = _unknown(rig.select(RunScript({relative: sliceless}, script.document)))

    assert "no slice" in unknown.reason


def test_attribution_to_no_node_makes_the_review_unknown(rig: Rig) -> None:
    unknown = _unknown(rig.select(single_review("a-slice-nobody-has")))

    assert "matches no single node" in unknown.reason


def test_attribution_to_several_nodes_makes_the_review_unknown(rig: Rig) -> None:
    rig.add_slice(SLICE_NAME)

    unknown = _unknown(rig.select(single_review(SLICE_NAME)))

    assert "matches no single node" in unknown.reason


def test_attribution_to_another_node_makes_the_review_unknown(rig: Rig) -> None:
    other = rig.add_slice("another-slice")

    unknown = _unknown(rig.select(single_review("another-slice")))

    assert other.id in unknown.reason
    assert "not the step's slice node" in unknown.reason


def test_one_bad_part_makes_the_whole_run_unknown(rig: Rig) -> None:
    script = split_review(SLICE_NAME)
    parts = list(script.files)
    broken = RunScript({parts[0]: script.files[parts[0]]}, script.document)

    unknown = _unknown(rig.select(broken))

    assert "missing" in unknown.reason


def _stamp_of(text: str) -> str | None:
    return parse_review_artifact(text).upstream_version


def test_an_unstamped_file_takes_the_captured_label(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files
    unstamped = re.sub(r"^squadronVersion:.*\n", "", script.files[relative], flags=re.M)
    assert _stamp_of(unstamped) is None

    [review] = _reviews(
        rig.select(RunScript({relative: unstamped}, script.document))
    ).reviews

    assert review.verdict.provenance.upstream_version == VERSION_LABEL


def test_a_stamped_file_keeps_its_own_stamp(rig: Rig) -> None:
    [review] = _reviews(rig.select(single_review(SLICE_NAME))).reviews

    stamp = _stamp_of(PAIR_ARTIFACT.read_text(encoding="utf-8"))
    assert stamp is not None
    assert review.verdict.provenance.upstream_version == stamp


def test_the_unavailable_marker_is_recorded_as_the_label(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    [relative] = script.files
    unstamped = re.sub(r"^squadronVersion:.*\n", "", script.files[relative], flags=re.M)

    [review] = _reviews(
        rig.select(
            RunScript({relative: unstamped}, script.document), label=VERSION_UNAVAILABLE
        )
    ).reviews

    assert review.verdict.provenance.upstream_version == VERSION_UNAVAILABLE


def test_a_file_in_a_watched_directory_is_keyed_by_the_watch_joined_path(
    rig: Rig,
) -> None:
    reviews_dir = rig.checkout / REVIEWS_DIR
    rig.watches.append(ReviewWatch(PROJECT, f"{reviews_dir}/", True, NOW, NOW, NOW))
    script = single_review(SLICE_NAME)
    [relative] = script.files

    [review] = _reviews(rig.select(script)).reviews

    assert review.detection.path == str(rig.checkout / relative)


def test_ingest_and_detection_compute_the_same_key(rig: Rig) -> None:
    """The Runner's ledger key is the one detection files the same file under."""
    reviews_dir = rig.checkout / REVIEWS_DIR
    rig.watches.append(ReviewWatch(PROJECT, str(reviews_dir), True, NOW, NOW, NOW))
    script = single_review(SLICE_NAME)
    [relative] = script.files
    [review] = _reviews(rig.select(script)).reviews
    file = rig.checkout / relative

    examine(rig.store, PROJECT, DetectedFile(file, file.read_bytes(), NOW), "label")

    row = rig.store.detection(PROJECT, review.detection.path, review.detection.digest)
    assert row is not None
    assert row.outcome is DetectionOutcome.INGESTED


def test_a_stamped_106_review_keeps_its_stamp_too(rig: Rig) -> None:
    text = with_slice(STAMPED_REVIEW_106.read_text(encoding="utf-8"), SLICE_NAME)
    relative = f"{REVIEWS_DIR}/{STAMPED_REVIEW_106.name}"

    [review] = _reviews(
        rig.select(RunScript({relative: text}, {"reviews": [{"path": relative}]}))
    ).reviews

    assert review.verdict.provenance.upstream_version == _stamp_of(text)
