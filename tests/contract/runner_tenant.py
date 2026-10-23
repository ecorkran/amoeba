"""``ProofRunner``: a real tenant, driven by ``intent`` messages (slice 110, D3).

It stands in for initiative 120's Runner using only the public surface. Each
tick it takes one pending intent, performs the step the intent names through the
store API, and can send itself ``SIGKILL`` at a named point in the step.

The intent body is this proof's own test driver, not a contract: ``intent`` is
the Translator-to-Runner channel, and this format (a step name and an optional
crash point) is only how the proof steers a stand-in.

An intent is acknowledged *before* its step runs. A crash step would otherwise
find its own intent pending after the restart and crash again, forever.
"""

from __future__ import annotations

import hashlib
import os
import signal
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from sq_run_fixtures import run_id_of, sq_run_parameters

from amoeba.process import ResidentProcess
from amoeba.store import (
    AcknowledgmentOutcome,
    BlockedKind,
    CFReference,
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    JournalEntry,
    JournalOutcome,
    Message,
    Node,
    NodeKind,
    NodeStatus,
    SQReference,
    Store,
)
from amoeba.upstream.squadron import (
    parse_review_artifact,
    review_record_id,
    to_verdict_input,
)
from contract.standin import (
    STANDIN_PIPELINE,
    STATUS_COMPLETED,
    STATUS_PAUSED,
    new_run_id,
    render_review,
    write_outcome,
)

#: The tenant's name in logs.
RUNNER_NAME = "proof-runner"

#: Keys of an intent body, defined once for the driver that writes it and the
#: tenant that reads it.
INTENT_STEP = "step"
INTENT_CRASH_AT = "crash_at"

#: The Squadron parameter the stand-in runs carry and the journal entries match.
PARAM_SLICE = "slice"


class ProofStep(StrEnum):
    """What an intent asks the Runner to do."""

    BUILD_TREE = "build_tree"
    LAUNCH_REVIEW = "launch_review"
    CHECKPOINT = "checkpoint"
    FINISH = "finish"


class CrashPoint(StrEnum):
    """Where in a step the Runner kills itself."""

    #: After ``journal_issue`` commits, before any side effect.
    AFTER_JOURNAL = "after_journal"
    #: After the run file and review are written, before the report.
    AFTER_SIDE_EFFECT = "after_side_effect"


def _crash() -> None:
    """Die as a power cut would: nothing caught, flushed, or cleaned up."""
    os.kill(os.getpid(), signal.SIGKILL)


class ProofRunner:
    """Implements ``Tenant`` and nothing more."""

    def __init__(
        self,
        reviews_dirs: Mapping[str, Path],
        review_fixture: Path,
        standin_run_age: timedelta,
    ) -> None:
        self._reviews_dirs = dict(reviews_dirs)
        self._review_template = review_fixture.read_text(encoding="utf-8")
        self._standin_run_age = standin_run_age
        slice_name = parse_review_artifact(self._review_template).slice
        if slice_name is None:
            raise ValueError("the review fixture names no slice to attribute to")
        self._slice_name = slice_name

    @property
    def name(self) -> str:
        return RUNNER_NAME

    def tick(self, host: ResidentProcess) -> bool:
        """Finish any run left in flight, else perform one pending intent."""
        if self._finish_in_flight(host):
            return True
        for project_id in host.project_ids:
            store = host.store_for(project_id)
            pending = store.pending_intents(project_id)
            if not pending:
                continue
            message = pending[0]
            step, crash_at = _read_intent(message)
            store.acknowledge_message(
                message.id,
                acknowledged_by=RUNNER_NAME,
                outcome=AcknowledgmentOutcome.APPLIED,
            )
            self._perform(store, project_id, step, crash_at)
            return True
        return False

    def _finish_in_flight(self, host: ResidentProcess) -> bool:
        """Resolve each entry recovery left in flight, as the real Runner will.

        Recovery leaves an existing run to its issuer (slice 122, D3). A tick
        never starts with an entry of its own open, so any open ``sq_run``
        entry here was left by an earlier process and carries a run id.
        """
        finished = False
        for project_id in host.project_ids:
            store = host.store_for(project_id)
            for entry in store.unresolved_journal_entries(project_id):
                if entry.kind is not CommandKind.SQ_RUN:
                    continue
                store.journal_resolve(
                    entry.id,
                    outcome=JournalOutcome.COMPLETED,
                    result={"run_id": run_id_of(entry)},
                )
                finished = True
        return finished

    def _perform(
        self,
        store: Store,
        project_id: str,
        step: ProofStep,
        crash_at: CrashPoint | None,
    ) -> None:
        match step:
            case ProofStep.BUILD_TREE:
                self._build_tree(store, project_id)
            case ProofStep.LAUNCH_REVIEW:
                self._launch_review(store, project_id, crash_at)
            case ProofStep.CHECKPOINT:
                self._checkpoint(store, project_id)
            case ProofStep.FINISH:
                self._finish(store, project_id)

    def _build_tree(self, store: Store, project_id: str) -> None:
        """Initiative, then a slice 106's attribution rule finds, then its gate."""
        initiative = store.create_node(
            project_id=project_id, kind=NodeKind.INITIATIVE, title="proof initiative"
        )
        slice_node = store.create_node(
            project_id=project_id,
            kind=NodeKind.SLICE,
            title="proof slice",
            parent_id=initiative.id,
            cf=CFReference(slice_name=self._slice_name),
        )
        store.create_node(
            project_id=project_id,
            kind=NodeKind.GATE,
            title="proof gate",
            parent_id=slice_node.id,
        )

    def _launch_review(
        self, store: Store, project_id: str, crash_at: CrashPoint | None
    ) -> None:
        """Journal, do the stand-in side effect, then report in one transaction."""
        # On the reviewed node: a verdict's journal entry must be on its own node.
        slice_node = only_node(store, project_id, NodeKind.SLICE)
        now = datetime.now(UTC)
        run_id = new_run_id(now)
        entry = self._journal_run(store, slice_node, run_id)
        if crash_at is CrashPoint.AFTER_JOURNAL:
            _crash()

        write_outcome(
            Path.home(),
            run_id=run_id,
            started_at=now,
            updated_at=now,
            status=STATUS_COMPLETED,
        )
        review_path = self._reviews_dirs[project_id] / f"{run_id}.md"
        review_path.write_text(
            render_review(self._review_template, run_id), encoding="utf-8"
        )
        if crash_at is CrashPoint.AFTER_SIDE_EFFECT:
            _crash()

        self._report(store, project_id, entry, run_id, review_path)

    def _report(
        self,
        store: Store,
        project_id: str,
        entry: JournalEntry,
        run_id: str,
        review_path: Path,
    ) -> None:
        """Parse the artifact as detection would, so both derive one record id."""
        content = review_path.read_bytes()
        parsed = parse_review_artifact(content.decode("utf-8"))
        record_id = review_record_id(parsed)
        slice_node = only_node(store, project_id, NodeKind.SLICE)
        verdict = to_verdict_input(
            parsed,
            node_id=slice_node.id,
            record_id=record_id,
            journal_entry_id=entry.id,
            source_path=str(review_path),
        )
        detection = DetectionInput(
            project_id,
            str(review_path),
            hashlib.sha256(content).hexdigest(),
            DetectionOutcome.RUNNER_ISSUED,
            record_id=record_id,
        )
        store.record_runner_report(
            entry.id, verdict, detection, result={"run_id": run_id}
        )

    def _checkpoint(self, store: Store, project_id: str) -> None:
        """A paused run, owned by the journal, holding the gate at a checkpoint."""
        gate = only_node(store, project_id, NodeKind.GATE)
        now = datetime.now(UTC)
        run_id = new_run_id(now)
        entry = self._journal_run(store, gate, run_id)
        write_outcome(
            Path.home(),
            run_id=run_id,
            started_at=now,
            updated_at=now - self._standin_run_age,
            status=STATUS_PAUSED,
        )
        store.journal_resolve(
            entry.id, outcome=JournalOutcome.COMPLETED, result={"run_id": run_id}
        )
        store.update_sq_reference(gate.id, SQReference(run_id=run_id))
        store.block(
            gate.id,
            kind=BlockedKind.SQ_CHECKPOINT,
            context=f"paused run {run_id} awaits a decision",
        )

    def _finish(self, store: Store, project_id: str) -> None:
        for kind in (NodeKind.SLICE, NodeKind.GATE):
            node = only_node(store, project_id, kind)
            store.update_node_status(node.id, NodeStatus.DONE)

    def _journal_run(self, store: Store, node: Node, run_id: str) -> JournalEntry:
        """Command-before-result: the entry commits before any side effect.

        The run id is minted first and journaled with the command, as the
        Runner will do (slice 122), so recovery can find the run by id.
        """
        return store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters=sq_run_parameters(
                {"pipeline": STANDIN_PIPELINE, "params": self._run_params()},
                run_id=run_id,
            ),
        )

    def _run_params(self) -> dict[str, object]:
        return {PARAM_SLICE: self._slice_name}


def _read_intent(message: Message) -> tuple[ProofStep, CrashPoint | None]:
    body = message.payload
    if body is None or INTENT_STEP not in body:
        raise ValueError(f"intent {message.id!r} names no {INTENT_STEP!r}: {body!r}")
    crash_at = body.get(INTENT_CRASH_AT)
    return (
        ProofStep(str(body[INTENT_STEP])),
        None if crash_at is None else CrashPoint(str(crash_at)),
    )


def only_node(store: Store, project_id: str, kind: NodeKind) -> Node:
    """The project's one node of this kind; the proof's tree has exactly one."""
    matching = [
        node for node in store.nodes_for_project(project_id) if node.kind is kind
    ]
    if len(matching) != 1:
        raise ValueError(
            f"{project_id!r} has {len(matching)} {kind.value} nodes, expected one"
        )
    return matching[0]
