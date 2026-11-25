"""The door under load: 16 clients against a real hub (slice 260, D18).

Five threads read ``decisions`` over 500 seeded answers, five write (``standing``,
``withdraw``, ``mark_read``), three ``send`` requests and three read ``inbox`` (slice
261: the caller's ``here`` travels with each). No call may be refused or unknown and
every one must finish within ``MAX_CALL_SECONDS``. A second case makes 100 calls from
one thread against the idle hub and holds the median under ``MEDIAN_CALL_SECONDS``,
for ``decisions``, ``inbox`` and ``send`` each.
"""

from __future__ import annotations

import statistics
import threading
import time
from pathlib import Path

from hub_fixture import FIRST, two_machine_hub
from hub_mcp import set_hub_timings
from store.decision_support import LINT, NAMES, seed_programs

from amoeba.store.store import Store
from load.door_load_support import (
    LOAD_TIMINGS,
    MAX_CALL_SECONDS,
    MAX_GAP_SECONDS,
    MAX_TICK_SECONDS,
    MEDIAN_CALL_SECONDS,
    SESSION_LOAD_SECONDS,
    SESSIONS,
    SINGLE_THREAD_CALLS,
    START_SPREAD_SECONDS,
    THREADS,
    SessionRun,
    client_of,
    live_session_rows,
    seed_answers,
    seed_session_members,
    session_body,
    sixteen_bodies,
    timed,
    timed_with_here,
    worker,
)


def test_sixteen_clients_none_refused_and_each_call_within_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        seqs: list[int] = []
        hub.seed(lambda store: seqs.append(seed_answers(store)))
        hub.start()
        seconds: list[float] = []
        errors: list[BaseException] = []

        bodies = sixteen_bodies(hub, seqs)
        assert len(bodies) == THREADS
        threads = [
            threading.Thread(
                target=worker,
                args=(body, seconds, errors),
            )
            for body in bodies
        ]
        began = time.monotonic()
        for thread in threads:
            thread.start()
            time.sleep(START_SPREAD_SECONDS)
        for thread in threads:
            thread.join(120)

        assert not errors, errors
        assert all(not thread.is_alive() for thread in threads)
        slowest = max(seconds)
        print(
            f"LOAD: {len(seconds)} calls in {time.monotonic() - began:.1f}s, "
            f"slowest {slowest:.3f}s, median {statistics.median(seconds):.3f}s"
        )
        assert slowest < MAX_CALL_SECONDS


def test_one_thread_on_the_idle_hub_has_a_median_under_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        client, cert = client_of(hub, FIRST)

        seconds = [
            timed(client, cert, "decisions", {}, think_seconds=0)[0]
            for _ in range(SINGLE_THREAD_CALLS)
        ]

        median = statistics.median(seconds)
        print(f"LOAD: {SINGLE_THREAD_CALLS} calls, median {median * 1000:.1f} ms")
        assert median < MEDIAN_CALL_SECONDS


def test_inbox_and_send_on_the_idle_hub_have_a_median_under_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        hub.seed(seed_programs)
        hub.start()
        client, cert = client_of(hub, FIRST)

        inbox = [
            timed_with_here(client, cert, "inbox", {}, think_seconds=0)[0]
            for _ in range(SINGLE_THREAD_CALLS)
        ]
        sends = [
            timed_with_here(
                client,
                cert,
                "send",
                {
                    "id": f"idle-{number}",
                    "to": NAMES[LINT],
                    "subject": "s",
                    "body": "b",
                },
                think_seconds=0,
            )[0]
            for number in range(SINGLE_THREAD_CALLS)
        ]

        for name, seconds in (("inbox", inbox), ("send", sends)):
            median = statistics.median(seconds)
            shown = f"median {median * 1000:.1f} ms"
            print(f"LOAD: {name} {SINGLE_THREAD_CALLS} calls, {shown}")
            assert median < MEDIAN_CALL_SECONDS


def test_fifty_ticking_sessions_beside_the_sixteen_clients(tmp_path: Path) -> None:
    """Slice 263, 8.6: 50 sessions on 10 members each tick every 0.5 s for 20 s while
    the sixteen clients run. Every tick is answered within ``MAX_TICK_SECONDS``, no
    session goes ``MAX_GAP_SECONDS`` between replies, every row stays live, and the
    sixteen clients keep 260's bound."""
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        seqs: list[int] = []

        def seed(store: Store) -> None:
            seqs.append(seed_answers(store))
            seed_session_members(store)

        hub.seed(seed)
        hub.start()
        set_hub_timings(hub, **LOAD_TIMINGS)
        seconds: list[float] = []
        errors: list[BaseException] = []
        stop_at = time.monotonic() + SESSION_LOAD_SECONDS
        runs = [SessionRun() for _ in range(SESSIONS)]
        threads = [
            threading.Thread(target=worker, args=(body, seconds, errors))
            for body in sixteen_bodies(hub, seqs)
        ] + [
            threading.Thread(
                target=worker, args=(session_body(hub, n, run, stop_at), [], errors)
            )
            for n, run in enumerate(runs)
        ]
        for thread in threads:
            thread.start()
            time.sleep(START_SPREAD_SECONDS)
        live: list[int] = []
        while time.monotonic() < stop_at - 1:
            time.sleep(1.0)
            if time.monotonic() > stop_at - SESSION_LOAD_SECONDS + 4:
                live.append(live_session_rows(hub))
        for thread in threads:
            thread.join(120)

        assert not errors, errors
        assert all(not thread.is_alive() for thread in threads)
        slowest_tick = max(max(run.took) for run in runs)
        longest_gap = max(run.longest_gap() for run in runs)
        print(
            f"LOAD: {sum(len(run.took) for run in runs)} ticks from {SESSIONS} "
            f"sessions, slowest tick {slowest_tick:.3f}s, longest gap "
            f"{longest_gap:.3f}s, live rows {min(live)}..{max(live)}; sixteen clients "
            f"slowest {max(seconds):.3f}s"
        )
        assert slowest_tick < MAX_TICK_SECONDS
        assert longest_gap < MAX_GAP_SECONDS
        assert live
        assert min(live) == SESSIONS
        assert max(seconds) < MAX_CALL_SECONDS
