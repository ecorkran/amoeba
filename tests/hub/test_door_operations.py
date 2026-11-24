"""The ten operations through ``handle_call`` (slice 261, 13.2 to 13.5, D5, D9, D12).

The hub is seeded with members ``CORE`` and ``LINT`` (names in ``NAMES``), each with a
checkout on ``alpha``, the machine every call here is made from. ``here`` and ``runs``
are the documents a client would send.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest
from store.decision_support import CORE, LINT, NAMES
from store.question_support import NOW
from store.release_support import FULL_HASH
from store.seed import insert_checkout

from amoeba.hub.store_open import open_hub_store
from amoeba.operations.errors import NOT_SERVED, CallRefused
from amoeba.operations.here_document import HereCaller, HereCheckout
from amoeba.operations.runs_document import RunsDocument, runs_to_document
from amoeba.store.machines import ActingMachine, hash_token, machine_for_token
from amoeba.wire.protocol import DoneReply, RefusalCode, RefusedReply
from hub.call_support import BETA_TOKEN, HubRig, build_rig, result_of

SRC = Path(__file__).parents[2] / "src" / "amoeba"
RUNS = runs_to_document(RunsDocument())
CALLER = HereCaller(project_id=CORE).model_dump()
FRESH_CHECKOUT = HereCheckout(
    project_id="cf-fresh",
    name="fresh-repo",
    path="/work/fresh",
    origin="github.com/org/fresh-repo",
).model_dump()
BOTH: dict[str, object] = {"here": CALLER, "runs": RUNS}


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


def _done(
    rig: HubRig,
    name: str,
    document: object,
    extra: dict[str, object] | None = None,
    *,
    call_id: str = "call-1",
) -> DoneReply:
    reply = rig.call(name, document, call_id=call_id, extra=extra)
    parsed = result_of(reply)
    assert isinstance(parsed, DoneReply), parsed
    return parsed


def _refused(reply_object: object, code: RefusalCode) -> RefusedReply:
    parsed = result_of(reply_object)  # type: ignore[arg-type]
    assert isinstance(parsed, RefusedReply), parsed
    assert parsed.code is code, parsed
    return parsed


def _kept(rig: HubRig) -> int:
    (row,) = rig.rows("SELECT COUNT(*) FROM call_results")
    return int(str(row[0]))


@pytest.mark.parametrize(
    ("name", "document", "extra"),
    [
        ("status", {}, BOTH),
        ("list", {}, BOTH),
        ("list", {"subject": "members"}, {}),
        ("inbox", {}, {"here": CALLER}),
        ("changes", {}, {"here": CALLER}),
    ],
    ids=["status", "list", "list-members", "inbox", "changes"],
)
def test_each_read_runs_on_the_hub_and_keeps_no_result(
    rig: HubRig, name: str, document: object, extra: dict[str, object]
) -> None:
    done = _done(rig, name, document, extra)

    assert done.result
    assert _kept(rig) == 0


def test_status_names_the_members_from_the_hub_store(rig: HubRig) -> None:
    done = _done(rig, "status", {}, BOTH)

    programs = cast("list[dict[str, Any]]", done.result["programs"])
    names = {
        str(member["member"]["name"])
        for program in programs
        for member in program["members"]
    }
    assert names == {NAMES[CORE]}


def test_list_members_ignores_a_here_it_does_not_need(rig: HubRig) -> None:
    done = _done(rig, "list", {"subject": "members"}, {"here": {"unparseable": True}})

    assert len(done.result["members"]) == 2  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("status", {"runs": RUNS}),
        ("status", {"here": CALLER}),
        ("list", {"runs": RUNS}),
        ("inbox", {}),
        ("changes", {}),
        ("send", {}),
        ("reply", {}),
        ("cancel", {}),
        ("report_release", {}),
        ("add", {}),
    ],
)
def test_a_call_missing_a_needed_value_is_malformed_with_the_touch_committed(
    rig: HubRig, name: str, extra: dict[str, object]
) -> None:
    reply = rig.call(name, {}, extra=extra or None)

    refused = _refused(reply, RefusalCode.MALFORMED_CALL)
    assert "here" in refused.message or "runs" in refused.message
    assert rig.rows("SELECT last_called_at FROM machines WHERE name = 'alpha'") == [
        (rig.clock_now.isoformat(),)
    ]
    assert _kept(rig) == 0


def test_an_unparseable_here_or_runs_is_malformed(rig: HubRig) -> None:
    bad_runs = rig.call("status", {}, extra={"here": CALLER, "runs": {"open_runs": 1}})
    bad_here = rig.call("inbox", {}, extra={"here": {"project_id": 7}})

    assert "runs" in _refused(bad_runs, RefusalCode.MALFORMED_CALL).message
    assert "here" in _refused(bad_here, RefusalCode.MALFORMED_CALL).message


def test_add_with_an_unreduced_origin_is_malformed_and_writes_nothing(
    rig: HubRig,
) -> None:
    password_form = {**FRESH_CHECKOUT, "origin": "https://user:secret@host/org/x.git"}
    before = rig.rows("SELECT COUNT(*) FROM members")

    reply = rig.call("add", {}, extra={"here": password_form})

    refused = _refused(reply, RefusalCode.MALFORMED_CALL)
    assert "secret" not in refused.message
    assert rig.rows("SELECT COUNT(*) FROM members") == before
    assert _kept(rig) == 0


def test_add_creates_a_member_with_the_checkout_and_keeps_its_result(
    rig: HubRig,
) -> None:
    done = _done(rig, "add", {}, {"here": FRESH_CHECKOUT})

    assert done.result["outcome"] == "applied"
    assert rig.rows("SELECT name, origin FROM members WHERE name = 'fresh-repo'") == [
        ("fresh-repo", "github.com/org/fresh-repo")
    ]
    assert rig.rows(
        "SELECT COUNT(*) FROM checkouts WHERE cf_project_id = 'cf-fresh'"
    ) == [(1,)]
    assert _kept(rig) == 1


def test_add_by_project_needs_no_here_and_rm_by_name_removes_with_no_here(
    rig: HubRig,
) -> None:
    added = _done(rig, "add", {"project": NAMES[LINT], "rules": []}, call_id="a")
    removed = _done(rig, "rm", {"members": [NAMES[LINT]]}, call_id="b")

    assert added.result["working_directory"] is None
    assert removed.result["outcome"] == "applied"
    assert removed.result["working_directory"] is None
    assert rig.rows(
        "SELECT removed_at IS NOT NULL FROM members WHERE project_id = ?".replace(
            "?", f"'{LINT}'"
        )
    ) == [(1,)]


def test_reply_cancel_and_report_release_run_and_keep_their_results(
    rig: HubRig,
) -> None:
    released = _done(
        rig,
        "report_release",
        {"commit": FULL_HASH, "changed": "a change", "touched": ["api"]},
        {"here": CALLER},
    )
    replied = rig.call(
        "reply",
        {"id": "nothing", "action": "accept"},
        call_id="r1",
        extra={"here": CALLER},
    )
    cancelled = rig.call(
        "cancel", {"id": "nothing"}, call_id="c1", extra={"here": CALLER}
    )

    assert released.result["outcome"] == "recorded"
    assert isinstance(result_of(replied), DoneReply)
    assert isinstance(result_of(cancelled), DoneReply)
    assert _kept(rig) == 3


def _give_lint_a_wake_command_on_beta(rig: HubRig) -> None:
    with open_hub_store(rig.layout) as store:
        with store.read() as transaction:
            beta = machine_for_token(transaction, hash_token(BETA_TOKEN))
        assert isinstance(beta, ActingMachine)
        store.act_as(beta)
        with store.write() as transaction:
            insert_checkout(
                transaction,
                member_id=LINT,
                cf_project_id="cf-lint-on-beta",
                path="/beta/lint",
                wake_command="claude -p go",
                now=NOW,
            )


SEND = {"id": "ask", "to": NAMES[LINT], "subject": "s", "body": "b"}
SEND_TO_CORE = {**SEND, "id": "ask-core", "to": NAMES[CORE]}


def test_a_send_to_a_member_with_no_wake_command_is_served(rig: HubRig) -> None:
    _give_lint_a_wake_command_on_beta(rig)

    done = _done(
        rig,
        "send",
        SEND_TO_CORE,
        {"here": {"project_id": LINT}, "logs_dir": "/machine/logs"},
    )

    assert done.result["outcome"] == "sent"
    assert rig.rows("SELECT COUNT(*) FROM messages") == [(1,)]
    assert _kept(rig) == 1


def test_a_hub_part_refusal_keeps_no_result_for_a_repeat(rig: HubRig) -> None:
    bad: dict[str, object] = {"here": CALLER, "runs": {"open_runs": 1}}

    first = rig.call("status", {}, call_id="same", extra=bad)
    again = rig.call("status", {}, call_id="same", extra=bad)

    assert _refused(first, RefusalCode.MALFORMED_CALL)
    assert _refused(again, RefusalCode.MALFORMED_CALL)
    assert _kept(rig) == 0


def test_a_refusal_code_the_hub_part_raises_is_a_refusal_code() -> None:
    assert RefusalCode(NOT_SERVED) is RefusalCode.NOT_SERVED
    assert issubclass(CallRefused, Exception)


def test_only_the_hub_call_handler_catches_call_refused() -> None:
    """With no client file a ``CallRefused`` is a bug that nothing catches (D12)."""
    catching: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            named = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
            if "CallRefused" in named:
                catching.append(str(path.relative_to(SRC)))

    assert catching == ["hub/calls.py"]
