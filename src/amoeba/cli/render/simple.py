"""The text of the one-result commands (slice 229, D2): answer, decisions, mark-read,
dismiss, retract and handle-pause.

The first line says what happened; a rejection is ``rejected: <code>: <detail>``.
Prose is cut to the width and commands are whole on their own line.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.answering.values import AnsweredBy
from amoeba.cli.render.commands import mark_read_command
from amoeba.cli.render.text import SEPARATOR, command_line, indented, prose_line
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.decisions_models import (
    DecisionsOutcome,
    DecisionsRecord,
    DecisionsResult,
)
from amoeba.operations.dismiss import DismissOutcome, DismissResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.pause_models import HandlePauseOutcome, HandlePauseResult
from amoeba.operations.retract import RetractOutcome, RetractResult
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import ResumeOutcome


def _rejected(code: str | None, problems: Sequence[str]) -> str:
    label = code or "rejected"
    lines = [prose_line(f"rejected: {label}: ", problem) for problem in problems]
    return "\n".join(lines or [f"rejected: {label}"]) + "\n"


def _key_text(key: QuestionKey | None) -> str:
    return "" if key is None else f"{key.run_id} at {key.paused_at}"


def render_answer(result: AnswerResult) -> str:
    if result.outcome is AnswerOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return _rejected(code, result.problems)
    lines = ["recorded", indented(f"question: {_key_text(result.key)}")]
    if result.answer_seq is not None:
        lines.append(indented(f"answer: #{result.answer_seq}"))
    if result.resume is not None:
        lines.append(indented(f"resume: {result.resume.outcome.value}"))
        if result.resume.outcome is not ResumeOutcome.RESUMED and result.resume.detail:
            lines.append(prose_line(indented("detail: ", 2), result.resume.detail))
    return "\n".join(lines) + "\n"


def render_dismiss(result: DismissResult) -> str:
    if result.outcome is DismissOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return _rejected(code, result.problems)
    lines = [f"{result.outcome.value}: {_key_text(result.key)}"]
    if result.closed_reason is not None:
        lines.append(indented(f"closed: {result.closed_reason.value}"))
    if result.closed_detail:
        lines.append(prose_line(indented("detail: "), result.closed_detail))
    return "\n".join(lines) + "\n"


def render_retract(result: RetractResult) -> str:
    if result.outcome is RetractOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return _rejected(code, result.problems)
    lines = [f"{result.outcome.value}: answer #{result.answer_seq}"]
    if result.key is not None:
        lines.append(indented(f"question: {_key_text(result.key)}"))
    return "\n".join(lines) + "\n"


def render_mark_read(result: MarkReadResult) -> str:
    if result.outcome is MarkReadOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return _rejected(code, result.problems)
    if result.outcome is MarkReadOutcome.MOVED:
        return f"moved: marker {result.previous} -> {result.current}\n"
    return f"unchanged: marker at {result.current}\n"


def render_decisions(result: DecisionsResult) -> str:
    if result.outcome is DecisionsOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return _rejected(code, result.problems)
    if not result.records:
        return f"no answers to show (marker at {result.marker})\n"
    count = len(result.records)
    lines = [f"{count} answer{'s' if count != 1 else ''} (marker at {result.marker})"]
    for record in result.records:
        lines.extend(_record(record))
    if result.read_through is not None:
        lines.append("when you have read them:")
        lines.append(command_line(mark_read_command(result.read_through), 1))
    return "\n".join(lines) + "\n"


def _record(record: DecisionsRecord) -> list[str]:
    who = "you" if record.answered_by is AnsweredBy.PM else "the answerer"
    when = record.recorded_at.strftime("%Y-%m-%d %H:%M")
    head = SEPARATOR.join(
        (f"#{record.seq}", when, record.member.name, f"answered by {who}")
    )
    lines = [
        indented(head),
        prose_line(indented("question: ", 2), record.question),
        prose_line(indented("answer: ", 2), record.answer),
    ]
    if record.retracted_at is not None:
        lines.append(
            prose_line(indented("retracted: ", 2), record.retract_reason or "")
        )
    return lines


def render_handle_pause(result: HandlePauseResult) -> str:
    """One line, nothing parses it: the hook's own output."""
    detail = f": {result.detail}" if result.detail else ""
    match result.outcome:
        case HandlePauseOutcome.RESUMED:
            line = "answered" + detail
        case HandlePauseOutcome.REFUSED:
            line = "answered, resume refused" + detail
        case HandlePauseOutcome.NOT_DELIVERED:
            line = "answered, not delivered" + detail
        case HandlePauseOutcome.WAITING_ON_PM:
            reason = (
                "" if result.waiting_reason is None else result.waiting_reason.value
            )
            line = f"waiting_on_pm: {reason}{detail}"
        case HandlePauseOutcome.SKIPPED:
            reason = "" if result.skip_reason is None else result.skip_reason.value
            line = f"skipped: {reason}{detail}"
        case HandlePauseOutcome.SUPERSEDED:
            line = "superseded" + detail
    return prose_line("", line) + "\n"
