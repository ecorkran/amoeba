"""Release notes: who is told of a release report, and what the note says (slice 243,
D5).

``report_release`` writes one note per consumer that can see the report in ``changes``,
inside its own transaction. The rule "can see" is ``visible_releases``, called and not
copied. Nothing here reads a clock, starts a process or calls ``cf``; the text is
composed from the stored report and the ids come from ``uuid4``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import uuid4

from amoeba.operations.names import OperationName
from amoeba.operations.note_room import make_room_for_note
from amoeba.operations.release_fields import FULL_HASH_LENGTHS, MAX_VERSION_LENGTH
from amoeba.operations.report_release_models import (
    MAX_CHANGED_LENGTH,
    MAX_TOUCHED_ITEM_LENGTH,
    MAX_TOUCHED_ITEMS,
    ReportOutcome,
)
from amoeba.store.models import Release
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.programs import pairs_provided_by
from amoeba.store.releases import visible_releases
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ConsumedMode

#: A release note's id is this followed by ``uuid4().hex``. A sender's id cannot hold a
#: colon (240 D2), so it never collides with one. Nothing parses it.
RELEASE_NOTE_ID_PREFIX: Final = "release:"

#: The outcomes that change what ``changes`` shows, so the ones that write notes.
NOTE_OUTCOMES: Final = frozenset(
    {
        ReportOutcome.RECORDED,
        ReportOutcome.VERSIONED,
        ReportOutcome.CORRECTED,
        ReportOutcome.WITHDRAWN,
    }
)

SUBJECT_TEMPLATE: Final = "Release report {outcome}: {headline}"
FIRST_LINE_TEMPLATE: Final = "A release report was {outcome}."
WITHDRAWN_LINE: Final = (
    "A release report was withdrawn and is to be disregarded; do not rely on it."
)
COMMIT_LINE: Final = "Commit: {commit}"
VERSION_LINE: Final = "Version: {version}"
NO_VERSION: Final = "none"
CHANGED_LINE: Final = "Changed: {changed}"
TOUCHED_LINE: Final = "Touched: {touched}"
TOUCHED_SEPARATOR: Final = "; "
CORRECTED_LINE: Final = "This replaces the earlier text of the report."
CLOSING_LINE: Final = f"`{OperationName.CHANGES.value}` holds the full record."


def release_note_recipients(
    transaction: Transaction,
    provider_id: str,
    outcome: ReportOutcome,
    report: Release,
    now: datetime,
) -> tuple[str, ...]:
    """The consumers that get a note for ``report``, by consumer id.

    A consumer gets one exactly when ``changes`` shows it the report. For a written
    report that is ``visible_releases`` with ``since`` at ``now`` (this event moved the
    report's time to ``now``). For a withdrawal the report must still be stored, and
    ``since`` is its own ``reported_at``: the consumers that could see it at all.

    Raises:
        ValueError: ``outcome`` writes no note.
    """
    if outcome not in NOTE_OUTCOMES:
        raise ValueError(f"a {outcome.value} report writes no release note")
    since = encode_timestamp(
        report.reported_at if outcome is ReportOutcome.WITHDRAWN else now
    )
    pairs = pairs_provided_by(transaction, provider_id)
    seen_by: dict[ConsumedMode, set[int]] = {
        mode: {
            release.seq
            for release in visible_releases(transaction, provider_id, mode, since)
        }
        for mode in {pair.consumed for pair in pairs}
    }
    return tuple(
        pair.consumer_id for pair in pairs if report.seq in seen_by[pair.consumed]
    )


def compose_release_note(
    outcome: ReportOutcome,
    commit: str,
    version: str | None,
    changed: str,
    touched: tuple[str, ...],
) -> tuple[str, str]:
    """The note's ``(subject, body)`` for a report, composed by Amoeba.

    A withdrawal carries the commit and version only: its report is to be disregarded.
    """
    version_text = NO_VERSION if version is None else version
    headline = commit if version is None else version
    subject = SUBJECT_TEMPLATE.format(outcome=outcome.value, headline=headline)
    identity = [
        COMMIT_LINE.format(commit=commit),
        VERSION_LINE.format(version=version_text),
    ]
    if outcome is ReportOutcome.WITHDRAWN:
        return subject, "\n".join([WITHDRAWN_LINE, *identity])
    lines = [
        FIRST_LINE_TEMPLATE.format(outcome=outcome.value),
        *identity,
        CHANGED_LINE.format(changed=changed),
        TOUCHED_LINE.format(touched=TOUCHED_SEPARATOR.join(touched)),
    ]
    if outcome is ReportOutcome.CORRECTED:
        lines.append(CORRECTED_LINE)
    lines.append(CLOSING_LINE)
    return subject, "\n".join(lines)


def _longest_body() -> int:
    """The longest body any outcome composes from a report with every field at its
    limit (the limits are ``report_release_models``'; the hash is the longest one)."""
    return max(
        len(
            compose_release_note(
                outcome,
                commit="c" * max(FULL_HASH_LENGTHS),
                version="v" * MAX_VERSION_LENGTH,
                changed="x" * MAX_CHANGED_LENGTH,
                touched=("t" * MAX_TOUCHED_ITEM_LENGTH,) * MAX_TOUCHED_ITEMS,
            )[1]
        )
        for outcome in NOTE_OUTCOMES
    )


#: The most a release note's body can hold, composed once from the report's own limits
#: and the template's text. ``send``'s ``body`` limit binds caller text, not this
#: (243 D5); a test composes the largest report and checks the body is within it.
MAX_RELEASE_NOTE_BODY_LENGTH: Final = _longest_body()


def write_release_notes(
    transaction: Transaction,
    provider_id: str,
    outcome: ReportOutcome,
    report: Release,
    now: datetime,
) -> tuple[str, ...]:
    """Write one note from the provider to each consumer that sees ``report``; the
    consumer ids. A provider with no consumers writes none.

    The recipients are found before anything is written, so for a withdrawal the
    report must not yet be deleted.
    """
    recipients = release_note_recipients(transaction, provider_id, outcome, report, now)
    if not recipients:
        return ()
    subject, body = compose_release_note(
        outcome, report.commit, report.version, report.changed, report.touched
    )
    for consumer_id in recipients:
        note = NewNote(
            message_id=f"{RELEASE_NOTE_ID_PREFIX}{uuid4().hex}",
            from_member=provider_id,
            to_member=consumer_id,
            to_program=None,
            subject=subject,
            body=body,
        )
        make_room_for_note(transaction, provider_id)
        insert_note(transaction, note, [consumer_id], now)
    return recipients
