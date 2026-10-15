"""Slice 106 end to end, through the real CLI as subprocesses.

Test A: a follower started while the process is stopped sees the seed, a human
reply, and two detected review rounds — and nothing for the baseline file.
Test B: ``kill -9`` mid-life records nothing twice, and the captured provider
failure lands with its standing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
from detection_e2e_harness import FAKE_SQ_LABEL, ChangeLine, DetectionE2E, copy_fixture

PROJECT = "demo"
ROUND_ONE_PART_ONE = (
    "102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md"
)
ROUND_ONE_PART_TWO = (
    "102-review.tasks.resident-process-and-recovery.part-2.20260921T112635.md"
)
ROUND_TWO_PART_ONE = "102-review.tasks.resident-process-and-recovery.part-1.md"
PROVIDER_FAILURE = "102-review.tasks.resident-process-and-recovery.part-2.md"


@pytest.fixture
def e2e(supervisor_dir: Path, tmp_path: Path) -> Iterator[DetectionE2E]:
    harness = DetectionE2E(supervisor_dir, tmp_path)
    yield harness
    harness.cleanup()


@pytest.fixture
def reviews_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "reviews"
    directory.mkdir()
    return directory


def _of_kind(lines: list[ChangeLine], kind: str) -> list[ChangeLine]:
    return [line for line in lines if line["kind"] == kind]


def _detected(count: int) -> Callable[[list[ChangeLine]], bool]:
    def enough(lines: list[ChangeLine]) -> bool:
        return len(_of_kind(lines, "review_detected")) >= count

    return enough


def _payload(line: ChangeLine) -> dict[str, object]:
    payload = line["payload"]
    assert isinstance(payload, dict)
    # Decoded JSON: an object's keys are strings.
    return cast(dict[str, object], payload)


def _seeded_and_stopped(e2e: DetectionE2E) -> tuple[str, str]:
    process = e2e.start_process()
    e2e.create_project(PROJECT)
    e2e.stop_process(process)
    return e2e.seed_demo()


def _register(e2e: DetectionE2E, directory: Path) -> None:
    result = e2e.run(
        "submit", "watch-reviews", "--project", PROJECT, "--by", "pm",
        "--reviews-dir", str(directory), "--active", "true",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    e2e.await_rows("watches", PROJECT, lambda rows: rows[0]["state"] == "ok")


def _assert_subjects_agree(e2e: DetectionE2E, lines: list[ChangeLine]) -> None:
    """Every feed subject is in the store, and every store row is on the feed."""
    verdict_ids = {row["id"] for row in e2e.inspect_json("verdicts", PROJECT)}
    assert {line["subject_id"] for line in _of_kind(lines, "verdict_recorded")} == (
        verdict_ids
    )
    detections = e2e.inspect_json("detections", PROJECT)
    loud = [row for row in detections if row["outcome"] != "baseline"]
    assert len(_of_kind(lines, "review_detected")) == len(loud)


def test_a_follow_reply_and_detect(e2e: DetectionE2E, reviews_dir: Path) -> None:
    slice_node, blocked_node = _seeded_and_stopped(e2e)
    follower = e2e.start_follower(PROJECT)
    follower.wait_for(lambda lines: len(_of_kind(lines, "node_created")) == 2)

    e2e.start_process()
    [escalation] = e2e.inspect_json("messages", PROJECT, "--channel", "escalation")
    result = e2e.run(
        "submit", "resolution", "--project", PROJECT, "--by", "pm",
        "--blocked-state-id", str(escalation["blocked_state_id"]), "--detail", "go",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    follower.wait_for(
        lambda lines: any(
            line["payload"] == {"from": "blocked_on_human", "to": "runnable"}
            for line in _of_kind(lines, "node_status_changed")
        )
    )

    baseline_file = copy_fixture(ROUND_ONE_PART_TWO, reviews_dir)
    _register(e2e, reviews_dir)
    copy_fixture(ROUND_ONE_PART_ONE, reviews_dir)
    follower.wait_for(_detected(1))
    copy_fixture(ROUND_TWO_PART_ONE, reviews_dir)
    lines = follower.wait_for(_detected(2))

    kinds = [line["kind"] for line in lines]
    assert kinds[:3] == ["node_created", "node_created", "node_status_changed"]
    assert lines[2]["node_id"] == blocked_node
    reply = next(
        i for i, line in enumerate(lines)
        if line["kind"] == "node_status_changed"
        and line["payload"] == {"from": "blocked_on_human", "to": "runnable"}
    )  # fmt: skip
    assert kinds[reply + 1 :] == ["verdict_recorded", "review_detected"] * 2
    detected_paths = [
        _payload(line)["path"] for line in _of_kind(lines, "review_detected")
    ]
    assert str(baseline_file) not in detected_paths

    verdicts = e2e.inspect_json("verdicts", PROJECT)
    assert [(v["node_id"], v["source"], v["upstream_version"]) for v in verdicts] == [
        (slice_node, "artifact_frontmatter", FAKE_SQ_LABEL)
    ] * 2
    assert [v["source_path"] for v in verdicts] == [
        str(reviews_dir / ROUND_ONE_PART_ONE),
        str(reviews_dir / ROUND_TWO_PART_ONE),
    ]
    _assert_subjects_agree(e2e, lines)
