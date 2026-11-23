"""The first four functional requirements, on a real hub and two joined homes
(slice 260, D18)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub
from store.decision_support import (
    CORE,
    LINT,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.decision_support import (
    FIRST as FIRST_KEY,
)
from store.decision_support import (
    SECOND as SECOND_KEY,
)
from store.question_support import ANSWERING_RUN, claimed_question

from amoeba.answering.standing_passages import STANDING_SOURCE_PREFIX
from amoeba.answering.values import AnsweringEvidence, PassageRef
from amoeba.store.answers import Settled, settle_answered
from amoeba.store.models import QuestionKey
from amoeba.store.questions import insert_question
from amoeba.store.store import Store

RULING = "Fixture versions are never bumped."
OTHER_RULING = "Releases are cut on Fridays."


def _json(done_out: str) -> dict[str, object]:
    document: dict[str, object] = json.loads(done_out)
    return document


def _standing(hub: FixtureHub, who: str, text: str) -> dict[str, object]:
    done = hub.clients[who].run("standing", "--text", text, "-j")
    assert done.code == 0, done.err
    return _json(done.out)


def _seed_standing_citation(store: Store, standing_id: object) -> None:
    key = QuestionKey("run-citing", "2026-11-10T12:00:00+00:00")
    source = f"{STANDING_SOURCE_PREFIX}{standing_id}"
    ref = PassageRef(id="P1", source=source, question_id=None, date=at(0))
    with store.write() as transaction:
        insert_question(
            transaction,
            replace(claimed_question(key, member_id=CORE), passages=(ref,)),
            now=at(1),
        )
    settled = settle_answered(
        store,
        key,
        ANSWERING_RUN,
        answer="No bump.",
        cited=("P1",),
        evidence=AnsweringEvidence(verdict="yes", reason="the ruling covers it"),
        gate=lambda _prior: None,
        now=at(2),
    )
    assert isinstance(settled, Settled)


def test_a_standing_answer_given_on_one_machine_is_read_from_the_other(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        given = _standing(hub, FIRST, RULING)
        again = _standing(hub, SECOND, RULING)
        other = _standing(hub, SECOND, OTHER_RULING)
        back = _standing(hub, FIRST, OTHER_RULING)

        assert (given["outcome"], again["outcome"]) == ("given", "unchanged")
        assert again["standing_id"] == given["standing_id"]
        assert (other["outcome"], back["outcome"]) == ("given", "unchanged")
        assert back["standing_id"] == other["standing_id"]

        hub.stop()

        def seed(store: Store) -> None:
            seed_programs(store)
            _seed_standing_citation(store, given["standing_id"])

        hub.seed(seed)
        hub.start()

        done = hub.clients[SECOND].run("decisions", "-j")
        assert done.code == 0, done.err
        records: list[dict[str, dict[str, list[dict[str, str]]]]]
        records = _json(done.out)["records"]  # type: ignore[assignment]
        ((record),) = records
        (cited,) = record["based_on"]["cited"]
        assert cited["kind"] == "standing_answer"
        assert cited["source"] == f"{STANDING_SOURCE_PREFIX}{given['standing_id']}"


def test_withdraw_from_the_second_machine_then_unchanged_from_the_first(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        given = _standing(hub, FIRST, RULING)
        standing_id = str(given["standing_id"])

        second = hub.clients[SECOND].run(
            "withdraw", standing_id, "--reason", "no longer true", "-j"
        )
        first = hub.clients[FIRST].run(
            "withdraw", standing_id, "--reason", "no longer true", "-j"
        )

        assert second.code == 0 and first.code == 0, (second.err, first.err)
        assert _json(second.out)["outcome"] == "withdrawn"
        assert _json(first.out)["outcome"] == "unchanged"


def _decisions(hub: FixtureHub, who: str) -> dict[str, object]:
    done = hub.clients[who].run("decisions", "-j")
    assert done.code == 0, done.err
    return _json(done.out)


def test_decisions_are_identical_from_both_and_mark_read_moves_the_shared_marker(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        seqs: list[int] = []

        def seed(store: Store) -> None:
            seed_programs(store)
            seqs.append(automatic_answer(store, FIRST_KEY, CORE, 1))
            seqs.append(waiting_then_pm(store, SECOND_KEY, LINT, 2))

        hub.seed(seed)
        hub.start()

        from_first, from_second = _decisions(hub, FIRST), _decisions(hub, SECOND)
        assert from_first == from_second
        records: list[dict[str, dict[str, str]]] = from_first["records"]  # type: ignore[assignment]
        assert [r["member"]["id"] for r in records] == [CORE, LINT]
        assert [r["member"]["name"] for r in records] == ["core-name", "lint-name"]

        moved = hub.clients[FIRST].run("mark-read", "--through", str(seqs[0]), "-j")
        assert moved.code == 0, moved.err
        after = _decisions(hub, SECOND)
        assert [r["seq"] for r in after["records"]] == [seqs[1]]  # type: ignore[attr-defined, index]
        assert after["marker"] == seqs[0]


def test_standing_for_a_seeded_member_works_and_any_other_reference_is_rejected(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        hub.stop()
        hub.seed(seed_programs)
        hub.start()
        client = hub.clients[SECOND]

        by_id = client.run("standing", "--text", RULING, "--member", CORE, "-j")
        by_name = client.run("standing", "--text", RULING, "--member", "core", "-j")

        assert by_id.code == 0, by_id.err
        assert _json(by_id.out)["member"] == CORE
        assert by_name.code == 1
        assert _json(by_name.out)["rejection"] == "no_such_member"
        assert "cf" not in " ".join(hub.stderr_lines).lower().split()
