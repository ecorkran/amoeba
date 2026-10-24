"""Reissuing a launch that never started (D9).

Until the reissue path lands, a step to be reissued is blocked on a human rather than
launched, so a new run is never started over one that may have started.
"""

from __future__ import annotations

from typing import Final

from amoeba.runner.decide import LaunchRun
from amoeba.runner.ingest.outcome import (
    PAYLOAD_REASON,
    PAYLOAD_RUN_ID,
    BlockPlan,
)
from amoeba.runner.ingest.record import block_once
from amoeba.store import BlockedKind, Store

#: The reason of the block, and the entry key it names.
REASON_REISSUE_NOT_SUPPORTED: Final = "reissue_not_supported"
PAYLOAD_REISSUE_OF: Final = "reissue_of"


def block_unsupported_reissue(store: Store, action: LaunchRun) -> None:
    """Block the step on a human, naming the ``not_applied`` entry."""
    block_once(
        store,
        action.node_id,
        BlockPlan(
            BlockedKind.HUMAN,
            (
                f"entry {action.reissue_of} never started run {action.run_id}, and "
                "reissuing it is not supported yet"
            ),
            {
                PAYLOAD_REASON: REASON_REISSUE_NOT_SUPPORTED,
                PAYLOAD_RUN_ID: action.run_id,
                PAYLOAD_REISSUE_OF: action.reissue_of,
            },
        ),
    )
