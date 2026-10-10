"""Slice 105 end to end: ingest real review files into a running process.

From an empty supervisor directory: create the project, seed a node, start, ingest
round 1, round 2, a provider failure, and round 1 again from a different path (a
hand-annotated copy), kill -9, and start again. The module-scoped run feeds both
the standing test and the record-content test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from cli_harness import (
    await_condition,
    await_stopped,
    start_running,
    stop_running,
)
from review_fixtures import ROUND_1_PART_1, ROUND_2_PART_1, ROUND_2_PART_2

from amoeba.inbox import pending
from amoeba.upstream.squadron import parse_review_artifact, review_record_id
from cli.ingest_e2e_harness import (
    PRE_STAMP_LABEL,
    applied,
    ingest_ok,
    inspect_rows,
    start_with_node,
)


@dataclass(frozen=True)
class Run:
    supervisor_dir: Path
    node: str
    round_1_id: str
    round_2_id: str
    failure_id: str
    repeat_id: str
    annotated_copy: Path


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    root = tmp_path_factory.mktemp("ingest-e2e")
    supervisor_dir = root / "supervisor"
    supervisor_dir.mkdir()
    runs_dir = root / "runs"
    runs_dir.mkdir()
    process, node = start_with_node(supervisor_dir, runs_dir)

    round_1_id = ingest_ok(supervisor_dir, node, ROUND_1_PART_1)
    round_2_id = ingest_ok(supervisor_dir, node, ROUND_2_PART_1)
    failure_id = ingest_ok(supervisor_dir, node, ROUND_2_PART_2)
    annotated = root / "annotated-round-1.md"
    text = ROUND_1_PART_1.read_text(encoding="utf-8")
    annotated.write_text(
        text.replace("findings:\n", "resolution: fixed\nfindings:\n", 1)
        + "\n## Response\n\nAddressed.\n",
        encoding="utf-8",
    )
    repeat_id = ingest_ok(supervisor_dir, node, annotated)
    await_condition(
        lambda: (
            applied(supervisor_dir, round_1_id, round_2_id, failure_id)
            and pending(supervisor_dir) == []
        ),
        "the four ingests to drain",
    )

    process.kill_and_wait()
    process.cleanup()
    await_stopped(supervisor_dir)
    process = start_running(supervisor_dir, runs_dir)
    stop_running(supervisor_dir, process)
    return Run(
        supervisor_dir, node, round_1_id, round_2_id, failure_id, repeat_id, annotated
    )


def test_three_verdicts_with_the_expected_standings_survive_a_crash(run: Run) -> None:
    verdicts = inspect_rows(run.supervisor_dir, "verdicts")
    assert [(v["id"], v["standing"]) for v in verdicts] == [
        (run.round_1_id, "stated"),
        (run.round_2_id, "stated"),
        (run.failure_id, "provider_failure"),
    ]
    assert pending(run.supervisor_dir) == []


def test_ids_are_digests_and_the_repeat_is_a_noop_replay(run: Run) -> None:
    for path, stored in (
        (ROUND_1_PART_1, run.round_1_id),
        (ROUND_2_PART_1, run.round_2_id),
        (ROUND_2_PART_2, run.failure_id),
    ):
        parsed = parse_review_artifact(path.read_text(encoding="utf-8"))
        assert stored == review_record_id(parsed)
    assert run.repeat_id == run.round_1_id
    submissions = inspect_rows(run.supervisor_dir, "submissions")
    assert [row["id"] for row in submissions if row["id"] == run.round_1_id] == [
        run.round_1_id
    ]
    assert len(inspect_rows(run.supervisor_dir, "verdicts")) == 3


def test_round_1_keeps_its_first_path_and_artifact_source(run: Run) -> None:
    first = next(
        v
        for v in inspect_rows(run.supervisor_dir, "verdicts")
        if v["id"] == run.round_1_id
    )
    assert first["source_path"] == str(ROUND_1_PART_1.resolve())
    assert first["source"] == "artifact_frontmatter"
    assert first["upstream_version"] == PRE_STAMP_LABEL
    assert first["source_path"] != str(run.annotated_copy.resolve())


def test_round_2_names_round_1_as_previous_with_every_finding_gone(run: Run) -> None:
    changes = inspect_rows(run.supervisor_dir, "changes", "--verdict", run.round_2_id)
    assert {row["previous_verdict_id"] for row in changes} == {run.round_1_id}
    gone = [row for row in changes if row["change"] == "gone"]
    round_1 = parse_review_artifact(ROUND_1_PART_1.read_text(encoding="utf-8"))
    assert len(gone) == len(round_1.findings) == 9
    assert {row["summary"] for row in gone} == {f.summary for f in round_1.findings}
    assert not [row for row in changes if row["change"] == "recurring"]
