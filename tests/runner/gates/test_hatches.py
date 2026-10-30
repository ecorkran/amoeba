"""D4: the two ungate hatches, over every cell of the table."""

from __future__ import annotations

import pytest

from amoeba.runner.gates.cf_reads import ReadFailure
from amoeba.runner.gates.checks import RunnerCheck, check_id
from amoeba.runner.gates.hatches import (
    DesignMissing,
    DesignSource,
    DesignText,
    FrontmatterError,
    hatch_checks,
    read_frontmatter,
)
from amoeba.store import CheckOutcome, CheckStanding, RecordSource
from amoeba.store.check_models import check_standing
from runner.purity import io_use

PATH = "project-documents/user/slices/128-slice.x.md"
ENTRY = "entry-1"
NODE = "node-1"
VERSION = "amoeba-test"


def _design(frontmatter: str, *, path: str = PATH) -> DesignText:
    return DesignText(path, f"---\n{frontmatter}---\n\n# Design\n")


def _checks(
    design: DesignSource, effective_date: str | ReadFailure = ""
) -> dict[str, tuple[CheckOutcome, CheckStanding]]:
    review, date = hatch_checks(ENTRY, NODE, design, effective_date, VERSION)
    return {
        check.name: (
            check.outcome,
            check_standing(check.outcome, check.examined_count),
        )
        for check in (review, date)
    }


def _standings(
    design: DesignSource, effective_date: str | ReadFailure = ""
) -> tuple[CheckStanding, CheckStanding]:
    checks = _checks(design, effective_date)
    return (
        checks[RunnerCheck.UNGATE_REVIEW_NONE][1],
        checks[RunnerCheck.UNGATE_EFFECTIVE_DATE][1],
    )


@pytest.mark.parametrize(
    ("review", "standing"),
    [
        ("review: none\n", CheckStanding.FAILED),
        ("review: None\n", CheckStanding.FAILED),
        ("review: NONE\n", CheckStanding.FAILED),
        ('review: " none "\n', CheckStanding.FAILED),
        ("review: concerns\n", CheckStanding.PASSED),
        ("review:\n", CheckStanding.PASSED),
        ("", CheckStanding.PASSED),
    ],
)
def test_the_review_none_check_follows_the_frontmatter(
    review: str, standing: CheckStanding
) -> None:
    design = _design(f"dateCreated: 20261026\n{review}")

    assert _standings(design)[0] is standing


def test_a_design_without_frontmatter_errors_the_review_none_check() -> None:
    design = DesignText(PATH, "# Design\n\nNo frontmatter here.\n")

    assert _standings(design)[0] is CheckStanding.ERRORED


def test_frontmatter_that_is_not_yaml_errors_the_review_none_check() -> None:
    design = _design("review: [unclosed\n")

    assert _standings(design)[0] is CheckStanding.ERRORED


@pytest.mark.parametrize(
    ("effective", "created", "standing"),
    [
        ("20261020", "20261019", CheckStanding.FAILED),
        ("20261020", "20261020", CheckStanding.PASSED),
        ("20261020", "20261021", CheckStanding.PASSED),
        ("", "20200101", CheckStanding.PASSED),
        ("  ", "20200101", CheckStanding.PASSED),
    ],
)
def test_the_effective_date_check_compares_the_dates_as_text(
    effective: str, created: str, standing: CheckStanding
) -> None:
    design = _design(f"dateCreated: '{created}'\n")

    assert _standings(design, effective)[1] is standing


def test_a_date_created_that_yaml_loads_as_an_integer_compares_as_text() -> None:
    design = _design("dateCreated: 20261021\n")

    assert _standings(design, "20261022")[1] is CheckStanding.FAILED
    assert _standings(design, "20261021")[1] is CheckStanding.PASSED


@pytest.mark.parametrize(
    "effective", ["2026-10-20", "2026102", "abcdefgh", "202610200"]
)
def test_an_effective_date_that_is_not_eight_digits_errors(effective: str) -> None:
    design = _design("dateCreated: 20261026\n")

    assert _standings(design, effective)[1] is CheckStanding.ERRORED


def test_a_failed_config_read_errors_the_effective_date_check() -> None:
    design = _design("dateCreated: 20261026\n")

    assert _standings(design, ReadFailure("cf exited 1"))[1] is CheckStanding.ERRORED


def test_a_missing_date_created_errors_only_while_a_date_is_set() -> None:
    design = _design("review: concerns\n")

    assert _standings(design, "20261020")[1] is CheckStanding.ERRORED
    assert _standings(design, "")[1] is CheckStanding.PASSED


@pytest.mark.parametrize(
    "effective", ["", "20261020", ReadFailure("boom")], ids=["unset", "set", "failed"]
)
def test_a_missing_design_is_vacuous_for_both_unless_a_check_errored(
    effective: str | ReadFailure,
) -> None:
    design = DesignMissing("the slice list names no design file")

    review, date = _standings(design, effective)

    assert review is CheckStanding.VACUOUS
    assert date is (
        CheckStanding.ERRORED
        if isinstance(effective, ReadFailure)
        else CheckStanding.VACUOUS
    )


def test_a_missing_design_examines_nothing() -> None:
    review, date = hatch_checks(ENTRY, NODE, DesignMissing("gone", PATH), "", VERSION)

    assert review.examined_count == 0 and date.examined_count == 0


def test_a_design_that_was_read_examines_one_file_and_records_what_it_saw() -> None:
    design = _design("dateCreated: 20261019\nreview: none\n")

    review, date = hatch_checks(ENTRY, NODE, design, "20261020", VERSION)

    assert review.examined_count == date.examined_count == 1
    assert review.examined == {"design_path": PATH, "review": "none"}
    assert date.examined == {
        "design_path": PATH,
        "effective_date": "20261020",
        "date_created": "20261019",
    }


def test_ids_provenance_and_node_follow_d4() -> None:
    review, date = hatch_checks(
        ENTRY, NODE, _design("dateCreated: 20261026\n"), "", VERSION
    )

    assert review.id == check_id(ENTRY, RunnerCheck.UNGATE_REVIEW_NONE)
    assert review.id == "chk-entry-1-ungate_review_none"
    assert date.id == "chk-entry-1-ungate_effective_date"
    for check in (review, date):
        assert check.node_id == NODE
        assert check.provenance.upstream == "amoeba"
        assert check.provenance.upstream_version == VERSION
        assert check.provenance.source is RecordSource.DOCUMENT
        assert check.provenance.source_path == PATH


@pytest.mark.parametrize(
    "text",
    ["﻿---\nreview: none\n---\n", "\n  \n---\nreview: none\n---\nbody"],
    ids=["byte-order mark", "leading whitespace"],
)
def test_a_byte_order_mark_and_leading_whitespace_are_allowed(text: str) -> None:
    assert read_frontmatter(text) == {"review": "none"}


@pytest.mark.parametrize(
    "text", ["", "no delimiter", "---\nreview: none\n"], ids=["empty", "none", "open"]
)
def test_text_without_closed_frontmatter_is_an_error(text: str) -> None:
    assert isinstance(read_frontmatter(text), FrontmatterError)


def test_an_empty_frontmatter_block_is_an_empty_mapping() -> None:
    assert read_frontmatter("---\n---\nbody") == {}


def test_the_module_does_no_io() -> None:
    import amoeba.runner.gates.hatches as hatches

    assert io_use(hatches) == []
