"""``open_runs``: what the calling machine has open (262 D4, D9, D12).

Its open questions' run ids (the status sweep checks the run file of each the listing
does not show, and the prune keeps the resume logs of each) and its open answering run
ids (the prune keeps their scratch and logs), and ``prune_after_days`` from the hub's
config. Only the calling machine's rows: another machine's files are its own.
"""

from __future__ import annotations

from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models_runs import OpenRunsReply, OpenRunsRequest
from amoeba.store.machines import acting_machine_id
from amoeba.store.question_closing import open_rows_of_machine


def open_runs(context: StepContext, request: OpenRunsRequest) -> OpenRunsReply:
    del request  # no fields
    config = context.require_config()
    rows = open_rows_of_machine(
        context.transaction, acting_machine_id(context.transaction)
    )
    return OpenRunsReply(
        run_ids=tuple(sorted({row.key.run_id for row in rows})),
        answering_run_ids=tuple(
            sorted({row.answering_run_id for row in rows if row.answering_run_id})
        ),
        prune_after_days=config.prune_after_days,
    )
