"""The text of ``list`` and ``status`` (slice 229, D2, D3): what needs the PM.

Sections, in this order, each left out when empty: **Waiting on you**, **Paused, not
handled**, **Unplaced runs**, **Problems**. With nothing in any of them it prints
``Nothing needs you.``. What this call closed comes next (the status document carries
it once). With ``settled`` given (``list --all``) every other run follows under its
member, then **Settled**. ``status`` uses this same renderer without ``settled``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.answering.values import AnsweredBy
from amoeba.cli.render.commands import (
    answer_command,
    dismiss_command,
    handle_pause_command,
    list_command,
)
from amoeba.cli.render.text import (
    SEPARATOR,
    command_line,
    how_long,
    indented,
    prose_line,
    was_cut,
)
from amoeba.operations.calls_log import CallEntry
from amoeba.operations.list_view import SettledEntry
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.status_models import (
    MemberStatus,
    RunEntry,
    StatusOutcome,
    StatusResult,
    UnplacedReason,
    UnplacedRunEntry,
    WaitingEntry,
    WaitingRunState,
)
from amoeba.operations.status_runs import HANDLED_BY_HANDLE_PAUSE
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import ClosedReason

QUESTION_PREFIX: Final = indented("question: ", 2)
NOTHING_NEEDS_YOU: Final = "Nothing needs you."

#: What a run paused in each class that ``handle-pause`` acts on has come to.
PAUSE_MEANING: Final = {
    PauseClass.UNHANDLED: "the hook did not run",
    PauseClass.CLAIM_STALE: "answering stopped part-way",
    PauseClass.ANSWERED_UNRESUMED: "an answer was recorded but not delivered",
}
#: Classes whose newest calls-log line shows why a hook missed.
SHOWS_LAST_CALL: Final = frozenset({PauseClass.UNHANDLED, PauseClass.CLAIM_STALE})
#: One line on how an unplaced run leaves the list; short enough not to be cut.
NO_AMOEBA_RECORD: Final = (
    "Amoeba has no record of it; it leaves the list when Squadron stops listing it"
)
CLEARS_ON_LISTING: Final = {
    UnplacedReason.LOOKUP_FAILED: "clears once `cf` answers; run this again:",
    UnplacedReason.NO_DIRECTORY: NO_AMOEBA_RECORD,
    UnplacedReason.DIRECTORY_MISSING: NO_AMOEBA_RECORD,
}
RUN_STATE_TEXT: Final = {
    WaitingRunState.AT_PAUSE: None,
    WaitingRunState.MOVED_ON: "the run has moved on",
    WaitingRunState.NOT_LISTED: "Squadron no longer lists the run",
}
ENDED_TEXT: Final = {
    AnsweredBy.PM: "answered by you",
    AnsweredBy.ANSWERER: "answered automatically",
    ClosedReason.DISMISSED: "dismissed",
    ClosedReason.RUN_MOVED_ON: "closed: the run moved on",
    ClosedReason.RUN_GONE: "closed: Squadron no longer knows the run",
}
WAITING_NOTES: Final = (
    "A fixed rules file or a raised size cap helps the next question, not these.",
    "A waiting question clears with an answer or a dismiss, or closes when its run "
    "moves on.",
)


def render_waiting(
    result: StatusResult,
    *,
    now: datetime,
    settled: tuple[SettledEntry, ...] | None = None,
) -> str:
    """The text of a ``status`` result, and of ``list`` with ``settled`` for ``all``."""
    if result.outcome is StatusOutcome.REJECTED:
        code = "" if result.rejection is None else result.rejection.value
        lines = [prose_line(f"rejected: {code}: ", p) for p in result.problems]
        return "\n".join(lines) + "\n"
    members = [member for entry in result.programs for member in entry.members]
    needs = [
        _waiting(members, now),
        _paused(members),
        _unplaced(result.unplaced_runs),
        _problems(result),
    ]
    sections = [section for section in needs if section]
    if not sections:
        sections.append([NOTHING_NEEDS_YOU])
    sections.extend(section for section in [_closed_now(result)] if section)
    if settled is not None:
        sections.extend(
            section for section in (_other_runs(members), _settled(settled)) if section
        )
    return "\n\n".join("\n".join(section) for section in sections) + "\n"


def _waiting(members: list[MemberStatus], now: datetime) -> list[str]:
    lines: list[str] = []
    cut_question = False
    for member in members:
        for entry in member.waiting_on_pm:
            lines.extend(_waiting_entry(member.member.name, entry, now))
            cut_question |= was_cut(QUESTION_PREFIX, entry.question)
    if not lines:
        return []
    section = ["Waiting on you", *lines, *(indented(note) for note in WAITING_NOTES)]
    if cut_question:
        section.append(indented("A question cut with … is whole in:"))
        section.append(command_line(list_command(as_json=True)))
    return section


def _waiting_entry(name: str, entry: WaitingEntry, now: datetime) -> list[str]:
    key = QuestionKey(entry.run_id, entry.paused_at)
    reason = "(none recorded)"
    if entry.waiting_reason is not None:
        reason = entry.waiting_reason.value
        if entry.waiting_detail:
            reason += f": {entry.waiting_detail}"
    lines = [
        indented(SEPARATOR.join((name, entry.run_id, how_long(entry.since, now)))),
        prose_line(indented("reason: ", 2), reason),
    ]
    run_state = RUN_STATE_TEXT[entry.run_state]
    if run_state is not None:
        detail = f" ({entry.detail})" if entry.detail else ""
        lines.append(prose_line(indented("run: ", 2), run_state + detail))
    lines += [
        prose_line(QUESTION_PREFIX, entry.question),
        indented("answer it, or close it without an answer:", 2),
        command_line(answer_command(key), 3),
        command_line(dismiss_command(key), 3),
    ]
    return lines


def _paused(members: list[MemberStatus]) -> list[str]:
    lines: list[str] = []
    for member in members:
        for run in member.runs:
            if _is_unhandled(run):
                lines.extend(_paused_entry(member.member.name, run))
    return ["Paused, not handled", *lines] if lines else []


def _is_unhandled(run: RunEntry) -> bool:
    return isinstance(run.pause, PauseClass) and run.pause in HANDLED_BY_HANDLE_PAUSE


def _paused_entry(name: str, run: RunEntry) -> list[str]:
    assert isinstance(run.pause, PauseClass)
    lines = [
        indented(SEPARATOR.join((name, run.run_id, PAUSE_MEANING[run.pause]))),
    ]
    if run.pause in SHOWS_LAST_CALL and run.last_call is not None:
        lines.append(prose_line(indented("last call: ", 2), _call_text(run.last_call)))
    directory = None if run.next is None else run.next.directory
    lines.append(indented("run it in the run's checkout:", 2))
    lines.append(command_line(handle_pause_command(run.run_id, directory), 3))
    return lines


def _call_text(call: CallEntry) -> str:
    when = call.at.strftime("%Y-%m-%d %H:%M")
    if call.error is not None:
        what = f"error {call.error}"
    else:
        what = (call.outcome or "") + (f" ({call.reason})" if call.reason else "")
    return " ".join(part for part in (when, what, call.detail) if part)


def _unplaced(runs: tuple[UnplacedRunEntry, ...]) -> list[str]:
    lines: list[str] = []
    for run in runs:
        lines.append(indented(SEPARATOR.join((run.run_id, run.reason.value))))
        if run.detail:
            lines.append(prose_line(indented("detail: ", 2), run.detail))
        lines.append(prose_line(indented("", 2), CLEARS_ON_LISTING[run.reason]))
        if run.reason is UnplacedReason.LOOKUP_FAILED:
            lines.append(command_line(list_command(), 3))
    return ["Unplaced runs", *lines] if lines else []


def _problems(result: StatusResult) -> list[str]:
    found = [
        *([] if result.sweep_problem is None else [result.sweep_problem]),
        *result.file_problems,
        *result.problems,
    ]
    return ["Problems", *(prose_line(indented(""), p) for p in found)] if found else []


def _closed_now(result: StatusResult) -> list[str]:
    lines: list[str] = []
    for item in result.closed_now:
        how = item.closed_reason.value if item.closed_reason else "answer not delivered"
        lines.append(
            prose_line(
                indented(f"{item.member.name}{SEPARATOR}{item.run_id}{SEPARATOR}"),
                f"{how}: {item.closed_detail}",
            )
        )
    return ["Closed by this check", *lines] if lines else []


def _other_runs(members: list[MemberStatus]) -> list[str]:
    lines: list[str] = []
    for member in members:
        others = [run for run in member.runs if not _is_unhandled(run)]
        if not others:
            continue
        lines.append(indented(member.member.name))
        lines.extend(_run_line(run) for run in others)
    return ["Other runs", *lines] if lines else []


def _run_line(run: RunEntry) -> str:
    pause = run.pause.value if run.pause is not None else None
    parts = [run.run_id, run.status, *([pause] if pause else [])]
    return prose_line(indented("", 2), SEPARATOR.join(parts))


def _settled(entries: tuple[SettledEntry, ...]) -> list[str]:
    lines = [line for entry in entries for line in _settled_entry(entry)]
    return ["Settled", *lines] if lines else []


def _settled_entry(entry: SettledEntry) -> list[str]:
    name = entry.member_name or f"{entry.member_id} (not in Context Forge)"
    when = entry.settled_at.strftime("%Y-%m-%d")
    return [
        indented(SEPARATOR.join((when, name, ENDED_TEXT[entry.ended]))),
        prose_line(indented("question: ", 2), entry.question),
    ]
