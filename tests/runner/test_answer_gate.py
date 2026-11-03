"""The answer gate (slice 142, D1/D2): the limit, the reserved screen, the text."""

from __future__ import annotations

import pytest
from answerer_settings import answerer_settings

from amoeba.runner.answering import gate
from amoeba.runner.answering.gate import compose_instructions, evaluate_gate
from amoeba.runner.project_config import AnswererSettings
from amoeba.store import DeclineReason, GateRefusal
from runner.purity import io_use

QUESTION = "Which branch should the release go on?"
ANSWER = "Use main."


def _settings(limit: int = 3, terms: list[str] | None = None) -> AnswererSettings:
    return answerer_settings(
        answer_limit=limit, reserved_terms=() if terms is None else tuple(terms)
    )


def _gate(
    *,
    question: str = QUESTION,
    answer: str = ANSWER,
    prior: int = 0,
    settings: AnswererSettings | None = None,
) -> GateRefusal | None:
    return evaluate_gate(
        question,
        prior,
        answer=answer,
        settings=_settings() if settings is None else settings,
    )


@pytest.mark.parametrize("prior", [0, 1, 2])
def test_below_the_limit_passes(prior: int) -> None:
    assert _gate(prior=prior) is None


@pytest.mark.parametrize("prior", [3, 4, 50])
def test_at_and_above_the_limit_refuses_without_a_term(prior: int) -> None:
    assert _gate(prior=prior) == GateRefusal(DeclineReason.ANSWER_LIMIT_REACHED, None)


def test_the_limit_wins_over_a_reserved_hit() -> None:
    refusal = _gate(prior=3, answer="drop table users", settings=_settings(3, ["drop"]))

    assert refusal == GateRefusal(DeclineReason.ANSWER_LIMIT_REACHED, None)


def test_a_term_in_the_question_refuses() -> None:
    refusal = _gate(
        question="Can I force push to main?", settings=_settings(terms=["force push"])
    )

    assert refusal == GateRefusal(DeclineReason.RESERVED_TERM, "force push")


def test_a_term_in_the_answer_refuses() -> None:
    refusal = _gate(answer="Yes, force push it.", settings=_settings(terms=["force"]))

    assert refusal == GateRefusal(DeclineReason.RESERVED_TERM, "force")


def test_case_and_split_whitespace_still_match_a_multi_word_term() -> None:
    refusal = _gate(
        answer="Go ahead and Drop\n Table users.",
        settings=_settings(terms=["drop table"]),
    )

    assert refusal == GateRefusal(DeclineReason.RESERVED_TERM, "drop table")


def test_a_term_matches_inside_a_longer_word() -> None:
    refusal = _gate(answer="It was pushed.", settings=_settings(terms=["push"]))

    assert refusal == GateRefusal(DeclineReason.RESERVED_TERM, "push")


def test_configured_order_decides_which_term_is_reported() -> None:
    both = "delete the branch, then merge"

    assert _gate(answer=both, settings=_settings(terms=["merge", "delete"])) == (
        GateRefusal(DeclineReason.RESERVED_TERM, "merge")
    )
    assert _gate(answer=both, settings=_settings(terms=["delete", "merge"])) == (
        GateRefusal(DeclineReason.RESERVED_TERM, "delete")
    )


def test_the_reported_term_keeps_its_configured_case() -> None:
    refusal = _gate(
        answer="deploy to prod", settings=_settings(terms=["Deploy To PROD"])
    )

    assert refusal == GateRefusal(DeclineReason.RESERVED_TERM, "Deploy To PROD")


def test_an_empty_term_list_never_refuses_on_terms() -> None:
    assert _gate(answer="drop table, force push, everything") is None


def test_a_clean_question_and_answer_pass() -> None:
    assert _gate(settings=_settings(terms=["drop table", "force push"])) is None


def test_compose_instructions_is_exactly_two_lines() -> None:
    assert compose_instructions(QUESTION, ANSWER) == (
        "You asked: Which branch should the release go on?\nAnswer: Use main."
    )


def test_the_gate_module_does_no_io() -> None:
    assert io_use(gate) == []
