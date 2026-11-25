"""What the door load tests share (slice 260, D18; slice 263, 8.6): the seeded answers,
timed calls, the sixteen clients of the 260 case, and the ticking sessions of 263."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hub_fixture import FIRST, SECOND, FixtureHub
from store.decision_support import CORE, LINT, NAMES, seed_programs
from store.question_support import ANSWERING_RUN, claimed_question

from amoeba.answering.values import AnsweringEvidence
from amoeba.client.call import call
from amoeba.client.client_file import ClientFile, load_client_file
from amoeba.operations.here_document import HereCaller
from amoeba.operations.steps.models_session import SessionTickRequest
from amoeba.store.answers import Settled, settle_answered
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.wire.protocol import SessionIdentity
from amoeba.wire.times import TICK_TIMES, DoorTimes

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


def seed_answers(store: Store) -> int:
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


def client_of(hub: FixtureHub, name: str) -> tuple[ClientFile, Path]:
    home = hub.clients[name].home
    cert = home / "pinned-hub-cert.pem"
    return load_client_file(home / "client.yaml", cert), cert


def timed(
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


def timed_with_here(
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


def worker(
    body: Callable[[], list[float]], seconds: list[float], errors: list[BaseException]
) -> None:
    try:
        seconds.extend(body())
    except BaseException as error:  # noqa: BLE001 - handed to the test thread
        errors.append(error)


def sixteen_bodies(hub: FixtureHub, seqs: list[int]) -> list[Callable[[], list[float]]]:
    """The sixteen clients' bodies: readers, writers, senders and inbox readers."""

    def reader(name: str) -> Callable[[], list[float]]:
        def run() -> list[float]:
            client, cert = client_of(hub, name)
            return [
                timed(client, cert, "decisions", {"since": "2020-01-01T00:00:00Z"})[0]
                for _ in range(ROUNDS)
            ]

        return run

    def writer(name: str, number: int) -> Callable[[], list[float]]:
        def run() -> list[float]:
            client, cert = client_of(hub, name)
            times: list[float] = []
            for round_number in range(ROUNDS):
                text = f"ruling {number}-{round_number}"
                took, given = timed(client, cert, "standing", {"text": text})
                assert given["outcome"] == "given", given
                times.append(took)
                took, withdrawn = timed(
                    client,
                    cert,
                    "withdraw",
                    {"standing_id": given["standing_id"], "reason": "load"},
                )
                assert withdrawn["outcome"] == "withdrawn", withdrawn
                times.append(took)
                took, marked = timed(client, cert, "mark_read", {"through": seqs[0]})
                assert marked["outcome"] in {"moved", "unchanged"}, marked
                times.append(took)
            return times

        return run

    def sender(number: int) -> Callable[[], list[float]]:
        def run() -> list[float]:
            client, cert = client_of(hub, FIRST)
            times: list[float] = []
            for round_number in range(ROUNDS):
                document = {
                    "id": f"load-{number}-{round_number}",
                    "to": NAMES[LINT],
                    "subject": "load",
                    "body": "a request under load",
                }
                took, sent = timed_with_here(client, cert, "send", document)
                assert sent["outcome"] == "sent", sent
                times.append(took)
            return times

        return run

    def inbox_reader() -> Callable[[], list[float]]:
        def run() -> list[float]:
            client, cert = client_of(hub, FIRST)
            times: list[float] = []
            for _ in range(ROUNDS):
                took, listed = timed_with_here(client, cert, "inbox", {})
                assert listed["outcome"] == "listed", listed
                times.append(took)
            return times

        return run

    return (
        [reader(FIRST if n % 2 else SECOND) for n in range(READERS)]
        + [writer(FIRST if n % 2 else SECOND, n) for n in range(WRITERS)]
        + [sender(n) for n in range(SENDERS)]
        + [inbox_reader() for _ in range(INBOX_READERS)]
    )


# --- ticking sessions (slice 263, 8.6) -------------------------------------------

SESSIONS = 50
SESSION_MEMBERS = 10
TICK_PERIOD_SECONDS = 0.5
SESSION_LOAD_SECONDS = 20.0
#: Every tick answered within this; no session goes longer than the gap between replies.
MAX_TICK_SECONDS = 2.0
MAX_GAP_SECONDS = 3.0
#: The hub's timings for the case: a tick every period, a row refresh each second, and
#: a row stale after four, so a session that missed a few ticks would show.
LOAD_TIMINGS = {
    "notify_poll_seconds": TICK_PERIOD_SECONDS,
    "session_heartbeat_seconds": 1.0,
    "session_stale_seconds": 4.0,
}
LOAD_STALE_SECONDS = 4.0
SESSION_CLIENT = "claude-code"


def session_member(number: int) -> str:
    """The member session ``number`` serves: ``SESSIONS`` spread over the members."""
    return f"load-member-{number % SESSION_MEMBERS}"


def seed_session_members(store: Store) -> None:
    """``SESSION_MEMBERS`` members of program ``trading``, each with a checkout on the
    acting machine whose Context Forge id is the member's own id."""
    from store.decision_support import TRADING, at
    from store.seed import insert_checkout, insert_member

    with store.write() as transaction:
        for number in range(SESSION_MEMBERS):
            member = session_member(number)
            insert_member(
                transaction,
                project_id=member,
                program_id=TRADING,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=at(0),
                updated_at=at(0),
                name=member,
            )
            insert_checkout(
                transaction,
                member_id=member,
                cf_project_id=member,
                path=f"/work/{member}",
                now=at(0),
            )


@dataclass
class SessionRun:
    """One session's ticks: how long each took, and when each reply came."""

    took: list[float] = field(default_factory=lambda: list[float]())
    replied_at: list[float] = field(default_factory=lambda: list[float]())

    def longest_gap(self) -> float:
        return max(
            b - a for a, b in zip(self.replied_at, self.replied_at[1:], strict=False)
        )


def session_body(
    hub: FixtureHub, number: int, run: SessionRun, stop_at: float
) -> Callable[[], list[float]]:
    """Session ``number``: a tick every ``TICK_PERIOD_SECONDS`` until ``stop_at``."""

    def ticking() -> list[float]:
        client, cert = client_of(hub, FIRST)
        member = session_member(number)
        directory = f"/work/{member}/session-{number}"
        identity = SessionIdentity(f"{number:032x}", member, SESSION_CLIENT, directory)
        request = SessionTickRequest(
            here=HereCaller(project_id=member),
            session_id=identity.session_id,
            client=SESSION_CLIENT,
            directory=directory,
            last_seen=None,
            push_confirmed=False,
        )
        document = request.model_dump(mode="json")
        due = time.monotonic()
        while time.monotonic() < stop_at:
            began = time.monotonic()
            call(client, cert, "session_tick", document, TICK_TIMES, identity=identity)
            ended = time.monotonic()
            run.took.append(ended - began)
            run.replied_at.append(ended)
            due += TICK_PERIOD_SECONDS
            time.sleep(max(0.0, due - time.monotonic()))
        return run.took

    return ticking


def live_session_rows(hub: FixtureHub) -> int:
    """How many rows have a heartbeat inside the stale time, on a plain read."""
    oldest = encode_timestamp(datetime.now(UTC) - timedelta(seconds=LOAD_STALE_SECONDS))
    with closing(sqlite3.connect(hub.layout.store_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE heartbeat_at > ?", (oldest,)
        ).fetchone()
    return int(row[0])
