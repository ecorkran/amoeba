"""Plan models and parsers, against real ``cf`` output (tests/fixtures/cf)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.upstream.context_forge import (
    READ_INITIATIVES,
    READ_SLICE_LIST,
    CFErrorDocument,
    CFInitiative,
    CFSliceEntry,
    CFSliceList,
    PlanEntryStatus,
    PlanParseError,
    UnknownPlanStatus,
    parse_initiatives,
    parse_slice_list,
    reported_complete,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cf"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _initiative(**overrides: object) -> str:
    entry: dict[str, object] = {"index": 1, "name": "n", "isChecked": False}
    return json.dumps([{**entry, **overrides}])


def _slice_list(*entries: dict[str, object]) -> str:
    return json.dumps({"entries": list(entries)})


def _slice_entry(**overrides: object) -> dict[str, object]:
    return {"index": 1, "name": "n", "isChecked": False, **overrides}


# --------------------------------------------------------------------------
# The captured output
# --------------------------------------------------------------------------


def test_initiatives_parse_with_every_index() -> None:
    raw = json.loads(_fixture("list_initiatives_a.json"))
    parsed = parse_initiatives(_fixture("list_initiatives_a.json"))
    assert [entry.index for entry in parsed] == [entry["index"] for entry in raw]
    assert all(isinstance(entry, CFInitiative) for entry in parsed)


def test_a_null_arch_file_parses() -> None:
    parsed = parse_initiatives(_fixture("list_initiatives_a.json"))
    unstarted = [entry for entry in parsed if entry.arch_file is None]
    assert unstarted
    assert all(entry.status == PlanEntryStatus.NOT_STARTED for entry in unstarted)


def test_a_complete_initiative_is_not_necessarily_checked() -> None:
    by_index = {
        e.index: e for e in parse_initiatives(_fixture("list_initiatives_a.json"))
    }
    assert by_index[120].status == PlanEntryStatus.COMPLETE
    assert by_index[120].is_checked is False
    assert reported_complete(by_index[120])


@pytest.mark.parametrize("name", ["list_slices_120.json", "list_slices_100.json"])
def test_slice_lists_parse(name: str) -> None:
    raw = json.loads(_fixture(name))
    parsed = parse_slice_list(_fixture(name))
    assert isinstance(parsed, CFSliceList)
    assert [entry.index for entry in parsed.entries] == [
        entry["index"] for entry in raw["entries"]
    ]
    assert all(entry.design_file for entry in parsed.entries[:1])


def test_the_error_fixture_parses_to_an_error_document() -> None:
    parsed = parse_slice_list(_fixture("list_slices_error.json"))
    assert isinstance(parsed, CFErrorDocument)
    assert parsed.error is True
    assert parsed.code == "UNKNOWN"


# --------------------------------------------------------------------------
# Leniency and strictness
# --------------------------------------------------------------------------


def test_unknown_extra_fields_are_ignored() -> None:
    [entry] = parse_initiatives(_initiative(somethingNew={"a": 1}))
    assert entry.index == 1
    parsed = parse_slice_list(_slice_list(_slice_entry(extra=1)))
    assert isinstance(parsed, CFSliceList)
    assert [entry.index for entry in parsed.entries] == [1]


@pytest.mark.parametrize("missing", ["index", "name", "isChecked"])
def test_a_missing_required_initiative_field_names_the_read(missing: str) -> None:
    entry: dict[str, object] = {"index": 7, "name": "n", "isChecked": False}
    del entry[missing]
    with pytest.raises(PlanParseError) as raised:
        parse_initiatives(json.dumps([entry]))
    assert raised.value.read == READ_INITIATIVES
    assert missing in raised.value.detail


def test_a_failing_entry_with_a_parsed_index_names_it() -> None:
    with pytest.raises(PlanParseError) as raised:
        parse_initiatives(json.dumps([{"index": 7, "name": "n"}]))
    assert raised.value.entry_index == 7
    assert "entry index 7" in str(raised.value)


def test_a_slice_entry_missing_its_index_has_no_entry_index() -> None:
    document = _slice_list({"name": "n", "isChecked": True})
    with pytest.raises(PlanParseError) as raised:
        parse_slice_list(document)
    assert raised.value.read == READ_SLICE_LIST
    assert raised.value.entry_index is None


def test_a_missing_entries_key_raises() -> None:
    with pytest.raises(PlanParseError) as raised:
        parse_slice_list(json.dumps({"slicePlan": "x", "total": 0}))
    assert raised.value.read == READ_SLICE_LIST
    assert "entries" in raised.value.detail


@pytest.mark.parametrize("text", ['{"entries": []}', '"text"', "42", "null"])
def test_a_non_array_initiatives_document_raises(text: str) -> None:
    with pytest.raises(PlanParseError) as raised:
        parse_initiatives(text)
    assert raised.value.read == READ_INITIATIVES


@pytest.mark.parametrize("text", ["[]", "42", "null"])
def test_a_non_object_slice_list_raises(text: str) -> None:
    with pytest.raises(PlanParseError):
        parse_slice_list(text)


@pytest.mark.parametrize("text", ["", "not json", "[1, 2"])
def test_malformed_json_raises_one_parse_error(text: str) -> None:
    with pytest.raises(PlanParseError, match="not JSON"):
        parse_initiatives(text)
    with pytest.raises(PlanParseError, match="not JSON"):
        parse_slice_list(text)


def test_an_empty_slice_list_parses() -> None:
    parsed = parse_slice_list(json.dumps({"entries": []}))
    assert isinstance(parsed, CFSliceList)
    assert parsed.entries == ()


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


def test_degraded_is_its_own_member() -> None:
    [entry] = parse_initiatives(_initiative(status="degraded"))
    assert entry.status is PlanEntryStatus.DEGRADED
    assert PlanEntryStatus.DEGRADED not in (
        PlanEntryStatus.COMPLETE,
        PlanEntryStatus.NOT_STARTED,
    )


def test_an_out_of_vocabulary_status_is_explicit_unknown() -> None:
    [entry] = parse_initiatives(_initiative(status="paused"))
    assert entry.status == UnknownPlanStatus(raw="paused")


def test_an_absent_status_is_none_not_a_default() -> None:
    [entry] = parse_initiatives(_initiative())
    assert entry.status is None


def test_a_slice_entry_status_is_coerced_the_same_way() -> None:
    parsed = parse_slice_list(
        _slice_list(_slice_entry(status="in_progress"), _slice_entry(status="odd"))
    )
    assert isinstance(parsed, CFSliceList)
    first, second = parsed.entries
    assert isinstance(first, CFSliceEntry)
    assert first.status is PlanEntryStatus.IN_PROGRESS
    assert second.status == UnknownPlanStatus(raw="odd")


@pytest.mark.parametrize(
    ("status", "is_checked", "expected"),
    [
        ("complete", False, True),
        ("in_progress", True, True),
        (None, True, True),
        ("in_progress", False, False),
        ("not_started", False, False),
        ("paused", False, False),
        (None, False, False),
    ],
)
def test_reported_complete(
    status: str | None, is_checked: bool, expected: bool
) -> None:
    overrides: dict[str, object] = {"isChecked": is_checked}
    if status is not None:
        overrides["status"] = status
    [entry] = parse_initiatives(_initiative(**overrides))
    assert reported_complete(entry) is expected
