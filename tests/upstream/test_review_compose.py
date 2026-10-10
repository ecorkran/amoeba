"""``to_verdict_input``: defaults, overrides, standing, and the D4 version rule."""

from __future__ import annotations

from pathlib import Path

import pytest
from review_fixtures import (
    PROVIDER_FAILURE_928,
    ROUND_1_PART_1,
    ROUND_2_PART_2,
    STAMPED_REVIEW_106,
)

from amoeba.store.evidence_models import (
    RecordSource,
    VerdictInput,
    VerdictStanding,
    verdict_standing,
)
from amoeba.upstream import squadron
from amoeba.upstream.squadron import (
    UpstreamVersionError,
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)

NODE = "node-under-test"
PRE_STAMP_LABEL = "label-from-the-caller"


def _parse(path: Path) -> squadron.ParsedReview:
    return parse_review_artifact(path.read_text(encoding="utf-8"))


def _standing(verdict: VerdictInput) -> VerdictStanding:
    return verdict_standing(
        provider_failure=verdict.provider_failure,
        verdict=verdict.verdict,
        findings_parsed=verdict.findings_parsed,
        derivation=verdict.derivation,
    )


def test_the_id_defaults_to_the_digest_and_upstream_is_squadron() -> None:
    parsed = _parse(ROUND_1_PART_1)
    composed = to_verdict_input(parsed, node_id=NODE, upstream_version=PRE_STAMP_LABEL)
    assert composed.id == review_record_id(parsed)
    assert composed.node_id == NODE
    assert composed.provenance.upstream == "squadron"
    assert composed.provenance.source is RecordSource.ARTIFACT_FRONTMATTER
    assert composed.findings == parsed.findings


def test_caller_values_pass_through() -> None:
    composed = to_verdict_input(
        _parse(ROUND_1_PART_1),
        node_id=NODE,
        record_id="chosen-id",
        upstream_version=PRE_STAMP_LABEL,
        journal_entry_id="journal-1",
        source_path="/abs/path.md",
    )
    assert composed.id == "chosen-id"
    assert composed.journal_entry_id == "journal-1"
    assert composed.provenance.source_path == "/abs/path.md"


def test_slice_and_source_document_do_not_reach_the_verdict_input() -> None:
    parsed = _parse(STAMPED_REVIEW_106)
    assert parsed.slice is not None and parsed.source_document is not None
    composed = to_verdict_input(parsed, node_id=NODE)
    assert not hasattr(composed, "slice")
    assert not hasattr(composed, "source_document")


@pytest.mark.parametrize(
    ("path", "standing"),
    [
        (ROUND_2_PART_2, VerdictStanding.PROVIDER_FAILURE),
        (PROVIDER_FAILURE_928, VerdictStanding.PROVIDER_FAILURE),
        (ROUND_1_PART_1, VerdictStanding.STATED),
    ],
)
def test_standing_on_real_files(path: Path, standing: VerdictStanding) -> None:
    parsed = _parse(path)
    label = None if parsed.upstream_version else PRE_STAMP_LABEL  # D4
    composed = to_verdict_input(parsed, node_id=NODE, upstream_version=label)
    assert _standing(composed) is standing


def test_a_stamp_alone_supplies_the_version() -> None:
    composed = to_verdict_input(_parse(STAMPED_REVIEW_106), node_id=NODE)
    assert composed.provenance.upstream_version == "0.15.0"


def test_an_argument_alone_supplies_the_version_for_a_pre_stamp_file() -> None:
    composed = to_verdict_input(
        _parse(ROUND_1_PART_1), node_id=NODE, upstream_version=PRE_STAMP_LABEL
    )
    assert composed.provenance.upstream_version == PRE_STAMP_LABEL


def test_neither_a_stamp_nor_an_argument_is_an_error() -> None:
    with pytest.raises(UpstreamVersionError, match="no upstream version"):
        to_verdict_input(_parse(ROUND_1_PART_1), node_id=NODE)


def test_a_stamp_and_a_different_argument_name_both_labels() -> None:
    with pytest.raises(UpstreamVersionError) as caught:
        to_verdict_input(
            _parse(STAMPED_REVIEW_106), node_id=NODE, upstream_version="0.1.0"
        )
    assert "0.15.0" in str(caught.value)
    assert "0.1.0" in str(caught.value)


def test_an_equal_stamp_and_argument_is_accepted() -> None:
    composed = to_verdict_input(
        _parse(STAMPED_REVIEW_106), node_id=NODE, upstream_version="0.15.0"
    )
    assert composed.provenance.upstream_version == "0.15.0"


def test_the_public_names_import() -> None:
    names = (
        "parse_review_json",
        "parse_review_artifact",
        "ParsedReview",
        "to_verdict_input",
        "review_record_id",
        "SquadronReviewError",
        "SquadronParseError",
        "UpstreamVersionError",
    )
    assert all(hasattr(squadron, name) for name in names)
    assert set(names) == set(squadron.__all__)
