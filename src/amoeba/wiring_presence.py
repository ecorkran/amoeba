"""The store and ``cf`` side of ``amoeba-mcp``'s presence (slice 241, D2, D3, D6).

``amoeba.mcp`` reaches nothing but ``wiring`` and the operations' types (226 D10), so
the synchronous bodies its worker threads run live here: each takes the store opener,
opens its own store (sqlite connections do not cross threads) and does one thing. The
types presence passes around are re-exported from here for the same reason.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from amoeba.operations.members import resolve_member
from amoeba.store.deliveries import highest_assigned_seq
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.models import Member, PushRow, Session
from amoeba.store.push_reads import member_high_seq, push_rows_after
from amoeba.store.sessions import delete_session, heartbeat
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.upstream.context_forge.cli_call import CfRun

__all__ = [
    "BUSY_TIMEOUT_SECONDS",
    "CfRun",
    "DeliveryEvent",
    "MemberLookup",
    "MessageKind",
    "PushRow",
    "Session",
    "StoreBusyError",
    "StoreError",
    "StoreOpener",
    "beat_session",
    "end_session",
    "lookup_member",
    "read_as_of_seq",
    "read_high_seq",
    "read_push_rows",
]

#: Opens a store; each worker call opens its own.
type StoreOpener = Callable[[], Store]


@dataclass(frozen=True)
class MemberLookup:
    """Where the server runs and the member it is, or why it is none."""

    directory: Path
    member_id: str | None
    #: For a non-member: what ``resolve_member`` said, for the log line.
    detail: str


def lookup_member(open_store: StoreOpener, cf_run: CfRun) -> MemberLookup:
    """Resolve the process's working directory to its member (D3).

    Raises:
        ContextForgeError: ``cf`` failed or timed out.
        StoreError: The lookup's read failed.
    """
    directory = Path.cwd()
    with open_store() as store:
        found = resolve_member(store, directory, cf_run)
    if isinstance(found, Member):
        return MemberLookup(directory, found.project_id, "")
    return MemberLookup(directory, None, str(found))


def beat_session(
    open_store: StoreOpener, session: Session, stale_seconds: float
) -> None:
    """One heartbeat: prune stale rows, then upsert ``session``, in one transaction."""
    with open_store() as store, store.write() as transaction:
        heartbeat(transaction, session, stale_seconds)


def end_session(open_store: StoreOpener, session_id: str) -> None:
    """Delete the session's row; an unknown id is a no-op."""
    with open_store() as store, store.write() as transaction:
        delete_session(transaction, session_id)


def read_high_seq(open_store: StoreOpener, member_id: str) -> int:
    with open_store() as store, store.read() as transaction:
        return member_high_seq(transaction, member_id)


def read_push_rows(
    open_store: StoreOpener, member_id: str, after_seq: int
) -> tuple[PushRow, ...]:
    with open_store() as store, store.read() as transaction:
        return push_rows_after(transaction, member_id, after_seq)


def read_as_of_seq(open_store: StoreOpener) -> int:
    """The number ``inbox`` reports as ``as_of_seq``."""
    with open_store() as store, store.read() as transaction:
        return highest_assigned_seq(transaction)
