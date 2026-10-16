"""The check standing table (D5) and the ``check`` payload conversion."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.store.check_models import (
    CHECK_EXAMINED_COUNT,
    CHECK_OUTCOME,
    CHECK_PAYLOAD_KEYS,
    CheckInput,
    CheckOutcome,
    CheckRecord,
    CheckStanding,
    check_from_payload,
    check_standing,
)
from amoeba.store.evidence_models import Provenance, RecordSource

Outcome = CheckOutcome
Standing = CheckStanding


@pytest.mark.parametrize(
    ("outcome", "examined_count", "standing"),
    [
        (Outcome.ERRORED, None, Standing.ERRORED),
        (Outcome.ERRORED, 0, Standing.ERRORED),
        (Outcome.ERRORED, 9, Standing.ERRORED),
        (Outcome.PASSED, None, Standing.UNATTESTED),
        (Outcome.FAILED, None, Standing.UNATTESTED),
        (Outcome.PASSED, 0, Standing.VACUOUS),
        (Outcome.FAILED, 0, Standing.VACUOUS),
        (Outcome.PASSED, 3, Standing.PASSED),
        (Outcome.FAILED, 3, Standing.FAILED),
    ],
)
def test_standing_follows_the_d5_table(
    outcome: CheckOutcome, examined_count: int | None, standing: CheckStanding
) -> None:
    assert check_standing(outcome, examined_count) is standing


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": "node-1",
        "name": "cf check",
        "outcome": "passed",
        "examined_count": 12,
        "examined": {"files": 12},
        "baseline_ref": "abc123",
        "upstream": "context-forge",
        "upstream_version": "1.2.3",
        "source": "command_output",
        "source_path": None,
    }
    payload.update(overrides)
    return payload


def test_a_full_payload_converts() -> None:
    check = check_from_payload("check-1", _payload())
    assert check == CheckInput(
        id="check-1",
        node_id="node-1",
        name="cf check",
        outcome=Outcome.PASSED,
        examined_count=12,
        examined={"files": 12},
        baseline_ref="abc123",
        provenance=Provenance(
            upstream="context-forge",
            upstream_version="1.2.3",
            source=RecordSource.COMMAND_OUTPUT,
            source_path=None,
        ),
    )


def test_the_payload_fixture_holds_exactly_the_payload_keys() -> None:
    assert set(_payload()) == CHECK_PAYLOAD_KEYS


def test_an_unknown_outcome_word_raises() -> None:
    with pytest.raises(ValueError, match=CHECK_OUTCOME):
        check_from_payload("check-1", _payload(outcome="pass"))


def test_a_null_examined_count_converts_to_none() -> None:
    assert check_from_payload("c", _payload(examined_count=None)).examined_count is None


def test_a_missing_examined_count_key_raises() -> None:
    payload = _payload()
    del payload[CHECK_EXAMINED_COUNT]
    with pytest.raises(ValueError, match=CHECK_EXAMINED_COUNT):
        check_from_payload("check-1", payload)


def test_a_record_standing_agrees_with_the_function() -> None:
    base = check_from_payload("check-1", _payload(examined_count=0))
    record = CheckRecord(
        **{field: getattr(base, field) for field in base.__dataclass_fields__},
        project_id="demo",
        recorded_seq=1,
        recorded_at=datetime(2026, 10, 15, tzinfo=UTC),
    )
    assert record.standing is check_standing(record.outcome, record.examined_count)
    assert record.standing is Standing.VACUOUS
