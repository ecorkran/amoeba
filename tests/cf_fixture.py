"""The real ``projects.json`` fixture, and one-edit derivations of it."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).parents[0] / "fixtures" / "cf" / "projects.json"

AMOEBA_ID = "project_1781844717321_1gukaohbc"  # has worktrees
NO_WORKTREES_ID = "project_1782680529434_oxdc201u1"  # ai-project-guide
OTHER_ID = "project_1773962297191_18jiro1z8"  # hydrology-dashboard
DEFAULT_WORKTREE_ID = "wt_1792034653114_tcyv1a3ry"


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def fixture_entries() -> list[dict[str, Any]]:
    return json.loads(fixture_bytes())


def derived(edit: Callable[[list[dict[str, Any]]], object]) -> bytes:
    """The fixture with one stated edit applied, re-serialized."""
    entries = fixture_entries()
    edit(entries)
    return json.dumps(entries).encode("utf-8")


def entry(entries: list[dict[str, Any]], cf_id: str) -> dict[str, Any]:
    return next(item for item in entries if item["id"] == cf_id)
