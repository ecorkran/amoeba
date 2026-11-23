"""Naming the members that exist (slice 261, D2, D4).

``open_state_store`` runs :func:`name_members` after it has the ``local`` machine, so
every command names the members from before migration 012 before anything reads one.

Gather, then write: one ``cf list projects`` call and one ``git remote get-url origin``
per member with a path, all before the write transaction (nothing runs ``cf`` or
``git`` under a lock). If ``cf`` fails, nothing is written and the next call tries
again; a member is never named by its id because ``cf`` was briefly broken. A ``git``
call that fails or times out only leaves that member with no ``origin``, and a warning.
The raw address git prints can hold a password: it is reduced at once and git's
stdout and stderr appear in no log line.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from amoeba.operations import here
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.origin import reduce_origin
from amoeba.store.checkouts import checkout_at, insert_checkout
from amoeba.store.machines import acting_machine_id
from amoeba.store.member_names import (
    UnnamedMember,
    active_member_by_name,
    active_member_by_origin,
    name_is_other_members_id,
    refuse_id_clash,
    retire_wake_command,
    set_member_name,
    set_member_origin,
    unnamed_members,
)
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import is_member_name
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.projects import ProjectDetail, project_details
from amoeba.upstream.git_read import (
    GitReadFailure,
    git_read,
    remote_origin_args,
)

logger = logging.getLogger(__name__)

#: All the ``git`` calls of one naming step share this much time (D4); each call also
#: has ``here.ORIGIN_READ_TIMEOUT_SECONDS``.
NAMING_GIT_SECONDS: Final = 30.0


def _git_root_within(path: Path, seconds: float) -> tuple[bool, Path | None]:
    """``here.git_root(path)``, or ``(False, None)`` when the file system does not
    answer within ``seconds``. The probe stats ``path``, which a hung mount can block
    for good and no subprocess timeout reaches, so it runs in a daemon thread that is
    left behind when it does not return."""
    found: list[Path | None] = []
    probe = threading.Thread(
        target=lambda: found.append(here.git_root(path)), daemon=True
    )
    probe.start()
    probe.join(seconds)
    if probe.is_alive():
        return False, None
    return True, found[0]


def _read_origin(path: Path, git: CfRun) -> str | None:
    """The reduced ``origin`` of the repo at ``path``, or ``None`` with a warning."""
    answered, root = _git_root_within(path, here.ORIGIN_READ_TIMEOUT_SECONDS)
    if not answered:
        logger.warning(
            "naming: %s did not answer within %ss (a hung mount?); its member has no "
            "origin",
            path,
            here.ORIGIN_READ_TIMEOUT_SECONDS,
        )
        return None
    if root is None:
        logger.info("naming: %s is not a git repo; its member has no origin", path)
        return None
    answer = git_read(remote_origin_args(), path, git, here.ORIGIN_READ_TIMEOUT_SECONDS)
    if isinstance(answer, GitReadFailure):
        logger.warning("naming: no origin read in %s: %s", path, answer.detail)
        return None
    if answer.exit_code == here.NO_SUCH_REMOTE_EXIT_CODE:
        return None
    if answer.exit_code != 0:
        logger.warning(
            "naming: git exited %s reading the origin in %s", answer.exit_code, path
        )
        return None
    return reduce_origin(answer.stdout)


def _gather_origins(
    members: tuple[UnnamedMember, ...],
    details: dict[str, ProjectDetail],
    git: CfRun,
    clock: Callable[[], float],
) -> dict[str, str]:
    """The reduced ``origin`` of each member whose project has a path, within budget."""
    origins: dict[str, str] = {}
    started = clock()
    unread = 0
    for member in members:
        detail = details.get(member.project_id)
        if detail is None or detail.path is None:
            continue
        if clock() - started >= NAMING_GIT_SECONDS:
            unread += 1
            continue
        origin = _read_origin(Path(detail.path), git)
        if origin is not None:
            origins[member.project_id] = origin
    if unread:
        logger.warning(
            "naming: the git time (%ss) ran out; %d members have no origin read",
            NAMING_GIT_SECONDS,
            unread,
        )
    return origins


def _name_for(
    transaction: Transaction,
    member: UnnamedMember,
    details: dict[str, ProjectDetail],
) -> str:
    """The Context Forge name when listed, valid and free, else the member's id.

    A removed member's name is for display only, so it skips the two clash checks.
    """
    detail = details.get(member.project_id)
    if detail is None:
        return _by_id(transaction, member, "Context Forge does not list its project")
    if not is_member_name(detail.name):
        return _by_id(
            transaction, member, f"{detail.name!r} is not a valid member name"
        )
    if member.removed:
        return detail.name
    if active_member_by_name(transaction, detail.name) is not None:
        return _by_id(
            transaction, member, f"another member already has the name {detail.name!r}"
        )
    if name_is_other_members_id(transaction, detail.name, member.project_id):
        return _by_id(transaction, member, f"{detail.name!r} is another member's id")
    return detail.name


def _by_id(transaction: Transaction, member: UnnamedMember, reason: str) -> str:
    """The member's own id as its name, said in the log so ``list members`` showing an
    id has a reason on record (``amoeba add --project ID --name NAME`` renames it). An
    id the name index would refuse is refused here, naming both members."""
    refuse_id_clash(transaction, member)
    logger.warning(
        "naming: member %s is named by its id: %s", member.project_id, reason
    )
    return member.project_id


def _origin_for(
    transaction: Transaction, member: UnnamedMember, origin: str | None
) -> str | None:
    """The member's ``origin``, or ``None`` when an active member has it (logged)."""
    if origin is None or member.removed:
        return origin
    holder = active_member_by_origin(transaction, origin)
    if holder is None:
        return origin
    logger.warning(
        "naming: member %s has the origin of member %s, so it keeps none",
        member.project_id,
        holder.project_id,
    )
    return None


def _write_member(
    transaction: Transaction,
    member: UnnamedMember,
    details: dict[str, ProjectDetail],
    origins: dict[str, str],
    now: datetime,
) -> None:
    set_member_name(
        transaction, member.project_id, _name_for(transaction, member, details), now
    )
    origin = _origin_for(transaction, member, origins.get(member.project_id))
    if origin is not None:
        set_member_origin(transaction, member.project_id, origin, now)
    detail = details.get(member.project_id)
    took = False
    if not (member.removed or detail is None or detail.path is None):
        machine_id = acting_machine_id(transaction)
        if checkout_at(transaction, machine_id, member.project_id) is None:
            insert_checkout(
                transaction,
                member_id=member.project_id,
                cf_project_id=member.project_id,
                path=detail.path,
                wake_command=member.wake_command,
                now=now,
            )
            took = True
    retire_wake_command(transaction, member, took)


def name_members(
    store: Store,
    cf: CfRun,
    git: CfRun,
    *,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Name the members that have no name, and give each active one its checkout.

    Raises:
        ContextForgeError: ``cf list projects`` failed; nothing was written.
        StoreError: The store failed.
    """
    with store.read() as transaction:
        waiting = unnamed_members(transaction)
    if not waiting:
        return
    listed = project_details(cf)
    if isinstance(listed, CfCallFailed):
        raise ContextForgeError(listed.detail)
    origins = _gather_origins(waiting, listed, git, clock)
    stamp = now()
    with store.write() as transaction:
        # Re-read under the lock: a concurrent call may have named them already.
        for member in unnamed_members(transaction):
            _write_member(transaction, member, listed, origins, stamp)
