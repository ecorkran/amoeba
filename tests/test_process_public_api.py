"""Regression test pinning the public export surface of ``amoeba.process``.

A tenant author imports only ``amoeba.process``, so a dropped or accidentally
added export should fail here, not in initiative 120.
"""

from __future__ import annotations

import amoeba.process as process_package

#: The hosting contract, written out rather than derived from ``__all__``:
#: deriving it from the thing under test would make the assertion vacuous.
EXPECTED_EXPORTS = {
    "ResidentProcess",
    "Tenant",
    "ProcessSettings",
    "Observer",
    "Observation",
    "Adopt",
    "InFlight",
    "NotApplied",
    "Unknown",
    "standard_tenants",
    "ProcessError",
    "AlreadyRunningError",
    "StartupFailedError",
    "GraceExpiredError",
    # Slice 120: the outcome reader, consumed by the Runner in 122 and 125.
    "RunOutcome",
    "OUTCOME_EXIT_CODES",
    "RunCheckpoint",
    "RunOutcomeDocument",
    "PollFailure",
    "RunPoll",
    "poll_run",
    "SQ_EXECUTABLE",
    "SQ_USAGE_ERROR_EXIT_CODE",
    # Slice 122: raised by the Runner's probes, mapped to an exit code by the CLI.
    "UpstreamShapeError",
    # Slice 125: the one place detection's ledger key is formed, called by ingest.
    "detection_key",
    "ledger_key",
    "capture_sq_version_label",
    # Slice 125: the one CF read-back, and the keys its adoption records.
    "read_back_answer",
    "ReadBackAnswer",
    "ReadFailed",
    "CFRun",
    "CF_FIELD_FILE_SLICE",
    "RESULT_FILE_SLICE",
    "RESULT_PROJECT_PATH",
    "RESULT_UPDATED_AT",
    "RESULT_WORKTREE_ID",
    # Slice 125: the outcome document's checkpoint, failure and reviews.
    "RunFailure",
    "RunReview",
    "CheckpointKind",
    "FailureKind",
    "UnknownKind",
    "parse_checkpoint_kind",
    "parse_failure_kind",
}

#: Deliberately not part of the contract: run-file parsing and pruning are
#: internal to the shipped tenants and the CLI.
NOT_EXPORTED = {"SquadronRun", "parse_run_file"}


def test_declared_exports_match_the_expected_surface() -> None:
    """``__all__`` is exactly the contract — nothing added, nothing dropped."""
    assert set(process_package.__all__) == EXPECTED_EXPORTS


def test_every_declared_export_is_importable() -> None:
    """Every name in ``__all__`` actually resolves on the package."""
    missing = [
        name for name in process_package.__all__ if not hasattr(process_package, name)
    ]

    assert missing == []


def test_run_file_parsing_and_pruning_are_not_exported() -> None:
    exported = set(process_package.__all__)

    assert exported & NOT_EXPORTED == set()
    assert not [name for name in exported if "prune" in name.lower()]
