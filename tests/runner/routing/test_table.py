"""The table parser and load-time validation (D2, D4): one case per refusal."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from amoeba.runner.routing.inputs import RoutingInput
from amoeba.runner.routing.table import (
    VERSION_PREFIX,
    TableError,
    load_table,
    parse_table,
)
from amoeba.store import Route
from runner.routing.table_support import CATCH_ALL, small_table, table_text

ADVANCE = """\
- id: advance
  when: {outcome: completed, verdict: pass}
  route: advance
"""


def _escalate(when: str) -> str:
    return f"- id: r\n  when: {when}\n  route: escalate\n  judge_eligible: true\n"


def _problems(text: str) -> tuple[str, ...]:
    with pytest.raises(TableError) as raised:
        parse_table(text)
    return raised.value.problems


def _mentions(problems: tuple[str, ...], *words: str) -> bool:
    return any(all(word in problem for word in words) for problem in problems)


def test_a_valid_table_parses() -> None:
    table = small_table(ADVANCE)
    assert [rule.id for rule in table.rules] == ["advance", "catch-all"]
    assert table.rules[0].route is Route.ADVANCE
    assert table.rules[0].when[RoutingInput.VERDICT] == frozenset({"pass"})
    assert table.rules[1].parameters == {"judge_eligible": False}


def test_no_catch_all_is_refused() -> None:
    problems = _problems(table_text(ADVANCE, catch_all=False))
    assert _mentions(problems, "catch-all", "advance")


def test_a_catch_all_that_is_not_escalate_is_refused() -> None:
    text = (
        table_text(catch_all=False) + "  - id: tail\n    when: {}\n    route: advance\n"
    )
    assert _mentions(_problems(text), "catch-all", "tail")


def test_an_empty_when_before_the_last_rule_is_refused() -> None:
    early = "- id: early\n  when: {}\n  route: escalate\n  judge_eligible: false\n"
    assert _mentions(_problems(table_text(early)), "early", "not last")


def test_an_unknown_input_is_refused() -> None:
    rule = _escalate("{mood: grim}")
    assert _mentions(_problems(table_text(rule)), "r", "mood")


def test_gate_state_is_refused_before_slice_128() -> None:
    rule = _escalate("{gate_state: open}")
    assert _mentions(_problems(table_text(rule)), "gate_state", "not a routing input")


def test_an_unknown_value_is_refused() -> None:
    rule = (
        "- id: r\n  when: {verdict: great}\n  route: escalate\n  judge_eligible: true\n"
    )
    assert _mentions(_problems(table_text(rule)), "r", "verdict", "great")


def test_an_unknown_route_is_refused() -> None:
    rule = "- id: r\n  when: {verdict: pass}\n  route: teleport\n"
    assert _mentions(_problems(table_text(rule)), "r", "teleport")


@pytest.mark.parametrize(
    ("rule", "words"),
    [
        (
            "- id: r\n  when: {outcome: completed}\n  route: rerun\n",
            ("r", "rerun", "needs max_attempts"),
        ),
        (
            "- id: r\n  when: {outcome: completed}\n  route: rerun\n"
            "  max_attempts: 0\n",
            ("r", "at least 1"),
        ),
        (
            "- id: r\n  when: {outcome: completed}\n  route: advance\n"
            "  max_attempts: 2\n",
            ("r", "advance", "takes no max_attempts"),
        ),
        (
            "- id: r\n  when: {}\n  route: escalate\n",
            ("r", "needs judge_eligible"),
        ),
        (
            "- id: r\n  when: {outcome: completed}\n  route: rerun\n"
            "  max_attempts: 2\n  judge_eligible: true\n",
            ("r", "takes no judge_eligible"),
        ),
    ],
)
def test_a_missing_or_extra_parameter_is_refused(
    rule: str, words: tuple[str, ...]
) -> None:
    assert _mentions(_problems(table_text(rule)), *words)


@pytest.mark.parametrize("route", ["advance", "rerun"])
@pytest.mark.parametrize(
    "when",
    ["{verdict: pass}", "{outcome: paused}", "{outcome: [completed, failed]}"],
)
def test_advance_and_rerun_must_name_only_completed_outcome(
    route: str, when: str
) -> None:
    extra = "  max_attempts: 2\n" if route == "rerun" else ""
    rule = f"- id: r\n  when: {when}\n  route: {route}\n{extra}"
    assert _mentions(_problems(table_text(rule)), "r", "outcome: completed")


def test_a_duplicate_rule_id_is_refused() -> None:
    assert _mentions(_problems(table_text(ADVANCE + ADVANCE)), "advance", "twice")


def test_an_empty_rule_id_is_refused() -> None:
    rule = "- id: ''\n  when: {outcome: completed}\n  route: advance\n"
    assert _mentions(_problems(table_text(rule)), "empty id")


def test_a_missing_time_bound_is_refused() -> None:
    text = table_text(bounds={"P4": 240, "P5": 240})
    assert _mentions(_problems(text), "P6")


def test_an_extra_time_bound_is_refused() -> None:
    text = table_text(bounds={"P4": 240, "P5": 240, "P6": 720, "P9": 10})
    assert _mentions(_problems(text), "P9", "no step runs")


def test_a_non_positive_time_bound_is_refused() -> None:
    text = table_text(bounds={"P4": 0, "P5": 240, "P6": 720})
    assert _mentions(_problems(text), "P4", "positive")


def test_an_unsupported_format_is_refused() -> None:
    text = table_text().replace("format: 1", "format: 2")
    assert _mentions(_problems(text), "format 2", "not supported")


def test_malformed_yaml_names_the_yaml_error() -> None:
    assert _mentions(_problems("rules: [unclosed"), "not valid YAML")


def test_a_table_that_is_not_a_mapping_is_refused() -> None:
    assert _mentions(_problems("- just\n- a list\n"), "mapping")


def test_a_field_of_the_wrong_type_is_refused_by_name() -> None:
    text = table_text().replace("P4: 240", "P4: soon")
    assert _mentions(_problems(text), "time_bounds_minutes")


def test_an_extra_key_is_refused() -> None:
    assert _mentions(_problems(table_text() + "surprise: true\n"), "surprise")


def test_several_problems_are_all_reported() -> None:
    rules = (
        "- id: a\n  when: {mood: grim}\n  route: teleport\n"
        "- id: a\n  when: {verdict: great}\n  route: escalate\n  judge_eligible: true\n"
    )
    problems = _problems(table_text(rules, bounds={"P4": 240}, catch_all=False))
    assert len(problems) >= 6
    assert _mentions(problems, "mood")
    assert _mentions(problems, "teleport")
    assert _mentions(problems, "twice")
    assert _mentions(problems, "great")
    assert _mentions(problems, "P5")
    assert _mentions(problems, "catch-all")


def test_a_missing_file_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(TableError, match=str(missing)):
        load_table(missing)


def test_a_directory_is_an_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(TableError, match="cannot read"):
        load_table(tmp_path)


def test_a_file_of_non_utf8_bytes_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_bytes(b"format: 1\n\xff\xfe")
    with pytest.raises(TableError, match="not UTF-8"):
        load_table(path)


def test_load_table_names_the_path_in_content_problems(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(table_text(ADVANCE, catch_all=False), encoding="utf-8")
    with pytest.raises(TableError, match="t.yaml: .*catch-all"):
        load_table(path)


def test_flow_and_block_yaml_styles_parse_to_equal_rules() -> None:
    flow = "- id: r\n  when: {outcome: completed, verdict: pass}\n  route: advance\n"
    block = (
        "- id: r\n  when:\n    outcome: completed\n    verdict: pass\n"
        "  route: advance\n"
    )
    assert small_table(flow).rules == small_table(block).rules


def test_values_compare_after_trimming_and_lowering() -> None:
    upper = "- id: r\n  when: {outcome: completed, verdict: PASS}\n  route: advance\n"
    padded = (
        "- id: r\n  when: {outcome: completed, verdict: ' pass '}\n  route: advance\n"
    )
    assert small_table(upper).rules == small_table(padded).rules
    assert small_table(upper).rules[0].when[RoutingInput.VERDICT] == {"pass"}


def test_a_condition_may_be_a_list() -> None:
    rule = _escalate("{verdict: [concerns, fail]}")
    table = small_table(rule)
    assert table.rules[0].when[RoutingInput.VERDICT] == {"concerns", "fail"}


def test_a_bare_yaml_boolean_reads_as_the_value_true() -> None:
    rule = (
        "- id: r\n  when: {at_loop: true}\n  route: escalate\n  judge_eligible: true\n"
    )
    assert small_table(rule).rules[0].when[RoutingInput.AT_LOOP] == {"true"}


def test_the_version_is_the_digest_of_the_text_bytes() -> None:
    text = table_text(ADVANCE)
    expected = VERSION_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()
    table = parse_table(text)
    assert table.version == expected
    assert table.content == text


def test_one_byte_changed_gives_a_new_version() -> None:
    text = table_text(ADVANCE)
    assert parse_table(text).version != parse_table(text + "# edit\n").version


def test_load_table_matches_parse_table(tmp_path: Path) -> None:
    text = table_text(ADVANCE)
    path = tmp_path / "t.yaml"
    path.write_bytes(text.encode("utf-8"))
    assert load_table(path) == parse_table(text)


def test_the_catch_all_constant_is_a_valid_final_rule() -> None:
    assert "route: escalate" in CATCH_ALL
