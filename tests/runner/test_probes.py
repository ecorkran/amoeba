"""The sq start probe and the per-link cf probes (D9)."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cf_stub import LOG_ENV, MODE_ENV, CfMode, write_cf_stub

from amoeba.process import (
    PollFailure,
    ProcessSettings,
    RunOutcome,
    RunPoll,
    StartupFailedError,
)
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.probes import (
    LinkProbes,
    ProbeCutOff,
    ProbeFailed,
    ProbePassed,
    probe_link,
    probe_sq,
)
from amoeba.store import NodeKind, Store
from runner.observe_support import Clock, FakeCf, Host, document
from runner.tick_support import PROJECT, Rig, link

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cf"
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
TIMEOUT = 8.0


def _budget(deadline: float = 1_000.0, clock: Clock | None = None) -> TickBudget:
    return TickBudget(deadline, Host(), (clock or Clock()).monotonic)


# -- the sq probe -------------------------------------------------------------


class ScriptedSq:
    """A stand-in for ``poll_run``: answers from a function of the asked id."""

    def __init__(self, answer: Callable[[str], RunPoll]) -> None:
        self.answer = answer
        self.asked: list[tuple[str, float]] = []

    def __call__(self, run_id: str, *, timeout_seconds: float) -> RunPoll:
        self.asked.append((run_id, timeout_seconds))
        return self.answer(run_id)


def _not_found(run_id: str) -> RunPoll:
    return document(run_id, RunOutcome.NOT_FOUND)


def test_sq_passes_on_not_found_for_the_minted_id() -> None:
    poll = ScriptedSq(_not_found)

    probe_sq(ProcessSettings(sq_timeout_seconds=3.0), NOW, poll)

    [(run_id, timeout)] = poll.asked
    assert run_id.startswith("amoeba-20261023T120000Z-") and timeout == 3.0


def _completed(run_id: str) -> RunPoll:
    return document(run_id, RunOutcome.COMPLETED)


def _other_id(_run_id: str) -> RunPoll:
    return document("someone-else", RunOutcome.NOT_FOUND)


def _failure(_run_id: str) -> RunPoll:
    return PollFailure("sq exited 2: no such command")


@pytest.mark.parametrize(
    ("answer", "words"),
    [
        (_completed, "completed"),
        (_other_id, "someone-else"),
        (_failure, "no such command"),
    ],
    ids=["other-outcome", "other-id", "poll-failure"],
)
def test_sq_fails_start_naming_the_shape_and_the_answer(
    answer: Callable[[str], RunPoll], words: str
) -> None:
    with pytest.raises(StartupFailedError) as raised:
        probe_sq(ProcessSettings(), NOW, ScriptedSq(answer))

    assert "runs wait" in str(raised.value) and "--timeout 0 --json" in str(
        raised.value
    )
    assert words in str(raised.value)


# -- one cf link ----------------------------------------------------------------


def test_a_good_cf_passes_after_two_separate_calls() -> None:
    cf = FakeCf()

    assert probe_link("cf-1", cf, _budget(), TIMEOUT) == ProbePassed()
    assert cf.calls == [
        ["cf", "status", "--json", "-p", "cf-1"],
        ["cf", "list", "initiatives", "--json", "-a", "-p", "cf-1"],
    ]


def test_each_call_is_bounded_and_detached_from_stdin() -> None:
    seen: list[dict[str, object]] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs)
        return FakeCf()(argv)

    probe_link("cf-1", run, _budget(), TIMEOUT)

    assert all(
        k["stdin"] == subprocess.DEVNULL
        and k["capture_output"] is True
        and k["timeout"] == TIMEOUT
        and k["check"] is False
        for k in seen
    )


@pytest.mark.parametrize(
    ("command", "output"),
    [
        ("status", ""),
        ("status", "[]"),
        ("status", "not json"),
        ("list", ""),
        ("list", "{}"),
    ],
    ids=["empty-status", "array-status", "text-status", "empty-list", "object-list"],
)
def test_empty_or_wrongly_shaped_output_fails(command: str, output: str) -> None:
    cf = FakeCf()
    cf.stdout[command] = output

    result = probe_link("cf-1", cf, _budget(), TIMEOUT)

    assert isinstance(result, ProbeFailed)
    assert "cf-1" in result.detail and "JSON" in result.detail


def test_the_probe_passes_on_the_captured_initiatives_output() -> None:
    cf = FakeCf()
    cf.stdout["list"] = (FIXTURES / "list_initiatives_a.json").read_text()

    assert probe_link("cf-1", cf, _budget(), TIMEOUT) == ProbePassed()


def test_an_initiative_missing_its_index_fails_the_probe() -> None:
    cf = FakeCf()
    cf.stdout["list"] = json.dumps([{"name": "n", "isChecked": False}])

    result = probe_link("cf-1", cf, _budget(), TIMEOUT)

    assert isinstance(result, ProbeFailed)
    assert "plan model rejects" in result.detail and "cf-1" in result.detail


def test_a_non_zero_exit_names_the_exit_code() -> None:
    cf = FakeCf()
    cf.returncode = 3

    result = probe_link("cf-1", cf, _budget(), TIMEOUT)

    assert isinstance(result, ProbeFailed) and "exited 3" in result.detail


def test_a_timeout_fails_naming_it() -> None:
    cf = FakeCf()
    cf.error = subprocess.TimeoutExpired("cf", TIMEOUT)

    result = probe_link("cf-1", cf, _budget(), TIMEOUT)

    assert isinstance(result, ProbeFailed) and "timed out" in result.detail


def test_a_missing_cf_fails_rather_than_raising() -> None:
    cf = FakeCf()
    cf.error = FileNotFoundError("cf")

    assert isinstance(probe_link("cf-1", cf, _budget(), TIMEOUT), ProbeFailed)


def test_no_call_starts_with_the_budget_spent() -> None:
    cf = FakeCf()

    assert probe_link("cf-1", cf, _budget(deadline=0.0), TIMEOUT) == ProbeCutOff()
    assert cf.calls == []


def test_a_probe_cut_off_between_the_commands_starts_no_second_call() -> None:
    clock = Clock()
    cf = FakeCf()
    cf.on_call = lambda: setattr(clock, "seconds", 99.0)

    result = probe_link("cf-1", cf, _budget(deadline=5.0, clock=clock), TIMEOUT)

    assert result == ProbeCutOff()
    assert len(cf.calls) == 1


# -- the real stub, as a subprocess ------------------------------------------------


@pytest.fixture
def stub_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = write_cf_stub(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv(LOG_ENV, str(tmp_path / "cf.log"))
    return tmp_path / "cf.log"


@pytest.mark.parametrize(
    ("mode", "passes"),
    [
        (CfMode.GOOD, True),
        (CfMode.EMPTY, False),
        (CfMode.WRONG_FORM, False),
        (CfMode.FAIL, False),
        (CfMode.SLEEP, False),
    ],
)
def test_the_stub_cf_in_each_mode(
    monkeypatch: pytest.MonkeyPatch, stub_path: Path, mode: CfMode, passes: bool
) -> None:
    monkeypatch.setenv(MODE_ENV, mode.value)

    result = probe_link("cf-1", subprocess.run, _budget(), 0.5)

    assert isinstance(result, ProbePassed) is passes
    if mode is CfMode.GOOD:
        assert stub_path.read_text().splitlines() == [
            "status --json -p cf-1",
            "list initiatives --json -a -p cf-1",
        ]


# -- links in a tick -----------------------------------------------------------------


def test_a_link_is_probed_once_per_lifetime() -> None:
    cf = FakeCf()
    probes = LinkProbes(run=cf, timeout_seconds=TIMEOUT)

    for _ in range(3):
        assert probes.check(["cf-1"], _budget(), TickFaults(), "demo") is (
            TickResult.COMPLETE
        )

    assert len(cf.calls) == 2
    assert probes.results(["cf-1", "unprobed"]) == {"cf-1": True}


def test_a_failed_link_recurs_as_a_fault_every_tick_without_reprobing() -> None:
    cf = FakeCf()
    cf.stdout["status"] = ""
    probes = LinkProbes(run=cf, timeout_seconds=TIMEOUT)

    first, second = TickFaults(), TickFaults()
    probes.check(["cf-1"], _budget(), first, "demo")
    probes.check(["cf-1"], _budget(), second, "demo")

    assert len(cf.calls) == 1
    assert (
        [f.kind for f in first]
        == [f.kind for f in second]
        == [FaultKind.CF_PROBE_FAILED]
    )
    assert probes.results(["cf-1"]) == {"cf-1": False}


def test_a_cut_off_probe_records_nothing_and_restarts_from_the_first_command() -> None:
    cf = FakeCf()
    probes = LinkProbes(run=cf, timeout_seconds=TIMEOUT)
    assert probes.check(["cf-1"], _budget(deadline=0.0), TickFaults(), "demo") is (
        TickResult.CUT_OFF
    )
    assert probes.results(["cf-1"]) == {}

    probes.check(["cf-1"], _budget(), TickFaults(), "demo")

    assert [c[1] for c in cf.calls] == ["status", "list"]


def test_a_failed_link_raises_one_escalation_and_the_tick_carries_on(
    tmp_path: Path, store: Store
) -> None:
    store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    link(store, "s-1", "cf-dead", PROJECT)
    rig = Rig(tmp_path, store)
    rig.cf.stdout["status"] = ""

    results = [rig.tick()[0] for _ in range(3)]

    assert results == [TickResult.COMPLETE] * 3
    [row] = store.open_project_escalations(PROJECT)
    assert row.fault_kind == FaultKind.CF_PROBE_FAILED.value
    assert row.payload is not None and "cf-dead" in str(row.payload["detail"])
    assert len(rig.cf.calls) == 1, "probed once per lifetime"
    assert len(store.journal_entries(PROJECT)) == 1, "the launch still happened"


def test_a_failed_link_stays_open_until_a_later_lifetime_passes(
    tmp_path: Path, store: Store
) -> None:
    link(store, "s-1", "cf-dead", PROJECT)
    rig = Rig(tmp_path, store)
    rig.cf.stdout["status"] = ""
    rig.tick()
    rig.tick()
    assert len(store.open_project_escalations(PROJECT)) == 1

    rig.probes = LinkProbes(run=FakeCf(), timeout_seconds=TIMEOUT)  # a restart
    result, _ = rig.tick()

    assert result is TickResult.COMPLETE
    assert store.open_project_escalations(PROJECT) == []


def test_a_probe_cut_off_by_the_deadline_makes_the_tick_cut_off(
    tmp_path: Path, store: Store
) -> None:
    link(store, "s-1", "cf-1", PROJECT)
    rig = Rig(tmp_path, store)
    rig.deadline = 0.0

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert rig.cf.calls == []
    assert rig.probes.results(["cf-1"]) == {}
