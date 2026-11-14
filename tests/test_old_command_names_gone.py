"""The old command names are gone from the code, docs, README and tests (slice 229, D1).

Scans ``src``, ``docs``, ``README.md`` and ``tests`` for ``amoeba set_up``,
``amoeba handle_pause``, ``amoeba mark_read`` and ``OperationName.SET_UP``. The scan
reads each file whole and lets whitespace, a line break included, stand between
``amoeba`` and the name, so a name split across two lines of prose is found. This file
holds the patterns and is skipped, and so is any match on a line ending
``# old-name-case``, which marks a test that feeds an old name to the parser on purpose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCANNED = ("src", "docs", "README.md", "tests")
SELF = Path(__file__).resolve()
SKIP_MARK = "# old-name-case"
BINARY_SUFFIXES = {".pyc", ".sqlite3", ".png", ".gz", ".zip"}
#: What an old name looks like in text; ``\s+`` spans a line break.
OLD_NAMES = re.compile(
    r"amoeba\s+(?:set_up|handle_pause|mark_read)\b|OperationName\.SET_UP\b"
)


def _files() -> list[Path]:
    found: list[Path] = []
    for name in SCANNED:
        path = ROOT / name
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        found.extend(
            file
            for file in candidates
            if file.is_file()
            and file.suffix not in BINARY_SUFFIXES
            and "__pycache__" not in file.parts
            and file.resolve() != SELF
        )
    return found


def old_name_hits(text: str) -> list[tuple[int, str]]:
    """Each old name in ``text`` as (line number, the text matched), except where a
    line it spans ends with the skip mark."""
    lines = text.splitlines()
    hits: list[tuple[int, str]] = []
    for match in OLD_NAMES.finditer(text):
        first = text.count("\n", 0, match.start())
        last = text.count("\n", 0, match.end())
        spanned = lines[first : last + 1]
        if any(line.rstrip().endswith(SKIP_MARK) for line in spanned):
            continue
        hits.append((first + 1, " ".join(match.group(0).split())))
    return hits


def test_no_old_command_name_is_left() -> None:
    found = {
        f"{file.relative_to(ROOT)}:{line}: {text}"
        for file in _files()
        for line, text in old_name_hits(file.read_text(encoding="utf-8"))
    }

    assert not found, "old command names remain:\n" + "\n".join(sorted(found))


@pytest.mark.parametrize(
    "text",
    [
        "run `amoeba set_up --file x`",
        "run amoeba handle_pause RUN",
        "amoeba mark_read --through 3",
        "uses OperationName.SET_UP here",
        "the command `amoeba\nhandle_pause` is split",
        "amoeba   \n  set_up after blanks",
    ],
)
def test_the_scan_finds_each_old_name_even_split_across_lines(text: str) -> None:
    assert old_name_hits(text)


@pytest.mark.parametrize(
    "text",
    [
        "run `amoeba handle-pause RUN`",
        "amoeba mark-read --through 3",
        "the set_up engine keeps its module name",
        "`handle_pause` is the MCP tool and the operation name",
        "OperationName.ADD",
    ],
)
def test_the_scan_leaves_the_new_names_and_the_snake_case_tool_names_alone(
    text: str,
) -> None:
    assert old_name_hits(text) == []


def test_a_match_on_a_line_ending_the_skip_mark_is_skipped() -> None:
    text = f'main(["amoeba", "set_up"])  {SKIP_MARK}\n'

    assert old_name_hits(text) == []
    assert old_name_hits('print("amoeba set_up")\n') != []
