"""Every value the ``verdict`` envelope accepts, the store's payload reader accepts.

The key names are pinned in ``tests/inbox/test_envelope.py``; this pins the
types. Each field of ``VerdictPayload`` and ``FindingPayload`` is driven through
``build_envelope`` with every sample its annotation has, then read back by
``verdict_from_payload``. A divergence would otherwise pass the envelope and
fail inside ``apply_submission``, parking the file in ``failed/`` instead of
quarantining it. A field with an annotation missing from ``_SAMPLES`` fails
here until its samples are added.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from amoeba.inbox.envelope import build_envelope
from amoeba.inbox.evidence_payloads import FindingPayload, VerdictPayload
from amoeba.store import (
    FindingSeverity,
    RecordSource,
    ReviewVerdict,
    SubmissionKind,
    VerdictDerivation,
)
from amoeba.store.verdict_payload import verdict_from_payload

_SAMPLES: dict[object, tuple[object, ...]] = {
    str: ("text",),
    str | None: ("text", None),
    bool: (True, False),
    bool | None: (True, False, None),
    int | None: (7, None),
    float | None: (0.5, 3, None),
    dict[str, object] | None: ({"a": 1, "b": [True]}, None),
    ReviewVerdict: (*(m.value for m in ReviewVerdict), "concerns"),
    FindingSeverity: (*(m.value for m in FindingSeverity), "CONCERN"),
    VerdictDerivation: tuple(m.value for m in VerdictDerivation),
    RecordSource: tuple(m.value for m in RecordSource),
}


def _cases(model: type[FindingPayload | VerdictPayload]) -> list[tuple[str, object]]:
    return [
        (name, sample)
        for name, field in model.model_fields.items()
        if field.annotation != list[FindingPayload]
        for sample in _SAMPLES[field.annotation]
    ]


def _first_samples(model: type[FindingPayload | VerdictPayload]) -> dict[str, object]:
    return {
        name: _SAMPLES[field.annotation][0]
        for name, field in model.model_fields.items()
        if field.annotation != list[FindingPayload]
    }


def _read_back(payload: Mapping[str, object]) -> None:
    envelope = build_envelope(
        submission_id="s1",
        project_id="demo",
        kind=SubmissionKind.VERDICT,
        submitted_by="judge",
        submitted_at=datetime(2026, 9, 27, tzinfo=UTC),
        payload=payload,
    )
    verdict_from_payload(envelope.id, envelope.payload)


@pytest.mark.parametrize(("name", "sample"), _cases(VerdictPayload))
def test_every_verdict_field_value_survives_the_store_reader(
    name: str, sample: object
) -> None:
    finding = _first_samples(FindingPayload)
    _read_back({**_first_samples(VerdictPayload), "findings": [finding], name: sample})


@pytest.mark.parametrize(("name", "sample"), _cases(FindingPayload))
def test_every_finding_field_value_survives_the_store_reader(
    name: str, sample: object
) -> None:
    finding = {**_first_samples(FindingPayload), name: sample}
    _read_back({**_first_samples(VerdictPayload), "findings": [finding]})


def test_an_empty_findings_list_survives_the_store_reader() -> None:
    _read_back({**_first_samples(VerdictPayload), "findings": []})
