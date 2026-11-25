"""The door under load with machine work seeded on both machines (262 D16).

The store holds 500 questions, half on each machine, and 500 open requests to members
with a wakeable checkout on each machine, so every call's work flag reads a full store.
Sixteen clients, two of them ``claim_work`` callers, hold 260's bound (every call inside
``MAX_CALL_SECONDS``). On the idle hub each of the sixteen steps is timed once, each
request built from a seeded row of the kind it needs, and the median holds 260's idle
bound. A step that consumes its row is timed after the steps that read it.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections.abc import Callable
from pathlib import Path

from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub
from store.decision_support import CORE, LINT, at, automatic_answer, seed_programs
from store.question_support import (
    ANSWERING_RUN,
    claimed_question,
    insert_held_row,
    waiting_question,
)
from store.seed import insert_checkout, mark_wake_wanted

from amoeba.client.call import call
from amoeba.client.client_file import ClientFile, load_client_file
from amoeba.hub.store_open import open_hub_store
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.wakes import WakeLimits, claim_wake
from amoeba.wire.protocol import STEP_CALLS
from amoeba.wire.times import DOOR_VERSION, DoorTimes
from load.door_load_support import (
    CALLER_HERE,
    MAX_CALL_SECONDS,
    MEDIAN_CALL_SECONDS,
    START_SPREAD_SECONDS,
    THINK_SECONDS,
)

SEEDED_QUESTIONS = 500
SEEDED_REQUESTS = 500
ROUNDS = 10
CLAIMERS = 2
LOGS = "/machine/logs"
COMMAND = "wake-agent --max-seconds 60"
CLAIMED = QuestionKey("load-claimed", "2026-11-10T08:00:00+00:00")
SETTLE = QuestionKey("load-settle", "2026-11-10T08:01:00+00:00")
HELD = QuestionKey("load-held", "2026-11-10T08:02:00+00:00")
ANSWERED = QuestionKey("load-answered", "2026-11-10T08:03:00+00:00")
WAKE_ID = "load-wake"
SEEDED_AT = at(0)


def _key(machine: str, number: int) -> QuestionKey:
    return QuestionKey(
        f"{machine}-run-{number}", f"2026-11-10T07:{number % 60:02d}:00Z"
    )


def _seed_machine(store: Store, machine: str, member: str) -> None:
    """Half the questions and requests, on the machine ``store`` acts as."""
    with store.write() as transaction:
        if machine == SECOND:
            insert_checkout(
                transaction,
                member_id=member,
                cf_project_id=member,
                path=f"/{machine}/{member}",
                wake_command=COMMAND,
                now=SEEDED_AT,
            )
        else:
            transaction.execute(
                "UPDATE checkouts SET wake_command = ? WHERE member_id = ?",
                (COMMAND, member),
            )
        for number in range(SEEDED_QUESTIONS // 2):
            insert_question(
                transaction,
                waiting_question(_key(machine, number), member_id=CORE),
                now=SEEDED_AT,
            )
        for _ in range(SEEDED_REQUESTS // 2):
            mark_wake_wanted(transaction, member, SEEDED_AT)


def _seed_step_rows(store: Store) -> None:
    """On the first machine: a row for each step that needs one."""
    with store.write() as transaction:
        insert_question(
            transaction, claimed_question(CLAIMED, member_id=CORE), now=SEEDED_AT
        )
        insert_question(
            transaction, claimed_question(SETTLE, member_id=CORE), now=SEEDED_AT
        )
        insert_held_row(transaction, HELD, member_id=CORE, now=SEEDED_AT)
        claimed = claim_wake(
            transaction,
            LINT,
            SEEDED_AT,
            WakeLimits(
                timeout_seconds=600,
                max_per_day=50,
                session_stale_seconds=90,
                door_version=DOOR_VERSION,
            ),
            WAKE_ID,
            f"{LOGS}/wake/{WAKE_ID}",
        )
        assert claimed is not None
    automatic_answer(store, ANSWERED, CORE, 1)


def _seed(hub: FixtureHub) -> None:
    hub.seed(seed_programs)
    hub.seed(lambda store: _seed_machine(store, FIRST, LINT), FIRST)
    hub.seed(lambda store: _seed_machine(store, SECOND, CORE), SECOND)
    hub.seed(_seed_step_rows, FIRST)


def _client(hub: FixtureHub, name: str) -> tuple[ClientFile, Path]:
    home = hub.clients[name].home
    cert = home / "pinned-hub-cert.pem"
    return load_client_file(home / "client.yaml", cert), cert


def _timed(
    client: ClientFile, cert: Path, name: str, document: object, think: float = 0
) -> tuple[float, dict[str, object]]:
    began = time.monotonic()
    result = call(client, cert, name, document, DoorTimes(), extra=CALLER_HERE)
    took = time.monotonic() - began
    time.sleep(think)
    return took, result


def test_sixteen_clients_with_claim_work_callers_each_within_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        _seed(hub)
        hub.start()
        seconds: list[float] = []
        errors: list[BaseException] = []

        def caller(name: str, call_name: str, document: object) -> Callable[[], None]:
            def run() -> None:
                try:
                    client, cert = _client(hub, name)
                    for _ in range(ROUNDS):
                        took, result = _timed(
                            client, cert, call_name, document, THINK_SECONDS
                        )
                        assert "work" in result or "work_problem" in result, result
                        seconds.append(took)
                except BaseException as error:  # noqa: BLE001 - to the test thread
                    errors.append(error)

            return run

        bodies = (
            [caller(FIRST if n % 2 else SECOND, "decisions", {}) for n in range(5)]
            + [caller(FIRST if n % 2 else SECOND, "inbox", {}) for n in range(5)]
            + [caller(FIRST, "open_runs", {}) for _ in range(4)]
            + [
                caller(FIRST if n % 2 else SECOND, "claim_work", {"logs_dir": LOGS})
                for n in range(CLAIMERS)
            ]
        )
        assert len(bodies) == 16
        threads = [threading.Thread(target=body) for body in bodies]
        for thread in threads:
            thread.start()
            time.sleep(START_SPREAD_SECONDS)
        for thread in threads:
            thread.join(120)

        assert not errors, errors
        slowest = max(seconds)
        print(
            f"LOAD 262: {len(seconds)} calls, slowest {slowest:.3f}s, "
            f"median {statistics.median(seconds):.3f}s"
        )
        assert slowest < MAX_CALL_SECONDS


def _step_documents() -> list[tuple[str, object]]:
    """Every step once, each on a seeded row; the steps that consume a row after the
    ones that read it."""
    passages: list[object] = []
    evidence = {"verdict": "yes", "reason": "cited"}
    return [
        (
            "pause_begin",
            {
                "run_id": "load-new",
                "here": None,
                "outcome": "completed",
                "paused": False,
                "checkpoint_kind": None,
                "paused_at": None,
                "question": None,
                "fate": None,
            },
        ),
        ("pause_sources", {"member_id": CORE}),
        ("open_runs", {}),
        (
            "session_tick",
            {
                "here": {"project_id": LINT},
                "session_id": "a" * 32,
                "client": "claude-code",
                "directory": "/alpha",
                "client_version": "1.2.3",
                "last_seen": None,
                "push_confirmed": False,
            },
        ),
        ("session_end", {"session_id": "a" * 32}),
        ("wake_read", {"wake_id": WAKE_ID}),
        (
            "question_insert",
            {
                "run_id": "load-insert",
                "paused_at": "2026-11-10T08:04:00+00:00",
                "member_id": CORE,
                "question": "q",
                "checkout": "/alpha/core",
                "slice_label": None,
                "source_commit": None,
                "passages": None,
                "answering_run_id": "load-insert-run",
                "waiting_reason": None,
                "waiting_detail": None,
            },
        ),
        (
            "question_hold",
            {
                "run_id": "load-hold",
                "paused_at": "2026-11-10T08:05:00+00:00",
                "member_id": CORE,
                "question": "q",
                "checkout": "/alpha/core",
                "request_id": "no-such-request",
            },
        ),
        (
            "question_claim_held",
            {
                "run_id": HELD.run_id,
                "paused_at": HELD.paused_at,
                "answering_run_id": "load-held-run",
                "passages": passages,
                "slice_label": "none",
                "source_commit": "abc123",
            },
        ),
        (
            "question_replace_claim",
            {
                "run_id": CLAIMED.run_id,
                "paused_at": CLAIMED.paused_at,
                "old_answering_run_id": ANSWERING_RUN,
                "new_answering_run_id": "load-replaced",
                "passages": passages,
            },
        ),
        (
            "question_wait",
            {
                "run_id": CLAIMED.run_id,
                "paused_at": CLAIMED.paused_at,
                "answering_run_id": "load-replaced",
                "reason": "answer_limit_reached",
                "detail": "load",
                "evidence": None,
            },
        ),
        (
            "question_settle",
            {
                "run_id": SETTLE.run_id,
                "paused_at": SETTLE.paused_at,
                "answering_run_id": ANSWERING_RUN,
                "answer": "an answer",
                "cited": [],
                "evidence": evidence,
            },
        ),
        ("wake_set_pid", {"wake_id": WAKE_ID, "pid": 4242}),
        (
            "wake_finish",
            {"wake_id": WAKE_ID, "outcome": "exited", "exit_code": 0, "detail": None},
        ),
    ]


def test_each_step_once_on_the_idle_hub_has_a_median_under_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        _seed(hub)
        hub.start()
        client, cert = _client(hub, FIRST)
        timings: dict[str, float] = {}

        for name, document in _step_documents():
            timings[name], _ = _timed(client, cert, name, document)
        answer_seq = _answer_seq(hub)
        took, claimed = _timed(client, cert, "resume_claim", {"answer_seq": answer_seq})
        timings["resume_claim"] = took
        claim = claimed["claim"]
        assert isinstance(claim, dict), claimed
        claim_id = str(claim["claim_id"])  # pyright: ignore[reportUnknownArgumentType]
        timings["resume_read"], _ = _timed(
            client,
            cert,
            "resume_read",
            {"answer_seq": answer_seq, "claim_id": claim_id},
        )
        timings["resume_record"], _ = _timed(
            client,
            cert,
            "resume_record",
            {
                "answer_seq": answer_seq,
                "claim_id": claim_id,
                "outcome": "resumed",
                "detail": None,
                "log": None,
            },
        )

        # Last: it would take the resume claim the three resume steps above use.
        timings["claim_work"], _ = _timed(
            client, cert, "claim_work", {"logs_dir": LOGS}
        )

        assert set(timings) == set(STEP_CALLS)
        median = statistics.median(timings.values())
        shown = ", ".join(f"{n} {t * 1000:.0f}" for n, t in sorted(timings.items()))
        print(f"LOAD 262 steps (ms): {shown}; median {median * 1000:.1f} ms")
        assert median < MEDIAN_CALL_SECONDS
        assert max(timings.values()) < MAX_CALL_SECONDS


def _answer_seq(hub: FixtureHub) -> int:
    with open_hub_store(hub.layout) as store, store.read() as transaction:
        row = transaction.execute(
            "SELECT seq FROM answers WHERE run_id = ?", (ANSWERED.run_id,)
        ).fetchone()
    assert row is not None
    return int(row[0])
