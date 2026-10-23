"""Shape probes: ``sq`` once at start, ``cf`` once per link (D9).

``sq`` is probed before the loop and a failure stops the process: a Runner
silently disabled would be a silent fallback. ``cf`` is probed per link on the
first observation of its project; a failure escalates that project and the
others carry on. Every ``cf`` call checks the :class:`TickBudget` first.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from amoeba.process import (
    SQ_EXECUTABLE,
    PollFailure,
    ProcessSettings,
    RunOutcome,
    RunPoll,
    StartupFailedError,
)
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.faults import Fault, FaultKind, TickFaults
from amoeba.runner.launch import mint_run_id

logger = logging.getLogger(__name__)

CF_EXECUTABLE: Final = "cf"
CF_PROJECT_FLAG: Final = "-p"
CF_JSON_FLAG: Final = "--json"

#: The two commands probed, without the executable or the ``-p <id>`` suffix.
CF_STATUS_COMMAND: Final = ("status", CF_JSON_FLAG)
CF_INITIATIVES_COMMAND: Final = ("list", "initiatives", CF_JSON_FLAG)

#: How much of a command's output a failure message quotes.
OUTPUT_HEAD_CHARS: Final = 200  # keeps a failing probe's detail one line long

#: Runs ``cf``: ``subprocess.run`` in production, a fake in unit tests.
type CfRun = Callable[..., subprocess.CompletedProcess[str]]


def probe_sq(
    settings: ProcessSettings,
    now: datetime,
    poll: Callable[..., RunPoll],
) -> None:
    """Check that ``sq runs wait <id> --timeout 0 --json`` has the shape needed.

    A freshly minted id has no run, so the right answer is a ``not_found``
    document carrying the same id.

    Raises:
        StartupFailedError: For any other answer, naming the shape and the answer.
    """
    run_id = mint_run_id(now)
    answer = poll(run_id, timeout_seconds=settings.sq_timeout_seconds)
    shape = f"`{SQ_EXECUTABLE} runs wait {run_id} --timeout 0 --json`"
    if isinstance(answer, PollFailure):
        raise StartupFailedError(f"sq probe failed: {shape}: {answer.reason}")
    if answer.outcome is not RunOutcome.NOT_FOUND or answer.run_id != run_id:
        raise StartupFailedError(
            f"sq probe failed: {shape} answered outcome {answer.outcome.value} "
            f"for run {answer.run_id}, expected not_found for {run_id}"
        )


@dataclass(frozen=True)
class ProbePassed:
    """Both commands answered in the expected shape."""


@dataclass(frozen=True)
class ProbeFailed:
    """A command failed; ``detail`` names it, the exit code and the output head."""

    detail: str


@dataclass(frozen=True)
class ProbeCutOff:
    """The budget refused a call. Nothing is recorded; the link restarts."""


type ProbeResult = ProbePassed | ProbeFailed | ProbeCutOff


def _is_json_object(value: object) -> bool:
    return isinstance(value, dict)


def _is_json_array(value: object) -> bool:
    return isinstance(value, list)


#: Each probed command with the top-level form its output must have.
_PROBES: Final = (
    (CF_STATUS_COMMAND, _is_json_object, "object"),
    (CF_INITIATIVES_COMMAND, _is_json_array, "array"),
)


def probe_link(
    cf_project_id: str, run: CfRun, budget: TickBudget, timeout_seconds: float
) -> ProbeResult:
    """Probe one CF link: both commands, each a separate budgeted call."""
    for command, has_form, form in _PROBES:
        if not budget.allows_call():
            return ProbeCutOff()
        argv = [CF_EXECUTABLE, *command, CF_PROJECT_FLAG, cf_project_id]
        shown = " ".join(argv)
        try:
            completed = run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ProbeFailed(f"`{shown}` timed out after {timeout_seconds}s")
        except OSError as error:
            # An expected external failure: cf missing or not runnable.
            return ProbeFailed(f"`{shown}` could not run: {error}")
        head = completed.stdout[:OUTPUT_HEAD_CHARS]
        if completed.returncode != 0:
            return ProbeFailed(f"`{shown}` exited {completed.returncode}: {head}")
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return ProbeFailed(f"`{shown}` printed no JSON {form}: {head!r}")
        if not has_form(parsed):
            return ProbeFailed(f"`{shown}` did not print a JSON {form}: {head!r}")
    return ProbePassed()


class LinkProbes:
    """Which CF links passed their probe in this process lifetime."""

    def __init__(self, *, run: CfRun, timeout_seconds: float) -> None:
        self._run = run
        self._timeout_seconds = timeout_seconds
        self._failed: dict[str, str] = {}
        self._passed: set[str] = set()

    def results(self, cf_project_ids: Sequence[str]) -> Mapping[str, bool]:
        """Link to whether it passed, for the links probed so far."""
        return {
            link: link in self._passed
            for link in cf_project_ids
            if link in self._passed or link in self._failed
        }

    def check(
        self,
        cf_project_ids: Sequence[str],
        budget: TickBudget,
        faults: TickFaults,
        project_id: str,
    ) -> TickResult:
        """Probe each unprobed link; replay the fault of each failed one.

        A failed link is a recurrence of ``cf_probe_failed`` on every later tick,
        so the (deduplicated) escalation stays open for the lifetime.
        """
        for link in cf_project_ids:
            if link in self._passed:
                continue
            if link not in self._failed:
                result = probe_link(link, self._run, budget, self._timeout_seconds)
                if isinstance(result, ProbeCutOff):
                    return TickResult.CUT_OFF
                if isinstance(result, ProbePassed):
                    self._passed.add(link)
                    logger.info("CF link %s passed its two shape probes", link)
                    continue
                self._failed[link] = result.detail
                logger.warning("CF link %s failed its probe: %s", link, result.detail)
            faults.add(
                Fault(
                    FaultKind.CF_PROBE_FAILED,
                    f"project {project_id}, CF link {link}: {self._failed[link]}",
                )
            )
        return TickResult.COMPLETE
