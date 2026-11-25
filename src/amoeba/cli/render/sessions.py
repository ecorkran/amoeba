"""The **Live sessions** section of ``status`` and ``list`` (slice 241, D8).

One line per live ``amoeba-mcp`` session, under its member: client, machine,
directory, how long it has served, how long since its last beat, and whether push is
confirmed, so the PM can see which sessions hold off waking. Left out when no member
has one. Sessions are not other agents' text and wait on nobody: they set no
notice and do not change ``Nothing needs you.``
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.cli.render.text import how_long, indented
from amoeba.operations.status_models import MemberStatus, SessionEntry

LIVE_SESSIONS: Final = "Live sessions"
PUSH_CONFIRMED: Final = "push confirmed"
PUSH_UNCONFIRMED: Final = "push unconfirmed"
#: Ends the line of a session on another door version than the hub's (263 D12).
BEHIND: Final = "behind"
#: Between a session line's fields.
FIELD_GAP: Final = "  "


def sessions_section(members: list[MemberStatus], now: datetime) -> list[str]:
    """The section, or nothing when no member has a live session."""
    lines: list[str] = []
    for member in members:
        if not member.sessions:
            continue
        lines.append(indented(member.member.name))
        lines.extend(
            indented(_session_line(entry, now), 2) for entry in member.sessions
        )
    return [LIVE_SESSIONS, *lines] if lines else []


def _session_line(entry: SessionEntry, now: datetime) -> str:
    push = PUSH_UNCONFIRMED if entry.push_confirmed_at is None else PUSH_CONFIRMED
    fields = [
        entry.client,
        entry.machine,
        entry.directory,
        f"up {how_long(entry.started_at, now)}",
        f"last beat {how_long(entry.heartbeat_at, now)} ago",
        push,
    ]
    if entry.behind:
        fields.append(BEHIND)
    return FIELD_GAP.join(fields)
