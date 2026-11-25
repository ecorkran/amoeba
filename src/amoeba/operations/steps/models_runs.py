"""``open_runs``'s models (262 D4, D9, D12)."""

from __future__ import annotations

from typing import Final

from amoeba.operations.steps.model_base import Step, StepModel


class OpenRunsRequest(StepModel):
    """No fields: the hub knows the calling machine."""


class OpenRunsReply(StepModel):
    """The calling machine's open questions' run ids and open answering run ids, and
    the hub's retention: what the client's sweep checks and its prune keeps."""

    run_ids: tuple[str, ...]
    answering_run_ids: tuple[str, ...]
    prune_after_days: int


OPEN_RUNS: Final = Step(
    "open_runs",
    OpenRunsRequest,
    OpenRunsReply,
    writes=False,
    keeps_result=False,
    needs_config=True,
)
