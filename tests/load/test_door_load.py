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
from collections.abc import Callable
from pathlib import Path

from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub
from store.decision_support import CORE, LINT, NAMES, seed_programs
from store.question_support import ANSWERING_RUN, claimed_question

from amoeba.answering.values import AnsweringEvidence
from amoeba.client.call import call
from amoeba.client.client_file import ClientFile, load_client_file
from amoeba.store.answers import Settled, settle_answered
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.wire.times import DoorTimes

SEEDED_ANSWERS = 500
THREADS = 16
READERS, WRITERS, SENDERS, INBOX_READERS = 5, 5, 3, 3
ROUNDS = 10
MAX_CALL_SECONDS = 2.0
SINGLE_THREAD_CALLS = 100
MEDIAN_CALL_SECONDS = 0.2
#: A client sends its next call this long after the last reply: an agent or a person
#: is not a tight loop. With none, 16 clients saturate the hub's one process (a
#: 500-answer ``decisions`` costs about 25 ms of its CPU, and Python threads share one
#: interpreter lock), and the slowest call is the queue's length, 1.2 to 2.0 s.
THINK_SECONDS = 0.25
#: Clients start this far apart, so the first calls are not one burst of 16.
START_SPREAD_SECONDS = 0.02


def _seed_answers(store: Store) -> int:
    """``SEEDED_ANSWERS`` automatic answers; returns the last one's seq."""
    from store.decision_support import at

    seed_programs(store)
    last = 0
    for number in range(SEEDED_ANSWERS):
        key = QuestionKey(f"run-{number}", f"2026-11-10T09:{number % 60:02d}:00+00:00")
        with store.write() as transaction:
            insert_question(
                transaction,
                claimed_question(key, member_id=CORE),
                now=at(number),
            )
        settled = settle_answered(
            store,
            key,
            ANSWERING_RUN,
            answer=f"answer {number}",
            cited=("r1",),
            evidence=AnsweringEvidence(verdict="yes", reason="cited"),
            gate=lambda _prior: None,
            now=at(number),
        )
        assert isinstance(settled, Settled)
        last = settled.answer_seq
    return last


def _client(hub: FixtureHub, name: str) -> tuple[ClientFile, Path]:
    home = hub.clients[name].home
    cert = home / "pinned-hub-cert.pem"
    return load_client_file(home / "client.yaml", cert), cert


def _timed(
    client: ClientFile,
    cert: Path,
    name: str,
    document: object,
    think_seconds: float = THINK_SECONDS,
) -> tuple[float, dict[str, object]]:
    began = time.monotonic()
    result = call(client, cert, name, document, DoorTimes())
    took = time.monotonic() - began
    time.sleep(think_seconds)
    return took, result


#: What the client sends beside the document: the caller is ``CORE`` on ``alpha``, and
#: ``send`` names the machine's logs directory for a wake it claims (262 D8).
CALLER_HERE: dict[str, object] = {
    "here": {"project_id": CORE},
    "logs_dir": "/machine/logs",
}


def _timed_with_here(
    client: ClientFile,
    cert: Path,
    name: str,
    document: object,
    think_seconds: float = THINK_SECONDS,
) -> tuple[float, dict[str, object]]:
    began = time.monotonic()
    result = call(client, cert, name, document, DoorTimes(), extra=CALLER_HERE)
    took = time.monotonic() - began
    time.sleep(think_seconds)
    return took, result


def _worker(
    body: Callable[[], list[float]], seconds: list[float], errors: list[BaseException]
) -> None:
    try:
        seconds.extend(body())
    except BaseException as error:  # noqa: BLE001 - handed to the test thread
        errors.append(error)


def test_sixteen_clients_none_refused_and_each_call_within_the_bound(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        seqs: list[int] = []
        hub.seed(lambda store: seqs.append(_seed_answers(store)))
        hub.start()
        seconds: list[float] = []
        errors: list[BaseException] = []

        def reader(name: str) -> Callable[[], list[float]]:
            def run() -> list[float]:
                client, cert = _client(hub, name)
                return [
                    _timed(
                        client, cert, "decisions", {"since": "2020-01-01T00:00:00Z"}
                    )[0]
                    for _ in range(ROUNDS)
                ]

            return run

        def writer(name: str, number: int) -> Callable[[], list[float]]:
            def run() -> list[float]:
                client, cert = _client(hub, name)
                times: list[float] = []
                for round_number in range(ROUNDS):
                    text = f"ruling {number}-{round_number}"
                    took, given = _timed(client, cert, "standing", {"text": text})
                    assert given["outcome"] == "given", given
                    times.append(took)
                    took, withdrawn = _timed(
                        client,
                        cert,
                        "withdraw",
                        {"standing_id": given["standing_id"], "reason": "load"},
                    )
                    assert withdrawn["outcome"] == "withdrawn", withdrawn
                    times.append(took)
                    took, marked = _timed(
                        client, cert, "mark_read", {"through": seqs[0]}
                    )
                    assert marked["outcome"] in {"moved", "unchanged"}, marked
                    times.append(took)
                return times

            return run

        def sender(number: int) -> Callable[[], list[float]]:
            def run() -> list[float]:
                client, cert = _client(hub, FIRST)
                times: list[float] = []
                for round_number in range(ROUNDS):
                    document = {
                        "id": f"load-{number}-{round_number}",
                        "to": NAMES[LINT],
                        "subject": "load",
                        "body": "a request under load",
                    }
                    took, sent = _timed_with_here(client, cert, "send", document)
                    assert sent["outcome"] == "sent", sent
                    times.append(took)
                return times

            return run

        def inbox_reader() -> Callable[[], list[float]]:
            def run() -> list[float]:
                client, cert = _client(hub, FIRST)
                times: list[float] = []
                for _ in range(ROUNDS):
                    took, listed = _timed_with_here(client, cert, "inbox", {})
                    assert listed["outcome"] == "listed", listed
                    times.append(took)
                return times

            return run

        bodies = (
            [reader(FIRST if n % 2 else SECOND) for n in range(READERS)]
            + [writer(FIRST if n % 2 else SECOND, n) for n in range(WRITERS)]
            + [sender(n) for n in range(SENDERS)]
            + [inbox_reader() for _ in range(INBOX_READERS)]
        )
        assert len(bodies) == THREADS
        threads = [
            threading.Thread(
                target=_worker,
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
        client, cert = _client(hub, FIRST)

        seconds = [
            _timed(client, cert, "decisions", {}, think_seconds=0)[0]
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
        client, cert = _client(hub, FIRST)

        inbox = [
            _timed_with_here(client, cert, "inbox", {}, think_seconds=0)[0]
            for _ in range(SINGLE_THREAD_CALLS)
        ]
        sends = [
            _timed_with_here(
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
