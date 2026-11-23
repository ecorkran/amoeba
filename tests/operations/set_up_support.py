"""Shared by the ``set_up`` tests: a routing fake ``cf`` and a one-call runner.

Directory lookups replay a recorded ``cf get --json`` fixture. A ``-p`` reference
replays that same recording with the project's id and name swapped in, for as many
projects as a test registers; an unregistered reference replays the recorded
``PROJECT_NOT_FOUND`` document.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    fixture_document,
    replay,
)
from store.seed import insert_checkout, insert_member
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.operations.caller import find_member
from amoeba.operations.here import gather_checkout
from amoeba.operations.here_document import HereCheckout, HereNotAProject
from amoeba.operations.set_up import SetUpResult, set_up
from amoeba.store.programs import get_member_any, get_program, upsert_program
from amoeba.store.store import Store
from amoeba.store.vocabulary import RulesFrom
from amoeba.upstream.context_forge.target_read import CF_PROJECT_FLAG

DIRECTORY = Path("/work/checkout")
SEEDED_AT = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
#: The Context Forge id and name of the recorded default-worktree project.
RECORDED_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
RECORDED_NAME: str = fixture_document(DEFAULT_WORKTREE)["name"]


def project_document(project_id: str, name: str) -> dict[str, Any]:
    """The recorded project document with another project's id and name."""
    document = fixture_document(DEFAULT_WORKTREE)
    return {**document, "id": project_id, "name": name}


class FakeCf:
    """Routes ``cf get --json`` by working directory or ``-p`` reference."""

    def __init__(
        self,
        *,
        directory_fixture: str,
        projects: Sequence[tuple[str, str]] = (),
    ) -> None:
        self._directory_fixture = directory_fixture
        self._projects = [(RECORDED_ID, RECORDED_NAME), *projects]
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if CF_PROJECT_FLAG not in argv:
            return replay(argv, self._directory_fixture)
        reference = argv[list(argv).index(CF_PROJECT_FLAG) + 1]
        for project_id, name in self._projects:
            if reference in (project_id, name):
                text = json.dumps(project_document(project_id, name))
                return subprocess.CompletedProcess(list(argv), 0, text, "")
        return replay(argv, OUTSIDE_ANY_PROJECT)


def no_origin_git(
    argv: Sequence[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    """A ``git`` for a repo with no ``origin`` remote: ``remote get-url`` exits 2.

    The recorded project path is a real directory on a developer's machine, so tests
    never ask the real ``git`` about it.
    """
    return subprocess.CompletedProcess(list(argv), 2, "", "error: No such remote")


def gathered(
    directory_fixture: str = DEFAULT_WORKTREE,
    projects: Sequence[tuple[str, str]] = (),
) -> HereCheckout | HereNotAProject:
    """What the client part gathers from ``DIRECTORY`` with this stub ``cf``."""
    cf = FakeCf(directory_fixture=directory_fixture, projects=projects)
    return gather_checkout(DIRECTORY, cf, no_origin_git)


def seed_member(
    store: Store, program: str, project_id: str, name: str, path: str | None = None
) -> None:
    """A member whose id is ``project_id`` and whose name is ``name``, in ``program``
    (made when missing), with a checkout of that project on the acting machine.

    A member has its own id and is found by name, so a test that names a repo other
    than the working directory's seeds it first (261 9.8): ``add`` cannot create a
    member for a repo it was not run in. Both the name and the id find it.
    """
    with store.write() as transaction:
        if get_program(transaction, program) is None:
            upsert_program(
                transaction,
                program_id=program,
                concept_member=None,
                concept_path=None,
                now=SEEDED_AT,
            )
        insert_member(
            transaction,
            project_id=project_id,
            program_id=program,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=SEEDED_AT,
            updated_at=SEEDED_AT,
            rules_from=RulesFrom.CONFIG_DEFAULT,
            name=name,
        )
        insert_checkout(
            transaction,
            member_id=project_id,
            cf_project_id=project_id,
            path=f"/work/{name}" if path is None else path,
            now=SEEDED_AT,
        )


def register_projects(
    store: Store, document: object, projects: Sequence[tuple[str, str]]
) -> None:
    """Seed each project the request names that is not a member yet, in the request's
    program (see ``seed_member``)."""
    program = _program_of(document)
    if program is None:
        return
    for project_id, name in projects:
        if project_id == RECORDED_ID or not _mentions(document, name, project_id):
            continue
        with store.read() as transaction:
            known = find_member(transaction, name) or get_member_any(
                transaction, project_id
            )
        if known is None:
            seed_member(store, program, project_id, name)


def _program_of(document: object) -> str | None:
    if not isinstance(document, dict):
        return None
    fields = cast("dict[str, object]", document)
    program = fields.get("program")
    return program if isinstance(program, str) else None


def _mentions(document: object, name: str, project_id: str) -> bool:
    """Whether a member entry of the request names the project, by name or id.

    Only entries make a project a member of the request's program; a ``depends_on``,
    ``remove`` or ``concept`` reference to a project that was never seeded stays a
    reference to a non-member."""
    if not isinstance(document, dict):
        return False
    entries = cast("dict[str, object]", document).get("members", [])
    if not isinstance(entries, list):
        return False
    named = {
        cast("dict[str, object]", entry).get("project")
        for entry in cast("list[object]", entries)
        if isinstance(entry, dict)
    }
    return name in named or project_id in named


def run_set_up(
    store: Store,
    document: object,
    *,
    config: UserConfig | None = None,
    directory_fixture: str = DEFAULT_WORKTREE,
    projects: Sequence[tuple[str, str]] = (),
) -> SetUpResult:
    chosen = config if config is not None else user_config()
    register_projects(store, document, projects)
    # A request that names every member gathers nothing (261 D5).
    here = gathered(directory_fixture) if _has_unnamed_entry(document) else None
    return set_up(store, chosen, document, here=here)


def _has_unnamed_entry(document: object) -> bool:
    """Whether some entry of the request names no member (so the client part gathers
    the directory's checkout); a document that is not a mapping is gathered for."""
    if not isinstance(document, dict):
        return True
    members = cast("dict[str, object]", document).get("members", [])
    if not isinstance(members, list):
        return True
    entries = cast("list[object]", members)
    return any(
        not isinstance(entry, dict) or "project" not in cast("dict[str, object]", entry)
        for entry in entries
    )


def row_counts(store: Store) -> dict[str, int]:
    """Row count of each table ``set_up`` writes."""
    with store.read() as transaction:
        return {
            table: int(
                transaction.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            )
            for table in ("programs", "members", "dependency_pairs")
        }
