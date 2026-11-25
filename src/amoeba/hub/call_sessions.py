"""What the hub does for a session's calls before it checks the door version
(slice 263, D6).

A session's ``session_tick`` and ``session_end`` set ``last_called_at`` and nothing
else of the machine's row, so an old session ticking never writes old versions onto a
machine an upgraded ``amoeba`` command has just touched. A ``session_tick`` refused
for its door version still leaves its row, with the versions the caller sent, so
``list`` can show the session as behind. The four session headers are read here and
nothing from them is stored unless every one has its shape.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from urllib.parse import unquote

from amoeba.operations.caller import find_caller
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.steps.models_session import SESSION_END, SESSION_TICK
from amoeba.operations.steps.session import write_behind_session
from amoeba.store.errors import SessionOfAnotherMachineError
from amoeba.store.models import Member
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    CLIENT_NAME_PATTERN,
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    is_session_directory,
    is_session_id,
)

#: The calls whose touch sets the time only.
SESSION_CALLS = frozenset({SESSION_TICK.name, SESSION_END.name})

type HeaderReader = Callable[[str], str | None]


def is_session_call(name: str) -> bool:
    return name in SESSION_CALLS


def _directory(text: str | None) -> str | None:
    """The decoded directory, or ``None`` for a missing, undecodable, over-long or
    control-character value."""
    if text is None:
        return None
    try:
        decoded = unquote(text, errors="strict")
    except UnicodeDecodeError:
        # Not UTF-8 after decoding: the value is bad, so no row is written.
        return None
    return decoded if is_session_directory(decoded) else None


def write_behind_row(  # noqa: PLR0913 - the call's parts the row is made from
    store: Store,
    machine_id: int,
    now: datetime,
    header: HeaderReader,
    client_version: str | None,
    door_version: int | None,
) -> None:
    """Keep or make the row of a refused tick (D6). Bad headers, or a caller that is
    no member, write nothing: the refusal stands either way."""
    session_id = header(HEADER_SESSION_ID)
    client = header(HEADER_SESSION_CLIENT)
    project = header(HEADER_SESSION_PROJECT)
    directory = _directory(header(HEADER_SESSION_DIRECTORY))
    if (
        session_id is None
        or not is_session_id(session_id)
        or client is None
        or CLIENT_NAME_PATTERN.fullmatch(client) is None
        or directory is None
        or client_version is None
        or door_version is None
    ):
        return
    here = (
        HereCaller(project_id=project)
        if project
        else HereNotAProject(not_a_project="no project header")
    )
    # A savepoint of the call scope, made after ``act_as`` so it acts as the caller.
    with store.write() as transaction:
        member = find_caller(transaction, machine_id, here)
        if not isinstance(member, Member):
            return
        try:
            write_behind_session(
                transaction,
                now,
                member.project_id,
                session_id,
                client,
                directory,
                client_version,
                door_version,
            )
        except SessionOfAnotherMachineError:
            # The session id belongs to another machine: no column was changed, and
            # the refusal the caller is owed stands.
            return
