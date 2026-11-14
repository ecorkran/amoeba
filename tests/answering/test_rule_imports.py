"""The ``@path`` import parser (slice 229, D10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.answering.rule_imports import rule_imports

RULES_REPO = Path(__file__).parent / "fixtures" / "rules_repo"


def test_a_plain_import_at_the_start_of_a_line() -> None:
    assert rule_imports("@docs/rules.md\n") == ("docs/rules.md",)


def test_an_import_after_whitespace_in_a_sentence() -> None:
    assert rule_imports("Also read @docs/style.md for naming.\n") == ("docs/style.md",)


def test_a_fenced_import_is_not_an_import() -> None:
    text = "```\n@docs/rules.md\n```\n~~~md\n@docs/other.md\n~~~\n"

    assert rule_imports(text) == ()


def test_an_import_after_a_closed_fence_is_read() -> None:
    text = "```\n@inside.md\n```\n@outside.md\n"

    assert rule_imports(text) == ("outside.md",)


def test_inline_code_is_not_an_import() -> None:
    assert rule_imports("Write `@docs/rules.md` to import.\n") == ()


def test_an_import_beside_inline_code_is_still_read() -> None:
    assert rule_imports("`code` @docs/rules.md `more`\n") == ("docs/rules.md",)


@pytest.mark.parametrize(
    "token", ["@types/node", "@modelcontextprotocol/server", "@scope/pkg.js"]
)
def test_a_package_name_is_not_an_import(token: str) -> None:
    assert rule_imports(f"Install {token} first.\n") == ()


@pytest.mark.parametrize("ending", [".", ",", ";", ":", ")", ").", ".)"])
def test_trailing_punctuation_is_removed(ending: str) -> None:
    assert rule_imports(f"(see @docs/rules.md{ending}\n") == ("docs/rules.md",)


def test_an_at_sign_inside_a_word_is_not_an_import() -> None:
    assert rule_imports("mail me@host/notes.md now\n") == ()


@pytest.mark.parametrize("token", ["@/etc/rules.md", "@~/rules.md"])
def test_an_absolute_or_home_path_is_not_an_import(token: str) -> None:
    assert rule_imports(f"{token}\n") == ()


def test_a_parent_segment_is_returned_as_written() -> None:
    assert rule_imports("@../shared/rules.md\n") == ("../shared/rules.md",)


def test_a_bare_suffix_is_not_a_path() -> None:
    assert rule_imports("@.md\n") == ()


def test_each_import_is_returned_once_in_order() -> None:
    text = "@b.md\n@a.md\nsee @b.md again\n"

    assert rule_imports(text) == ("b.md", "a.md")


@pytest.mark.parametrize("name", ["CLAUDE.md", "AGENTS.md"])
def test_the_real_rules_files_hold_no_import(name: str) -> None:
    assert rule_imports((RULES_REPO / name).read_text(encoding="utf-8")) == ()
