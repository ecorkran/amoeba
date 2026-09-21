"""Pin the journal vocabularies and the entry model.

These run before any SQL depends on them. The member-set assertions are written
out literally rather than derived from the enums: deriving the expectation from
the thing under test makes the assertion vacuous, so adding or renaming a member
must fail here and be a deliberate edit.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from amoeba.store.journal_models import (
    REQUIRED_PARAMETER_KEYS,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)


def test_command_kind_members_are_exactly_the_closed_set() -> None:
    """The command vocabulary is closed; a new kind is a deliberate change."""
    assert {kind.value for kind in CommandKind} == {"cf_write", "sq_run"}


def test_journal_outcome_members_are_exactly_the_closed_set() -> None:
    """Two issuer-written outcomes and three recovery-written ones."""
    assert {outcome.value for outcome in JournalOutcome} == {
        "completed",
        "failed",
        "adopted",
        "not_applied",
        "unknown",
    }


def test_journal_resolver_members_are_exactly_the_closed_set() -> None:
    """Only the issuer and recovery ever close an entry."""
    assert {resolver.value for resolver in JournalResolver} == {"issuer", "recovery"}


def test_vocabularies_are_string_enums() -> None:
    """``StrEnum`` so stored values read as plain strings under inspection."""
    assert CommandKind.SQ_RUN == "sq_run"
    assert JournalOutcome.ADOPTED == "adopted"
    assert JournalResolver.RECOVERY == "recovery"


def test_every_command_kind_declares_required_parameter_keys() -> None:
    """A kind cannot be added without saying what recovery needs from it."""
    assert set(REQUIRED_PARAMETER_KEYS) == set(CommandKind)


def test_required_parameter_keys_match_the_design() -> None:
    """The keys each kind's observer matches on, per the LLD."""
    assert REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN] == frozenset(
        {"pipeline", "params"}
    )
    assert REQUIRED_PARAMETER_KEYS[CommandKind.CF_WRITE] == frozenset(
        {"project", "expected"}
    )


def _entry(outcome: JournalOutcome | None = None) -> JournalEntry:
    """Build an entry, defaulting the fields a test does not care about."""
    return JournalEntry(
        id="entry-1",
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.SQ_RUN,
        parameters={"pipeline": "p6", "params": {"slice": "102"}},
        issued_at=datetime(2026, 9, 21, tzinfo=UTC),
        outcome=outcome,
    )


def test_journal_entry_is_frozen() -> None:
    """Entries are immutable transfer objects, as every model in this package is."""
    entry = _entry()

    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.outcome = JournalOutcome.ADOPTED  # type: ignore[misc]


def test_is_resolved_is_false_without_an_outcome() -> None:
    """An entry with no outcome is exactly what recovery reconciles."""
    assert _entry().is_resolved is False


@pytest.mark.parametrize("outcome", list(JournalOutcome))
def test_is_resolved_is_true_for_every_outcome(outcome: JournalOutcome) -> None:
    """Every outcome closes the entry — including ``unknown``."""
    assert _entry(outcome=outcome).is_resolved is True


def test_is_resolved_stores_no_redundant_flag() -> None:
    """``is_resolved`` derives from ``outcome``; it is not a separate field."""
    field_names = {field.name for field in dataclasses.fields(JournalEntry)}

    assert "is_resolved" not in field_names


def test_entry_carries_the_contract_fields() -> None:
    """The field set the API contract names, and nothing implicit beyond it."""
    assert {field.name for field in dataclasses.fields(JournalEntry)} == {
        "id",
        "project_id",
        "node_id",
        "kind",
        "parameters",
        "issued_at",
        "outcome",
        "result",
        "resolved_at",
        "resolved_by",
    }
