"""Pre-dispatch checks: what a checkout and CF's gate must say before a launch (D5, D6).

Every rule here is pure. ``Ok`` carries the evidence a launch's journal entry records
as ``dispatch_check``; ``Block`` is a node block the planner turns into a
``BlockDispatch``. This module imports nothing from ``decide.py``: the action type
imports it, not the other way around.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.runner.faults import FaultKind


@dataclass(frozen=True)
class Ok:
    """The checkout and the gate allow the dispatch; ``evidence`` says on what basis."""

    evidence: Mapping[str, str | None]


@dataclass(frozen=True)
class Block:
    """The dispatch must not go ahead: block the node on a human, saying why."""

    fault_kind: FaultKind
    context: str
    payload: Mapping[str, object]


#: What the pre-dispatch checks decided for one candidate. A candidate with no entry
#: in the view's ``dispatch_checks`` has no result: its reads were cut off or failed.
type DispatchCheck = Ok | Block
