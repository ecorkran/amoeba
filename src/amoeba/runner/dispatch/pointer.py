"""The CF slice pointer: write it in the checkout, then read it back (D2, D1).

``cf set -p <id> slice <index>`` runs in the step's checkout, because CF chooses a
worktree by working directory alone. The write is journaled before it is issued (a
``cf_write`` entry with the checkout and the index it expects), so a crash between
the journal and the write is recoverable. Every ``cf`` call goes through the tick
budget and the one bounded runner, and a failure is an answer, never an exception.

:func:`issue_pointer_write` journals, writes and reads back. It resolves nothing:
:func:`apply_set_result` and :func:`apply_answer` turn what happened into store
writes, so the same code finishes an entry whether the read-back happened in the tick
that wrote it or in a later one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from amoeba.process import (
    RESULT_FILE_SLICE,
    RESULT_PROJECT_PATH,
    RESULT_WORKTREE_ID,
    Adopt,
    NotApplied,
    ReadFailed,
    Unknown,
    read_back_answer,
)
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfCallFailed, CfRun, output_head, run_cf
from amoeba.runner.decide import WriteSlicePointer
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.lifecycle.plan_read import set_slice_argv
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED,
    PARAM_EXPECTED_SLICE_INDEX,
    PARAM_PROJECT,
    CommandKind,
    JournalEntry,
    Store,
)
from amoeba.upstream.context_forge import SliceStem, parse_slice_stem

#: The worktree the write was meant for (``None`` for a project without worktrees),
#: so a read-back in a later tick can judge the record without re-resolving.
PARAM_EXPECTED_WORKTREE_ID = "expected_worktree_id"


@dataclass(frozen=True)
class SetDone:
    """``cf set`` exited zero."""


@dataclass(frozen=True)
class SetFailed:
    """``cf set`` exited non-zero; ``detail`` is the head of its output."""

    exit_code: int
    detail: str


@dataclass(frozen=True)
class SetCutOff:
    """``cf set`` timed out or could not run: it may or may not have landed."""

    detail: str


type SetResult = SetDone | SetFailed | SetCutOff


@dataclass(frozen=True)
class Confirmed:
    """CF points at the slice, in the right checkout. ``result`` is what to record."""

    stem: SliceStem
    result: Mapping[str, object]


@dataclass(frozen=True)
class Mismatch:
    """CF reads another slice index, path or worktree than the write meant."""

    reason: str


@dataclass(frozen=True)
class PointerUnknown:
    """CF was read and its record cannot be judged (a field absent or unparseable)."""

    reason: str


@dataclass(frozen=True)
class PointerReadFailed:
    """``cf get`` could not be read; transient, so the read is repeated."""

    reason: str


type PointerAnswer = Confirmed | Mismatch | PointerUnknown | PointerReadFailed


@dataclass(frozen=True)
class PointerAttempt:
    """What one pointer write did. ``answer`` is ``None`` when no read-back happened."""

    entry: JournalEntry
    set_result: SetResult
    answer: PointerAnswer | None


def issue_pointer_write(
    store: Store,
    action: WriteSlicePointer,
    run: CfRun,
    timeout_seconds: float,
    budget: TickBudget,
) -> PointerAttempt | None:
    """Journal the write, run ``cf set`` in the checkout, and read it back.

    Returns ``None``, having written nothing, if the budget refuses the first call.
    The read-back is skipped, leaving the entry for the next tick's observe, when
    ``cf set`` failed or was cut off, or when the budget refuses a second call.
    """
    if not budget.allows_call():
        return None
    entry = store.journal_issue(
        action.node_id,
        kind=CommandKind.CF_WRITE,
        parameters={
            PARAM_PROJECT: action.cf_project_id,
            PARAM_CHECKOUT: str(action.checkout.path),
            PARAM_EXPECTED: {},
            PARAM_EXPECTED_SLICE_INDEX: action.slice_index,
            PARAM_EXPECTED_WORKTREE_ID: action.checkout.worktree_id,
        },
    )
    result = _set_slice(action, run, timeout_seconds)
    if not isinstance(result, SetDone) or not budget.allows_call():
        return PointerAttempt(entry, result, None)
    return PointerAttempt(
        entry, result, read_back(entry, action.checkout, run, timeout_seconds)
    )


def expected_checkout(entry: JournalEntry) -> Checkout | None:
    """The checkout a pointer-write entry meant, or ``None`` if it names none.

    ``None`` for an entry the Runner did not write as a pointer write (it has no
    expected slice index) or one with no checkout.
    """
    path = entry.parameters.get(PARAM_CHECKOUT)
    worktree_id = entry.parameters.get(PARAM_EXPECTED_WORKTREE_ID)
    if PARAM_EXPECTED_SLICE_INDEX not in entry.parameters:
        return None
    if not isinstance(path, str) or not path:
        return None
    return Checkout(Path(path), worktree_id if isinstance(worktree_id, str) else None)


def read_back(
    entry: JournalEntry, expected: Checkout, run: CfRun, timeout_seconds: float
) -> PointerAnswer:
    """Read CF in the entry's checkout and judge it against ``expected``.

    The observer's own function does the index check; this adds D1's check that the
    record answers for the resolved checkout: its path, and its worktree id (absent
    when the project has no worktrees).
    """
    answer = read_back_answer(entry, run, timeout_seconds)
    if isinstance(answer, ReadFailed):
        return PointerReadFailed(answer.reason)
    if isinstance(answer, Unknown):
        return PointerUnknown(answer.reason)
    if isinstance(answer, NotApplied):
        return Mismatch(answer.reason)
    return _confirmed(answer, expected)


def _confirmed(
    answer: Adopt, expected: Checkout
) -> Confirmed | Mismatch | PointerUnknown:
    result = answer.result
    file_slice = result.get(RESULT_FILE_SLICE)
    stem = parse_slice_stem(file_slice if isinstance(file_slice, str) else None)
    if stem is None:
        return PointerUnknown(f"CF's fileSlice does not parse: {file_slice!r}")
    path = result.get(RESULT_PROJECT_PATH)
    if not isinstance(path, str):
        return PointerUnknown(f"CF's projectPath is not a string: {path!r}")
    if Path(path) != expected.path:
        return Mismatch(f"CF answered for {path!r}, not {str(expected.path)!r}")
    worktree_id = result.get(RESULT_WORKTREE_ID)
    if worktree_id != expected.worktree_id:
        return Mismatch(
            f"CF answered for worktree {worktree_id!r}, not {expected.worktree_id!r}"
        )
    return Confirmed(stem, result)


def _set_slice(
    action: WriteSlicePointer, run: CfRun, timeout_seconds: float
) -> SetResult:
    in_checkout: CfRun = partial(run, cwd=str(action.checkout.path))
    completed = run_cf(
        set_slice_argv(action.cf_project_id, action.slice_index),
        in_checkout,
        timeout_seconds,
    )
    if isinstance(completed, CfCallFailed):
        return SetCutOff(completed.detail)
    if completed.returncode != 0:
        return SetFailed(completed.returncode, output_head(completed))
    return SetDone()
