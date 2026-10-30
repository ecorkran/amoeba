"""D6, D7: ``ingest`` blocks, records the reviews, and resolves, against a real store.

Review files are on disk (real captures, with only their ``slice`` rewritten) and
the run's outcome document comes from the stub ``sq``'s scripts, so the whole path
from document to verdict is the production one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sq_stub_scripts import (
    RunScript,
    empty_reviews,
    missing_file_review,
    null_path_review,
    single_review,
    split_review,
)

from amoeba.process import ProcessSettings, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.finish import record
from amoeba.runner.ingest.outcome import PAYLOAD_REASON, REASON_FAILED
from amoeba.runner.ingest.record import (
    PAYLOAD_PATH,
    PAYLOAD_REVIEW_FAULT,
    RESULT_OUTCOME_DOCUMENT,
    RESULT_REVIEW_FAULT,
    RESULT_VERDICT_IDS,
)
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.observed import RunEnded
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    BlockedKind,
    CFReference,
    Channel,
    CommandKind,
    DetectionOutcome,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeKind,
    Store,
    StoreError,
)

PROJECT = "demo"
RUN_ID = "amoeba-20261024T101500Z-0123456789ab"
SLICE_NAME = "demo-slice"
VERSION_LABEL = "sq-test-label"


class Rig:
    """A slice node with a step under it, a journaled run, and a checkout."""

    def __init__(self, store: Store, checkout: Path) -> None:
        self.store = store
        self.checkout = checkout
        self.slice_node = self.add_slice(SLICE_NAME)
        self.step = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title="tasks",
            parent_id=self.slice_node.id,
        )
        self.entry = self.journal(self.step)

    def add_slice(self, slice_name: str) -> Node:
        return self.store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title=slice_name,
            cf=CFReference(project="cf", slice_name=slice_name),
        )

    def journal(self, node: Node, **extra: object) -> JournalEntry:
        parameters: dict[str, object] = {
            PARAM_PIPELINE: "p5",
            PARAM_PARAMS: {},
            PARAM_RUN_ID: RUN_ID,
            PARAM_CHECKOUT: str(self.checkout),
            **extra,
        }
        return self.store.journal_issue(
            node.id, kind=CommandKind.SQ_RUN, parameters=parameters
        )

    def finish(
        self, script: RunScript, outcome: RunOutcome = RunOutcome.COMPLETED
    ) -> RunOutcomeDocument:
        """Write the run's files and ingest the document it would report."""
        for relative, text in script.files.items():
            target = self.checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        document = RunOutcomeDocument.model_validate(
            {
                "run_id": RUN_ID,
                "outcome": outcome.value,
                "status": outcome.value,
                **script.document,
            }
        )
        record(
            self.store,
            self.entry,
            RunEnded(document),
            VERSION_LABEL,
            ProcessSettings().auto_resume_limit,
        )
        return document

    def resolved(self) -> JournalEntry:
        entry = self.store.journal_entry(self.entry.id)
        assert entry is not None
        return entry

    def open_blocks(self) -> list[BlockedKind]:
        states = self.store.all_blocked_states(self.step.id)
        return [state.kind for state in states if not state.is_resolved]

    def escalation_payloads(self) -> list[dict[str, object]]:
        messages = self.store.messages(PROJECT, channel=Channel.ESCALATION)
        return [dict(message.payload or {}) for message in messages]


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with Store.open_temporary() as store:
        yield Rig(store, checkout)


def test_a_completed_run_records_its_review_on_the_slice_node(rig: Rig) -> None:
    rig.finish(single_review(SLICE_NAME))

    [verdict] = rig.store.verdicts(PROJECT)
    assert verdict.node_id == rig.slice_node.id
    assert verdict.sq_run_id == RUN_ID
    assert verdict.journal_entry_id is None
    [row] = rig.store.detections(PROJECT)
    assert row.outcome is DetectionOutcome.RUNNER_ISSUED
    assert row.verdict_id == verdict.id
    done = rig.resolved()
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.awaits_routing is True
    assert done.result is not None
    assert done.result[RESULT_VERDICT_IDS] == [verdict.id]
    assert done.result[RESULT_REVIEW_FAULT] is None
    assert rig.open_blocks() == []


def test_split_review_records_every_part(rig: Rig) -> None:
    rig.finish(split_review(SLICE_NAME))

    verdicts = rig.store.verdicts(PROJECT)
    assert len(verdicts) == 2
    assert len(rig.store.detections(PROJECT)) == 2
    done = rig.resolved()
    assert done.result is not None
    assert sorted(done.result[RESULT_VERDICT_IDS]) == sorted(v.id for v in verdicts)  # pyright: ignore[reportArgumentType]
    assert rig.open_blocks() == []


def test_an_empty_list_resolves_and_flags_the_entry(rig: Rig) -> None:
    rig.finish(empty_reviews())

    done = rig.resolved()
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.awaits_routing is True
    assert done.result is not None and done.result[RESULT_VERDICT_IDS] == []
    assert rig.store.verdicts(PROJECT) == []


def test_the_result_keeps_the_polled_document(rig: Rig) -> None:
    document = rig.finish(single_review(SLICE_NAME))

    done = rig.resolved()
    assert done.result is not None
    assert done.result[RESULT_OUTCOME_DOCUMENT] == document.model_dump(mode="json")


@pytest.mark.parametrize(
    ("script", "fragment"),
    [
        (null_path_review(), "neither path nor paths"),
        (missing_file_review(), "missing"),
        (single_review("a-slice-nobody-has"), "matches no single node"),
    ],
    ids=["null path", "missing file", "no such slice"],
)
def test_an_unknown_review_blocks_on_a_human_and_still_resolves(
    rig: Rig, script: RunScript, fragment: str
) -> None:
    rig.finish(script)

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    [payload] = rig.escalation_payloads()
    assert payload[PAYLOAD_FAULT_KIND] == FaultKind.REVIEW_UNKNOWN.value
    assert fragment in str(payload[PAYLOAD_REASON])
    assert PAYLOAD_PATH in payload
    done = rig.resolved()
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.awaits_routing is True
    assert done.result is not None
    assert fragment in str(done.result[RESULT_REVIEW_FAULT])
    assert done.result[RESULT_VERDICT_IDS] == []
    assert rig.store.verdicts(PROJECT) == []
    assert rig.store.detections(PROJECT) == []


def test_attribution_to_another_slice_is_unknown(rig: Rig) -> None:
    rig.add_slice("another-slice")

    rig.finish(single_review("another-slice"))

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    assert rig.store.verdicts(PROJECT) == []


def test_a_paused_run_with_a_good_review_blocks_on_the_checkpoint(rig: Rig) -> None:
    script = single_review(SLICE_NAME)
    paused = RunScript(
        script.files, {**script.document, "checkpoint": {"kind": "awaits_human"}}
    )

    rig.finish(paused, RunOutcome.PAUSED)

    assert rig.open_blocks() == [BlockedKind.SQ_CHECKPOINT]
    assert len(rig.store.verdicts(PROJECT)) == 1
    assert rig.resolved().outcome is JournalOutcome.COMPLETED


def test_a_paused_run_with_an_unknown_review_blocks_on_a_human_instead(
    rig: Rig,
) -> None:
    rig.finish(missing_file_review(), RunOutcome.PAUSED)

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    assert len(rig.escalation_payloads()) == 1, "a checkpoint block posts no message"
    done = rig.resolved()
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.awaits_routing is True


def test_a_failed_run_with_an_unknown_review_keeps_its_block_and_adds_the_fault(
    rig: Rig,
) -> None:
    script = RunScript(
        {}, {**missing_file_review().document, "failure": {"kind": "cost_cap"}}
    )

    rig.finish(script, RunOutcome.FAILED)

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    [payload] = rig.escalation_payloads()
    assert payload[PAYLOAD_REASON] == REASON_FAILED
    assert "missing" in str(payload[PAYLOAD_REVIEW_FAULT])


def test_a_missing_checkout_makes_a_listed_review_unknown(rig: Rig) -> None:
    entry = rig.store.journal_issue(
        rig.step.id,
        kind=CommandKind.SQ_RUN,
        parameters={PARAM_PIPELINE: "p5", PARAM_PARAMS: {}, PARAM_RUN_ID: "run-2"},
    )
    rig.entry = entry

    rig.finish(single_review(SLICE_NAME))

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    [payload] = rig.escalation_payloads()
    assert "no checkout" in str(payload[PAYLOAD_REASON])


def test_a_step_with_no_slice_parent_makes_a_listed_review_unknown(
    rig: Rig,
) -> None:
    orphan = rig.store.create_node(
        project_id=PROJECT, kind=NodeKind.PHASE_OR_ARTIFACT, title="orphan step"
    )
    rig.step = orphan
    rig.entry = rig.journal(orphan)

    rig.finish(single_review(SLICE_NAME))

    assert rig.open_blocks() == [BlockedKind.HUMAN]
    [payload] = rig.escalation_payloads()
    assert "has no slice" in str(payload[PAYLOAD_REASON])


def test_recording_again_after_a_crash_gives_one_block_and_one_verdict_per_part(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    split = split_review(SLICE_NAME)
    script = RunScript(split.files, {**split.document, "failure": {"kind": "cost_cap"}})
    original = Store.record_runner_report
    crash = {"armed": True}

    def crash_once(self: Store, *args: object, **kwargs: object) -> object:
        if crash["armed"]:
            crash["armed"] = False
            raise StoreError("killed between the block and the report")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Store, "record_runner_report", crash_once)

    with pytest.raises(StoreError):
        rig.finish(script, RunOutcome.FAILED)
    assert rig.open_blocks() == [BlockedKind.HUMAN]
    assert not rig.resolved().is_resolved

    rig.finish(script, RunOutcome.FAILED)

    assert rig.open_blocks() == [BlockedKind.HUMAN], "one block, not two"
    assert len(rig.store.verdicts(PROJECT)) == 2, "one verdict per part"
    assert len(rig.store.detections(PROJECT)) == 2
    assert rig.resolved().is_resolved
