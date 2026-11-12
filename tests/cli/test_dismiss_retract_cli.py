"""``amoeba dismiss`` and ``amoeba retract``: result JSON and exit codes
(slice 228, D5, D6, D13).

In-process through ``main``: neither command needs ``sq``, ``cf`` or the config, and
``AMOEBA_HOME`` is the autouse temporary home.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from store.decision_support import SECOND, waiting_then_pm
from store.question_support import KEY, MEMBER_ID, NOW, seed_members, waiting_question

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE, main
from amoeba.config.home import store_path
from amoeba.store.questions import insert_question
from amoeba.store.store import Store

REASON = "not needed tonight"


def _seed_waiting() -> None:
    with Store.open(store_path()) as store:
        seed_members(store)
        with store.write() as transaction:
            insert_question(transaction, waiting_question(), now=NOW)


def _seed_pm_answer() -> int:
    with Store.open(store_path()) as store:
        seed_members(store)
        return waiting_then_pm(store, SECOND, MEMBER_ID, 2)


def _run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str, str]:
    code = main(list(arguments))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_dismiss_prints_its_result_and_exits_zero_for_dismissed_and_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_waiting()

    code, out, _ = _run(capsys, "dismiss", KEY.run_id, "--reason", REASON)

    assert code == EXIT_OK
    first = json.loads(out)
    assert first["outcome"] == "dismissed"
    assert first["closed_detail"] == REASON
    assert first["key"] == {"run_id": KEY.run_id, "paused_at": KEY.paused_at}

    code, out, _ = _run(capsys, "dismiss", KEY.run_id, "--reason", "again")

    assert code == EXIT_OK
    assert json.loads(out)["outcome"] == "unchanged"


def test_dismiss_takes_a_paused_at(capsys: pytest.CaptureFixture[str]) -> None:
    _seed_waiting()

    code, out, _ = _run(
        capsys, "dismiss", KEY.run_id, "--paused-at", KEY.paused_at, "--reason", REASON
    )

    assert code == EXIT_OK
    assert json.loads(out)["key"]["paused_at"] == KEY.paused_at


def test_a_rejected_dismiss_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    _seed_waiting()

    code, out, _ = _run(capsys, "dismiss", "no-such-run", "--reason", REASON)

    assert code == EXIT_REJECTED
    result = json.loads(out)
    assert (result["outcome"], result["rejection"]) == (
        "rejected",
        "no_such_question",
    )


def test_a_blank_reason_is_a_rejected_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_waiting()

    code, out, _ = _run(capsys, "dismiss", KEY.run_id, "--reason", "  ")

    assert code == EXIT_REJECTED
    assert json.loads(out)["rejection"] == "malformed"


def test_retract_prints_its_result_and_exits_zero_for_retracted_and_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seq = _seed_pm_answer()

    code, out, _ = _run(capsys, "retract", str(seq), "--reason", "wrong number")

    assert code == EXIT_OK
    assert json.loads(out)["outcome"] == "retracted"
    assert json.loads(out)["answer_seq"] == seq

    code, out, _ = _run(capsys, "retract", str(seq), "--reason", "wrong number")

    assert code == EXIT_OK
    assert json.loads(out)["outcome"] == "unchanged"


def test_a_rejected_retract_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    _seed_pm_answer()

    code, out, _ = _run(capsys, "retract", "999", "--reason", "x")

    assert code == EXIT_REJECTED
    assert json.loads(out)["rejection"] == "no_such_answer"


@pytest.mark.parametrize(
    "arguments",
    [
        ["dismiss"],
        ["dismiss", "run-1"],
        ["retract"],
        ["retract", "7"],
        ["retract", "seven", "--reason", "x"],
    ],
)
def test_missing_or_malformed_arguments_exit_two(
    capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == EXIT_USAGE
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "arguments",
    [["dismiss", "run-1", "--reason", "x"], ["retract", "1", "--reason", "x"]],
)
def test_a_store_error_exits_three(
    capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    path: Path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("this is not a sqlite database" * 100, encoding="utf-8")

    code, out, err = _run(capsys, *arguments)

    assert code == EXIT_ERROR
    assert out == ""
    assert err.startswith("error: StoreCorruptError")
