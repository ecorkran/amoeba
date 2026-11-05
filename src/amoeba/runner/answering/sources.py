"""The one call the answering run makes to get its passages (slice 143, 144's input).

``assemble_sources`` finds the slice's checkout and target, reads the committed rules
and plan (``source_reads``), reads PM precedent from the question record, and hands
all of it to the pure ``assemble``. It writes nothing. A problem the repository or the
configuration can cause is returned as a value; only a programming error (a node CF
never indexed) raises.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.runner.answering.passages import (
    PassageSet,
    PmAnswer,
    SourcesProblem,
    assemble,
    unreadable,
)
from amoeba.runner.answering.source_reads import (
    CommittedSources,
    SliceRef,
    read_committed_sources,
)
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.dispatch.checkout_reads import ReadFailure, read_target
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import (
    AnsweredBy,
    CFSnapshot,
    Node,
    NodeKind,
    QuestionRecord,
    QuestionState,
    Store,
)
from amoeba.upstream.context_forge import CheckoutUnresolved, resolve_checkout


def slice_label(node: Node) -> str:
    """``"<cf.index> <title>"``: the label on PM passages and on ``question.md``.

    Raises:
        ValueError: The node has no ``cf.index``. The Runner only launches runs on
            CF-linked slices, so this is a programming error.
    """
    return f"{_cf_index(node)} {node.title}"


def _cf_index(node: Node) -> int:
    """The node's CF index; a node CF never indexed is a programming error."""
    if node.cf.index is None:
        raise ValueError(f"node {node.id} has no Context Forge index")
    return node.cf.index


def pm_precedent(store: Store, project_id: str) -> tuple[PmAnswer, ...]:
    """Every PM answer that has text and the question it answered (D6).

    An answer the answerer gave is never precedent: ``answered_by`` decides.

    Raises:
        ValueError: A record's slice node is missing.
    """
    found: list[PmAnswer] = []
    labels: dict[str, str] = {}  # one node read per slice, not per record
    for record in store.questions(project_id, state=QuestionState.ANSWERED):
        if record.answered_by is not AnsweredBy.PM:
            continue
        if not (record.answer and record.answer.strip()):
            continue
        if not (record.question and record.question.strip()):
            continue
        if record.node_id not in labels:
            node = store.get_node(record.node_id)
            if node is None:
                raise ValueError(f"question {record.id} names a missing node")
            labels[record.node_id] = slice_label(node)
        found.append(
            PmAnswer(
                record_id=record.id,
                question=record.question,
                answer=record.answer,
                date=record.updated_at,
                node_id=record.node_id,
                slice_label=labels[record.node_id],
            )
        )
    return tuple(found)


def _slice_ref(store: Store, node: Node) -> SliceRef:
    """The slice's index and its initiative's, as CF indexes them (D1)."""
    slice_index = _cf_index(node)
    parent = None if node.parent_id is None else store.get_node(node.parent_id)
    if parent is None or parent.kind is not NodeKind.INITIATIVE:
        raise ValueError(f"slice node {node.id} has no initiative parent")
    return SliceRef(slice_index=slice_index, initiative_index=_cf_index(parent))


def assemble_sources(
    store: Store,
    project_id: str,
    record: QuestionRecord,
    snapshot: CFSnapshot | None,
    cf_project_id: str,
    settings: AnswererSettings,
    budget: TickBudget,
    run: CfRun,
    timeout_seconds: float,
) -> PassageSet | SourcesProblem | None:
    """The passages for one question: a set, a named problem, or ``None``.

    ``None`` means the tick budget refused a call; the question stays pending and the
    next tick starts again. A problem is final: the caller declines the question.

    Raises:
        ValueError: The question's slice node is missing, unindexed, or has no
            initiative parent with an index.
    """
    node = store.get_node(record.node_id)
    if node is None:
        raise ValueError(f"question {record.id} names a missing node")
    slice_ref = _slice_ref(store, node)
    checkout = resolve_checkout(snapshot, slice_ref.slice_index, is_dir=Path.is_dir)
    if isinstance(checkout, CheckoutUnresolved):
        return unreadable(checkout.reason)
    target = read_target(checkout.path, cf_project_id, budget, run, timeout_seconds)
    if target is None:
        return None
    if isinstance(target, ReadFailure):
        return unreadable(target.detail)
    committed = read_committed_sources(
        checkout.path,
        target,
        slice_ref,
        settings.rules_paths,
        settings.passages_max_chars,
        budget,
        run,
        timeout_seconds,
    )
    if not isinstance(committed, CommittedSources):
        return committed
    return assemble(
        committed.files,
        pm_precedent(store, project_id),
        question_node_id=record.node_id,
        max_chars=settings.passages_max_chars,
        source_commit=committed.commit,
    )
