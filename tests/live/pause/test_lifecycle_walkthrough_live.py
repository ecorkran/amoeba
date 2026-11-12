"""The slice 228 verification walkthrough, steps 4 to 8, with real ``sq``, ``cf`` and
models (slice 228, task 13.3).

A throwaway member (its own Context Forge data directory and ``AMOEBA_HOME``) runs real
pipelines that pause on a question, and the real ``amoeba`` commands act on them. A
stub ``amoeba`` that does nothing is first on ``PATH``, so the pause hook (configured
user-level) never handles a pause behind the test's back: every ``handle_pause`` call
is the test's own, by absolute path. A wrong result fails the test; nothing is retried.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml
from git_repo import git
from live_harness import POLL_INTERVAL_SECONDS, watch_run
from live_settings import LiveSettings

from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    poll_run,
)
from live.pause.harness import (
    PIPELINE_MODEL_PARAM,
    PauseWorld,
    result_of,
    run_amoeba,
    start_pause,
    store_rows,
)

UNSETTLED_PIPELINE: Final = Path(__file__).parent / "asks_unsettled_question.yaml"
POLL_CALL_TIMEOUT_SECONDS: Final = 30.0
NEXT_PAUSE_SECONDS: Final = 300.0
RESUME_TIMEOUT_SECONDS: Final = 600.0
SETTLED_QUESTION: Final = (
    "What is the maximum length of a source file in this repository?"
)
OLD_STAMP: Final = (datetime(2026, 1, 1, tzinfo=UTC)).timestamp()


def _world(world: PauseWorld) -> PauseWorld:
    """``world`` with a do-nothing ``amoeba`` first on ``PATH`` (the hook's command)."""
    stub_dir = world.repo.parent / "hook-stub"
    stub_dir.mkdir()
    stub = stub_dir / "amoeba"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    path = str(stub_dir) + os.pathsep + world.environ["PATH"]
    return replace(world, environ={**world.environ, "PATH": path})


def _amoeba(
    world: PauseWorld, *arguments: str, cwd: Path | None = None, expect: int = 0
) -> dict[str, Any]:
    completed = run_amoeba(world, *arguments, cwd=cwd)
    assert completed.returncode == expect, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def _pause_at(run_id: str) -> str:
    poll = poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)
    assert isinstance(poll, RunOutcomeDocument), poll
    assert poll.outcome is RunOutcome.PAUSED, poll
    assert poll.checkpoint is not None
    assert poll.checkpoint.paused_at_text is not None
    return poll.checkpoint.paused_at_text


def _next_pause(run_id: str, after: str) -> str:
    """Wait for the run to pause at a pause other than ``after``."""
    deadline = time.monotonic() + NEXT_PAUSE_SECONDS
    while time.monotonic() < deadline:
        poll = poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)
        assert not isinstance(poll, PollFailure), poll
        if poll.outcome is RunOutcome.PAUSED and poll.checkpoint is not None:
            if poll.checkpoint.paused_at_text != after:
                assert poll.checkpoint.paused_at_text is not None
                return poll.checkpoint.paused_at_text
        assert poll.outcome in (RunOutcome.PAUSED, RunOutcome.TIMED_OUT), poll
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"run {run_id} did not pause again within {NEXT_PAUSE_SECONDS}s"
    )


def _new_run(world: PauseWorld, pipeline: Path = UNSETTLED_PIPELINE) -> tuple[str, str]:
    """Start a run that pauses without a hook; returns its id and its pause."""
    run_id = mint_run_id(datetime.now(UTC))
    started = start_pause(world, run_id, opt_out=True, pipeline=pipeline)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    return run_id, _pause_at(run_id)


def _precedent_passages(world: PauseWorld, run_id: str, pause: str) -> list[object]:
    """The claim's passages that are a PM answer (they carry a ``question_id``)."""
    rows = store_rows(
        world,
        "SELECT passages FROM questions WHERE run_id = ? AND paused_at = ?",
        (run_id, pause),
    )
    assert len(rows) == 1, rows
    passages: list[dict[str, Any]] = json.loads(str(rows[0][0])) if rows[0][0] else []
    return [item for item in passages if item.get("question_id") is not None]


def _questions(world: PauseWorld, run_id: str) -> list[tuple[object, ...]]:
    return store_rows(
        world,
        "SELECT paused_at, state, closed_reason, answering_run_id FROM questions "
        "WHERE run_id = ? ORDER BY claimed_at",
        (run_id,),
    )


def _member(status: dict[str, Any]) -> dict[str, Any]:
    (program,) = status["programs"]
    (member,) = program["members"]
    entry: dict[str, Any] = member
    return entry


def _run_entry(status: dict[str, Any], run_id: str) -> dict[str, Any]:
    (entry,) = [r for r in _member(status)["runs"] if r["run_id"] == run_id]
    found: dict[str, Any] = entry
    return found


def _set_config(world: PauseWorld, **changes: object) -> None:
    path = world.amoeba_home / "config.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document.update(changes)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")


def _several_questions(directory: Path, name: str, steps: int) -> Path:
    """A pipeline of ``steps`` steps, each ending on the file-length question."""
    document = {
        "name": name,
        "description": "Stop on the same question several times",
        "params": {PIPELINE_MODEL_PARAM: "required"},
        "steps": [
            {
                "dispatch": {
                    "name": f"ask{number}",
                    "model": "{" + PIPELINE_MODEL_PARAM + "}",
                    "artifact": "design",
                    "prompt": (
                        "Do not edit any file and do not run any command. Reply "
                        "with exactly the text between the markers and no other "
                        "words. If you are later given an answer to it, reply "
                        "with exactly the same text again, because the next step "
                        f"needs it.\n<<<\n{SETTLED_QUESTION}\n>>>"
                    ),
                }
            }
            for number in range(1, steps + 1)
        ],
    }
    path = directory / f"{name}.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_step_4_an_earlier_pause_closes_as_the_run_moves_on(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    world = _world(pause_world)
    run_id, first_pause = _new_run(world)
    waiting = _amoeba(world, "handle_pause", run_id)
    assert waiting["outcome"] == "waiting_on_pm", waiting

    # Resume it outside Amoeba, with the pause hook off so the next call is by hand.
    argv = ["sq", "run", "--resume", run_id, "--instructions", "Use teal."]
    resumed = watch_run(
        [*argv, "--no-pause-hook"],
        run_id,
        world.repo,
        RESUME_TIMEOUT_SECONDS,
        30.0,
        world.environ,
    )
    assert isinstance(resumed.poll, RunOutcomeDocument), resumed.sq_output
    handled = _amoeba(world, "handle_pause", run_id)
    first = [row for row in _questions(world, run_id) if row[0] == first_pause]

    # Whether the run then pauses again or finishes is up to the model; the first
    # pause's row closes either way, which is all this step claims.
    assert [row[:3] for row in first] == [(first_pause, "closed", "run_moved_on")], (
        first,
        resumed.poll,
        handled,
    )
    again = _amoeba(world, "status")
    assert again["outcome"] == "listed"


def test_step_5_dismiss_then_the_hook_skips_it_and_status_shows_closed(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    world = _world(pause_world)
    run_id, _pause = _new_run(world)
    assert _amoeba(world, "handle_pause", run_id)["outcome"] == "waiting_on_pm"

    dismissed = _amoeba(world, "dismiss", run_id, "--reason", "not needed tonight")
    assert dismissed["outcome"] == "dismissed", dismissed
    assert dismissed["closed_reason"] == "dismissed"
    assert _amoeba(world, "dismiss", run_id, "--reason", "again")["outcome"] == (
        "unchanged"
    )
    skipped = _amoeba(world, "handle_pause", run_id)
    assert (skipped["outcome"], skipped["skip_reason"]) == ("skipped", "closed")
    status = _amoeba(world, "status")
    entry = _run_entry(status, run_id)
    assert entry["pause"] == "closed", entry
    assert entry["next"] is None
    assert "still paused" in entry["detail"], entry
    assert [w for w in _member(status)["waiting_on_pm"] if w["run_id"] == run_id] == []


def test_step_6_a_pm_answer_resets_the_limit_and_a_retraction_ends_precedent(
    pause_world: PauseWorld, live_settings: LiveSettings, tmp_path: Path
) -> None:
    del live_settings
    world = _world(pause_world)
    _set_config(world, answer_limit=1)
    pipeline = _several_questions(tmp_path, "asks-four", 4)
    run_id, pause = _new_run(world, pipeline)

    first = _amoeba(world, "handle_pause", run_id)
    assert first["outcome"] == "resumed", first  # an automatic answer: 1 of 1
    pause = _next_pause(run_id, pause)
    limited = _amoeba(world, "handle_pause", run_id)
    assert (limited["outcome"], limited["waiting_reason"]) == (
        "waiting_on_pm",
        "answer_limit_reached",
    ), limited
    answered = _amoeba(world, "answer", run_id, "--text", "About 300 lines.")
    assert answered["resume"]["outcome"] == "resumed", answered
    pause = _next_pause(run_id, pause)
    after_reset = _amoeba(world, "handle_pause", run_id)
    assert after_reset["outcome"] == "resumed", after_reset  # the limit was reset
    assert _precedent_passages(world, run_id, pause), "the PM answer was not precedent"

    records = _amoeba(world, "decisions")["records"]
    (pm_record,) = [r for r in records if r["answered_by"] == "pm"]
    retracted = _amoeba(
        world, "retract", str(pm_record["seq"]), "--reason", "wrong number"
    )
    assert retracted["outcome"] == "retracted", retracted
    shown = _amoeba(world, "decisions", "--since", "2026-01-01T00:00:00+00:00")
    (listed,) = [r for r in shown["records"] if r["seq"] == pm_record["seq"]]
    assert listed["retracted_at"] is not None and listed["retract_reason"] == (
        "wrong number"
    )

    pause = _next_pause(run_id, pause)
    _amoeba(world, "handle_pause", run_id)
    assert _precedent_passages(world, run_id, pause) == []


def test_step_7_a_call_from_a_second_worktree_is_a_wrong_checkout(
    pause_world: PauseWorld, live_settings: LiveSettings, tmp_path: Path
) -> None:
    del live_settings
    world = _world(pause_world)
    run_id, _pause = _new_run(world)
    second = tmp_path / "second-worktree"
    git(world.repo, "worktree", "add", "-q", str(second), "-b", "second")

    skipped = _amoeba(world, "handle_pause", run_id, cwd=second)

    assert (skipped["outcome"], skipped["skip_reason"]) == (
        "skipped",
        "wrong_checkout",
    ), skipped
    assert (
        str(second.resolve()) in skipped["detail"] or str(second) in skipped["detail"]
    )
    assert (
        str(world.repo.resolve()) in skipped["detail"]
        or str(world.repo) in (skipped["detail"])
    )
    assert _questions(world, run_id) == []
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    last = (world.amoeba_home / "logs" / "calls" / f"{day}.jsonl").read_text("utf-8")
    line = json.loads(last.splitlines()[-1])
    assert (line["run_id"], line["outcome"], line["reason"]) == (
        run_id,
        "skipped",
        "wrong_checkout",
    )


def _age(path: Path) -> None:
    os.utime(path, (OLD_STAMP, OLD_STAMP))
    for child in path.rglob("*"):
        os.utime(child, (OLD_STAMP, OLD_STAMP))


def test_step_8_removal_is_blocked_by_an_open_question_and_pruning_keeps_it(
    pause_world: PauseWorld, live_settings: LiveSettings
) -> None:
    del live_settings
    world = _world(pause_world)
    settled_run, _ = _new_run(world)
    assert _amoeba(world, "handle_pause", settled_run)["outcome"] == "waiting_on_pm"
    _amoeba(world, "dismiss", settled_run, "--reason", "done with it")
    open_run, _ = _new_run(world)
    assert _amoeba(world, "handle_pause", open_run)["outcome"] == "waiting_on_pm"
    answering = world.amoeba_home / "answering"
    settled_dir = answering / str(_questions(world, settled_run)[0][3])
    open_dir = answering / str(_questions(world, open_run)[0][3])
    orphan_dir = answering / "orphan-run"
    orphan_dir.mkdir()
    (orphan_dir / "input.json").write_text("{}", encoding="utf-8")
    for directory in (settled_dir, open_dir, orphan_dir):
        assert directory.is_dir(), directory
        _age(directory)

    _set_config(world, prune_after_days=1)
    _amoeba(world, "status")

    assert not settled_dir.exists()
    assert not orphan_dir.exists()
    assert open_dir.is_dir()

    request = world.repo.parent / "remove.yaml"
    member = str(store_rows(world, "SELECT project_id FROM members")[0][0])
    request.write_text(
        yaml.safe_dump({"program": "live-pause", "remove": {"members": [member]}}),
        encoding="utf-8",
    )
    blocked = _amoeba(world, "set_up", "--file", str(request), expect=1)
    assert [p["code"] for p in blocked["problems"]] == ["member_has_open_questions"]
    _amoeba(world, "dismiss", open_run, "--reason", "no longer needed")
    applied = _amoeba(world, "set_up", "--file", str(request))
    assert applied["outcome"] == "applied", applied
    assert _amoeba(world, "set_up", "--file", str(request))["outcome"] == "unchanged"
