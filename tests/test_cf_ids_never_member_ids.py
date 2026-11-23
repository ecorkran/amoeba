"""No ``cf`` argument list in the pause path is built from ``Member.project_id``
(slice 261, D6, 7.7): a member made by this slice has an id Context Forge does not
know, and ``cf -p`` fails for one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[1] / "src" / "amoeba" / "operations"
PAUSE_PATH = ("pause_context.py", "program_sources.py")
#: The attribute a member's id is read from.
MEMBER_ID_ATTRIBUTES = ("project_id",)
#: The ``cf``-reading functions whose arguments are checked.
CF_READERS = ("read_target", "read_initiatives", "read_slices", "resolve_slice")


def _member_id_reads(path: Path) -> list[int]:
    """Lines where a call to a ``cf`` reader has a ``.project_id`` in its arguments."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", None))
        if name not in CF_READERS:
            continue
        for argument in (*node.args, *(k.value for k in node.keywords)):
            for inner in ast.walk(argument):
                if (
                    isinstance(inner, ast.Attribute)
                    and inner.attr in MEMBER_ID_ATTRIBUTES
                ):
                    lines.append(inner.lineno)
    return lines


@pytest.mark.parametrize("name", PAUSE_PATH)
def test_no_cf_call_in_the_pause_path_is_given_a_member_id(name: str) -> None:
    assert _member_id_reads(SOURCE / name) == []


def test_the_scan_catches_a_member_id_given_to_a_reader(tmp_path: Path) -> None:
    path = tmp_path / "fixture.py"
    path.write_text(
        "read_target(checkout, member.project_id, run, 1.0)\n", encoding="utf-8"
    )

    assert _member_id_reads(path) == [1]
