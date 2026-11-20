"""``amoeba standing`` and ``amoeba withdraw``: text, JSON and exit codes (slice 230).

In-process through ``main``, with the autouse temporary ``AMOEBA_HOME``. The
``--member`` lookup is stubbed at the operation's ``project_of``.
"""

from __future__ import annotations

import json

import pytest
from store.question_support import MEMBER_ID, seed_members
from user_configs import example_config_text

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE, main
from amoeba.config.home import config_path, store_path
from amoeba.operations import standing as standing_operation
from amoeba.store.errors import StoreBusyError
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import CFProject

RULING = "CONCERNS reviews never block a merge."


@pytest.fixture(autouse=True)
def _members() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")
    with Store.open(store_path()) as store:
        seed_members(store)


@pytest.fixture
def known_member(monkeypatch: pytest.MonkeyPatch) -> None:
    """``cf`` knows ``member-name`` as the seeded member."""
    project = CFProject(id=MEMBER_ID, name="member-name", project_path="/work/a")

    def found(**_kwargs: object) -> CFProject:
        return project

    monkeypatch.setattr(standing_operation, "project_of", found)


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = main(list(argv))
    return code, capsys.readouterr().out


def _count() -> int:
    with Store.open(store_path()) as store, store.read() as transaction:
        return int(
            transaction.execute("SELECT COUNT(*) FROM standing_answers").fetchone()[0]
        )


@pytest.mark.parametrize(
    ("flags", "reach"),
    [
        ((), "reach: everything"),
        (("--program", "demo"), "reach: program demo"),
        (("--member", "member-name"), f"reach: member {MEMBER_ID}"),
    ],
)
@pytest.mark.usefixtures("known_member")
def test_standing_prints_the_id_and_reach_and_exits_zero(
    capsys: pytest.CaptureFixture[str], flags: tuple[str, ...], reach: str
) -> None:
    code, out = _run(capsys, "standing", "--text", RULING, *flags)

    assert code == EXIT_OK
    assert out.splitlines()[0] == "given: standing answer #1"
    assert reach in out


def test_a_repeat_prints_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    _run(capsys, "standing", "--text", RULING)

    code, out = _run(capsys, "standing", "--text", RULING)

    assert code == EXIT_OK
    assert out.startswith("unchanged: standing answer #1")
    assert _count() == 1


def test_both_flags_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["standing", "--text", RULING, "--program", "demo", "--member", "x"])

    assert raised.value.code == EXIT_USAGE
    assert _count() == 0


def test_an_unknown_program_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run(capsys, "standing", "--text", RULING, "--program", "nope")

    assert code == EXIT_REJECTED
    assert out.startswith("rejected: no_such_program: ")


def test_withdraw_then_unchanged_then_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _run(capsys, "standing", "--text", RULING)

    first = _run(capsys, "withdraw", "1", "--reason", "wrong")
    second = _run(capsys, "withdraw", "1", "--reason", "wrong")
    unknown = _run(capsys, "withdraw", "2", "--reason", "wrong")

    assert first == (EXIT_OK, "withdrawn: standing answer #1\n")
    assert second == (EXIT_OK, "unchanged: standing answer #1\n")
    assert unknown[0] == EXIT_REJECTED
    assert unknown[1].startswith("rejected: no_such_standing_answer: ")


def test_withdraw_needs_no_config_file(capsys: pytest.CaptureFixture[str]) -> None:
    _run(capsys, "standing", "--text", RULING)
    config_path().unlink()

    assert _run(capsys, "withdraw", "1", "--reason", "wrong") == (
        EXIT_OK,
        "withdrawn: standing answer #1\n",
    )


@pytest.mark.usefixtures("known_member")
def test_json_carries_the_result_fields(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run(capsys, "standing", "-j", "--text", RULING, "--member", "x")
    given = json.loads(out)
    _, out = _run(capsys, "withdraw", "-j", "1", "--reason", "wrong")
    withdrawn = json.loads(out)

    assert code == EXIT_OK
    assert given == {
        "outcome": "given",
        "rejection": None,
        "standing_id": 1,
        "reach": "member",
        "program": None,
        "member": MEMBER_ID,
        "problems": [],
    }
    assert withdrawn == {
        "outcome": "withdrawn",
        "rejection": None,
        "standing_id": 1,
        "problems": [],
    }


def test_a_store_error_exits_three_with_nothing_written(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def busy(*_args: object) -> tuple[int, bool]:
        raise StoreBusyError("store busy")

    monkeypatch.setattr(standing_operation, "give_standing", busy)

    code = main(["standing", "--text", RULING])

    assert code == EXIT_ERROR
    assert "StoreBusyError" in capsys.readouterr().err
    assert _count() == 0


def test_a_cf_failure_exits_three_with_nothing_written(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed(**_kwargs: object) -> CfCallFailed:
        return CfCallFailed("cf broke")

    monkeypatch.setattr(standing_operation, "project_of", failed)

    code = main(["standing", "--text", RULING, "--member", "member-name"])

    assert code == EXIT_ERROR
    assert "ContextForgeError" in capsys.readouterr().err
    assert _count() == 0
