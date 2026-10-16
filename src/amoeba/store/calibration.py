"""The descriptive judge calibration report (107, D3). Read-only.

One row per ``(review_type, model)`` over judge samples. It counts and describes
each group's samples on their own: no field compares samples with each other,
within an invocation or across models, and there is no threshold or
recommendation. The report must not be consumed as agreement evidence;
agreement is initiative 140's computation (GitHub issues #4 and #6).

Mixed into ``Store``; it issues only SELECTs and reads ``verdicts`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from typing import Final

from amoeba.store import sql_evidence
from amoeba.store._base import StoreBase
from amoeba.store.evidence_models import ReviewVerdict, VerdictRecord, VerdictStanding
from amoeba.store.mapping_evidence import map_verdict


@dataclass(frozen=True, kw_only=True)
class CalibrationRow:
    """One group's samples, counted. ``None`` scores mean no sample had one."""

    review_type: str
    model: str
    samples: int
    invocations: int
    pass_count: int
    concerns_count: int
    fail_count: int
    unknown_count: int
    provider_failures: int
    score_min: float | None
    score_mean: float | None
    score_max: float | None


#: ``(CalibrationRow field, listing/JSON column)``, defined once. The columns are
#: the D3 names; ``pass`` is not a usable Python field name.
CALIBRATION_COLUMNS: Final = (
    ("review_type", "review_type"),
    ("model", "model"),
    ("samples", "samples"),
    ("invocations", "invocations"),
    ("pass_count", "pass"),
    ("concerns_count", "concerns"),
    ("fail_count", "fail"),
    ("unknown_count", "unknown"),
    ("provider_failures", "provider_failures"),
    ("score_min", "score_min"),
    ("score_mean", "score_mean"),
    ("score_max", "score_max"),
)


def _count(samples: list[VerdictRecord], verdict: ReviewVerdict) -> int:
    return sum(1 for sample in samples if sample.verdict is verdict)


def _row(review_type: str, model: str, samples: list[VerdictRecord]) -> CalibrationRow:
    scores = [sample.score for sample in samples if sample.score is not None]
    return CalibrationRow(
        review_type=review_type,
        model=model,
        samples=len(samples),
        invocations=len({sample.judge_invocation_id for sample in samples}),
        pass_count=_count(samples, ReviewVerdict.PASS),
        concerns_count=_count(samples, ReviewVerdict.CONCERNS),
        fail_count=_count(samples, ReviewVerdict.FAIL),
        unknown_count=_count(samples, ReviewVerdict.UNKNOWN),
        provider_failures=sum(
            1 for s in samples if s.standing is VerdictStanding.PROVIDER_FAILURE
        ),
        score_min=min(scores) if scores else None,
        score_mean=sum(scores) / len(scores) if scores else None,
        score_max=max(scores) if scores else None,
    )


class CalibrationOperations(StoreBase):
    """Read the judge calibration report."""

    def calibration(self, project_id: str) -> list[CalibrationRow]:
        """One row per ``(review_type, model)`` over a project's judge samples.

        Groups on the stored values as given, ordered by review type, then model.
        """
        rows = self._execute(sql_evidence.SELECT_JUDGE_SAMPLES, (project_id,))
        samples = [map_verdict(row, ()) for row in rows.fetchall()]
        return [
            _row(review_type, model, list(group))
            for (review_type, model), group in groupby(
                samples, key=lambda sample: (sample.review_type, sample.model)
            )
        ]
