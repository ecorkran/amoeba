"""Member readability: can a program's member project be read right now?

A program is read through its members' own stores, links and checkouts. A member
that cannot be read must show up with the reason, not vanish, so the reasons are
a closed vocabulary computed from store reads and one directory check, first
failure wins:

1. ``store_missing`` — no ``{project_id}.sqlite3`` in the supervisor directory.
2. ``store_unreadable`` — the read-only open or a read raised a ``StoreError``.
3. ``unlinked`` — no CF link, or more than one (none is chosen).
4. ``snapshot_missing`` — the link has no ``observed`` snapshot.
5. ``checkout_unresolved`` — ``resolve_checkout`` at the member's requests
   initiative index names no checkout.

The checkout checked is the one that owns the requests initiative index, because
that is the checkout request runs use. No subprocess is started: it is store
reads plus ``Path.is_dir``. Readability is never stored; it is a function of the
stores and directories at the time of reading, so it cannot go stale.

Only the member's own failures are caught here. A member store's failure is the
member's problem, not the process's; the program store's own failures never pass
through this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from amoeba.store import Member, Store, StoreError
from amoeba.store.paths import STORE_FILE_SUFFIX, project_store_path
from amoeba.upstream.context_forge import (
    Checkout,
    CheckoutUnresolved,
    resolve_checkout,
)


class MemberUnreadableReason(StrEnum):
    """Why a member cannot be read, in the order they are checked."""

    STORE_MISSING = "store_missing"
    STORE_UNREADABLE = "store_unreadable"
    UNLINKED = "unlinked"
    SNAPSHOT_MISSING = "snapshot_missing"
    CHECKOUT_UNRESOLVED = "checkout_unresolved"


@dataclass(frozen=True)
class Readable:
    """A member that can be read: its one link and the checkout it resolves to."""

    cf_project_id: str
    checkout: Checkout


@dataclass(frozen=True)
class Unreadable:
    """A member that cannot be read, with the first reason that applies."""

    reason: MemberUnreadableReason
    detail: str


MemberState = Readable | Unreadable


def read_member(
    store_dir: Path, member: Member, *, busy_timeout_seconds: float | None = None
) -> MemberState:
    """Whether ``member`` can be read, and if not, why.

    Args:
        store_dir: The supervisor directory holding the member's store.
        member: The program member to read.
        busy_timeout_seconds: How long the member store's read-only open may
            wait on a lock. ``None`` is the store's own timeout.

    Returns:
        :class:`Readable`, or :class:`Unreadable` with the first failing reason.
        No exception escapes for any of the five reasons.
    """
    path = project_store_path(store_dir, member.project_id)
    if not path.is_file():
        return Unreadable(
            MemberUnreadableReason.STORE_MISSING,
            f"no {member.project_id}{STORE_FILE_SUFFIX} in {store_dir}",
        )

    try:
        with _open_read_only(path, busy_timeout_seconds) as store:
            links = store.cf_links(member.project_id)
            if len(links) != 1:
                return Unreadable(
                    MemberUnreadableReason.UNLINKED, _link_detail(len(links))
                )
            cf_project_id = links[0].cf_project_id
            observed = store.latest_cf_snapshots(member.project_id, cf_project_id)[1]
    except StoreError as error:
        # Specific: a corrupt, wrong-version or busy member store is that
        # member's problem, reported as its reason. Only the program store's own
        # failures may stop the process, and they do not pass through here.
        return Unreadable(MemberUnreadableReason.STORE_UNREADABLE, str(error))

    if observed is None:
        return Unreadable(
            MemberUnreadableReason.SNAPSHOT_MISSING,
            f"no observed snapshot of CF project {cf_project_id}",
        )

    checkout = resolve_checkout(
        observed, member.requests_initiative, is_dir=Path.is_dir
    )
    if isinstance(checkout, CheckoutUnresolved):
        return Unreadable(MemberUnreadableReason.CHECKOUT_UNRESOLVED, checkout.reason)
    return Readable(cf_project_id=cf_project_id, checkout=checkout)


def _open_read_only(path: Path, busy_timeout_seconds: float | None) -> Store:
    if busy_timeout_seconds is None:
        return Store.open_read_only(path)
    return Store.open_read_only(path, busy_timeout_seconds=busy_timeout_seconds)


def _link_detail(count: int) -> str:
    """Zero links and two links are both ``unlinked``; the detail says which."""
    if count == 0:
        return "the project has no CF link"
    return f"the project has {count} CF links; none is chosen"
