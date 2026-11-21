"""The stand-in's pure parts: spotting a hand-off, the prompt, reading the verdict."""

from __future__ import annotations

import pytest

from amoeba.operations.stand_in import (
    MESSAGE_MAX_CHARS,
    Verdict,
    VerdictError,
    build_prompt,
    hands_off,
    read_verdict,
)


@pytest.mark.parametrize(
    "message",
    [
        "Want me to run the same pass on the task files?",
        "264, no-checkout restore (your call): add a command or not.",
        "Say the word and I'll fix them.",
        "Two options: A or B. Let me know.",
        "This is a PM decision.",
    ],
)
def test_a_message_that_hands_something_off_is_spotted(message: str) -> None:
    assert hands_off(message)


@pytest.mark.parametrize(
    "message",
    ["Done. Tests pass and the fix is committed as abc123.", "Committed and pushed."],
)
def test_a_report_of_finished_work_is_not_a_handoff(message: str) -> None:
    assert not hands_off(message)


def test_the_prompt_holds_every_part_and_cuts_a_long_message() -> None:
    prompt = build_prompt(
        message="x" * (MESSAGE_MAX_CHARS + 50),
        rules="RULES-TEXT",
        memory="",
        standing="- [all] STANDING-TEXT",
        cwd="/some/repo",
    )
    assert "RULES-TEXT" in prompt
    assert "STANDING-TEXT" in prompt
    assert "/some/repo" in prompt
    assert "(none found)" in prompt
    assert "[... cut for length ...]" in prompt


def test_a_verdict_inside_a_code_fence_is_read() -> None:
    reply = 'Here it is:\n```json\n{"verdict": "settled", "text": " Do B. "}\n```'
    judgement = read_verdict(reply)
    assert judgement.verdict is Verdict.SETTLED
    assert judgement.text == "Do B."


@pytest.mark.parametrize(
    "reply",
    [
        "no object here",
        '{"verdict": "maybe", "text": "x"}',
        '{"verdict": "for_pm", "text": "  "}',
        '{"verdict": "settled"',
    ],
)
def test_an_unreadable_verdict_raises(reply: str) -> None:
    with pytest.raises(VerdictError):
        read_verdict(reply)


def test_asking_the_pm_whether_to_ask_a_peer_is_a_handoff_the_judge_settles() -> None:
    message = "Should I ask the ai-project-guide session to release the guide?"

    assert hands_off(message)
    prompt = build_prompt(message=message, rules="", memory="", standing="", cwd="/r")
    assert "message that session directly" in prompt
    assert "that session's question to raise" in prompt
