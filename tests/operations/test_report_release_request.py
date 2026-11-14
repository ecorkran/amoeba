"""``ReportReleaseRequest``: the mode rules and field rules (slice 227, D1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from amoeba.operations.report_release_models import ReportMode, ReportReleaseRequest

HASH = "ab12" * 10
WRITING_MODES = (ReportMode.REPORT, ReportMode.CORRECT)


def _document(mode: ReportMode, **overrides: object) -> dict[str, object]:
    """A valid document for ``mode``, then the overrides; ``None`` drops a field."""
    document: dict[str, object] = {"mode": mode.value, "commit": HASH}
    if mode is not ReportMode.WITHDRAW:
        document |= {"changed": "what changed", "touched": ["one", "two"]}
    document |= overrides
    return {key: value for key, value in document.items() if value is not None}


def _rejected(document: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as raised:
        ReportReleaseRequest.model_validate(document)
    return str(raised.value)


@pytest.mark.parametrize("mode", list(ReportMode))
def test_a_valid_document_is_accepted_in_each_mode(mode: ReportMode) -> None:
    request = ReportReleaseRequest.model_validate(_document(mode))
    assert request.mode is mode
    assert request.commit == HASH


def test_mode_defaults_to_report() -> None:
    document = _document(ReportMode.REPORT)
    del document["mode"]
    assert ReportReleaseRequest.model_validate(document).mode is ReportMode.REPORT


@pytest.mark.parametrize("mode", list(ReportMode))
@pytest.mark.parametrize("commit", [HASH[:7], "z" * 40, "", "a" * 41])
def test_a_bad_hash_is_rejected_in_each_mode(mode: ReportMode, commit: str) -> None:
    assert "git rev-parse" in _rejected(_document(mode, commit=commit))


@pytest.mark.parametrize("mode", list(ReportMode))
def test_a_missing_hash_is_rejected_in_each_mode(mode: ReportMode) -> None:
    assert "commit" in _rejected(_document(mode, commit=None))


def test_an_upper_case_hash_is_stored_lowercased() -> None:
    request = ReportReleaseRequest.model_validate(
        _document(ReportMode.REPORT, commit=f"  {HASH.upper()} ")
    )
    assert request.commit == HASH


def test_a_64_character_hash_is_accepted() -> None:
    long_hash = "0f" * 32
    request = ReportReleaseRequest.model_validate(
        _document(ReportMode.REPORT, commit=long_hash)
    )
    assert request.commit == long_hash


@pytest.mark.parametrize("mode", WRITING_MODES)
@pytest.mark.parametrize("changed", ["", "   "])
def test_empty_changed_is_rejected(mode: ReportMode, changed: str) -> None:
    assert "changed" in _rejected(_document(mode, changed=changed))


@pytest.mark.parametrize("mode", WRITING_MODES)
def test_missing_changed_is_rejected_naming_field_and_mode(mode: ReportMode) -> None:
    message = _rejected(_document(mode, changed=None))
    assert f"changed is required in mode {mode.value}" in message


@pytest.mark.parametrize("mode", WRITING_MODES)
@pytest.mark.parametrize("touched", [[], [""], ["  "]])
def test_empty_touched_is_rejected(mode: ReportMode, touched: list[str]) -> None:
    assert "touched" in _rejected(_document(mode, touched=touched))


@pytest.mark.parametrize("mode", WRITING_MODES)
def test_missing_touched_is_rejected_naming_field_and_mode(mode: ReportMode) -> None:
    message = _rejected(_document(mode, touched=None))
    assert f"touched is required in mode {mode.value}" in message


@pytest.mark.parametrize("mode", WRITING_MODES)
def test_a_blank_version_is_rejected(mode: ReportMode) -> None:
    assert "version" in _rejected(_document(mode, version="  "))


@pytest.mark.parametrize("field", ["version", "changed", "touched"])
def test_withdraw_does_not_allow_the_field(field: str) -> None:
    value: object = ["x"] if field == "touched" else "x"
    message = _rejected(_document(ReportMode.WITHDRAW, **{field: value}))
    assert f"{field} is not allowed in mode withdraw" in message


@pytest.mark.parametrize("mode", list(ReportMode))
def test_an_unknown_field_is_rejected(mode: ReportMode) -> None:
    assert "extra_field" in _rejected(_document(mode, extra_field="x"))


def test_duplicate_touched_items_are_removed_in_order() -> None:
    request = ReportReleaseRequest.model_validate(
        _document(ReportMode.REPORT, touched=["b", "a", "b", " a ", "c"])
    )
    assert request.touched == ("b", "a", "c")


def test_version_is_stripped() -> None:
    request = ReportReleaseRequest.model_validate(
        _document(ReportMode.REPORT, version="  tag-one ")
    )
    assert request.version == "tag-one"


@pytest.mark.parametrize("mode", WRITING_MODES)
@pytest.mark.parametrize(
    "version", ["tag one", "tag\none", "tag\tone", "tag\x1b[31mone", "tag\x00one"]
)
def test_a_version_with_whitespace_or_control_characters_inside_is_rejected(
    mode: ReportMode, version: str
) -> None:
    assert "no whitespace" in _rejected(_document(mode, version=version))
