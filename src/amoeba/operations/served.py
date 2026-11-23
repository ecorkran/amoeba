"""The six operations the door serves, run by one function (slice 260, D11).

``run_served`` is used by the local way (``wiring``) and by the hub, so the two never
differ in what an operation does. What an operation reads from outside the store is in
``ServedEdges``: the clock and the config. Names and member references are store reads
(slice 261, D6).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from typing import Final

from pydantic import BaseModel, TypeAdapter

from amoeba.config.user_config import UserConfig
from amoeba.operations.decisions import DecisionsResult, decisions
from amoeba.operations.dismiss import DismissResult, dismiss
from amoeba.operations.mark_read import MarkReadResult, mark_read
from amoeba.operations.names import OperationName
from amoeba.operations.retract import RetractResult, retract
from amoeba.operations.standing import standing
from amoeba.operations.standing_models import StandingResult, WithdrawResult
from amoeba.operations.withdraw import withdraw
from amoeba.store.store import Store

type ServedResult = (
    DecisionsResult
    | MarkReadResult
    | DismissResult
    | RetractResult
    | StandingResult
    | WithdrawResult
)


@dataclass(frozen=True)
class ServedEdges:
    """What the served operations read from outside the store."""

    clock: Callable[[], datetime]
    #: Called only by an operation that needs config (``standing``).
    load_config: Callable[[], UserConfig]


type _Runner = Callable[[Store, object, ServedEdges], ServedResult]


def _decisions(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return decisions(store, document)


def _mark_read(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return mark_read(store, document)


def _dismiss(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return dismiss(store, document, clock=edges.clock)


def _retract(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return retract(store, document, clock=edges.clock)


def _standing(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return standing(
        store,
        document,
        max_chars=edges.load_config().passages_max_chars,
        now=edges.clock(),
    )


def _withdraw(store: Store, document: object, edges: ServedEdges) -> ServedResult:
    return withdraw(store, document, now=edges.clock())


@dataclass(frozen=True)
class ServedOperation:
    """What the door needs to know about one served operation: how to run it and the
    type its result document is read back as."""

    run: _Runner
    result_type: type[ServedResult]
    #: Whether the operation reads ``config.yaml``; the hub loads it before the call
    #: scope, so a missing file is a refusal that costs no write lock.
    needs_config: bool = False


#: The one registry: each served operation's name to its runner and result type.
#: To serve a new operation, add (1) its name to ``wire.protocol.SERVED_OPERATIONS``,
#: and to ``WRITING_CALLS`` and ``UNKNOWN_ADVICE`` there when it writes, (2) an entry
#: here, and (3) its type to ``ServedResult``. ``tests/operations/test_served.py`` and
#: ``tests/wire/test_protocol.py`` fail, naming what is missing, when they disagree.
SERVED: Final[dict[str, ServedOperation]] = {
    OperationName.DECISIONS: ServedOperation(_decisions, DecisionsResult),
    OperationName.MARK_READ: ServedOperation(_mark_read, MarkReadResult),
    OperationName.DISMISS: ServedOperation(_dismiss, DismissResult),
    OperationName.RETRACT: ServedOperation(_retract, RetractResult),
    OperationName.STANDING: ServedOperation(
        _standing, StandingResult, needs_config=True
    ),
    OperationName.WITHDRAW: ServedOperation(_withdraw, WithdrawResult),
}


def _served(name: str) -> ServedOperation:
    operation = SERVED.get(name)
    if operation is None:
        raise ValueError(f"{name} is not a served operation")
    return operation


def run_served(
    name: str, store: Store, document: object, edges: ServedEdges
) -> ServedResult:
    """Run the served operation ``name`` on ``document``.

    Raises:
        ValueError: ``name`` is not a served operation.
    """
    return _served(name).run(store, document, edges)


def result_from_document(name: str, document: dict[str, object]) -> ServedResult:
    """The typed result of the served operation ``name``, rebuilt from its
    ``result_document`` form: the door's reply becomes the value the local way
    returns, so the CLI's renderers and exit codes need no second path.

    Raises:
        ValueError: ``name`` is not a served operation, or ``document`` is not that
            operation's result (pydantic's ``ValidationError`` is a ``ValueError``).
    """
    return TypeAdapter(_served(name).result_type).validate_python(document)


def result_document(result: object) -> dict[str, object]:
    """``result`` as the JSON document both doors give: enums are strings."""
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if is_dataclass(result) and not isinstance(result, type):
        document: dict[str, object] = json.loads(json.dumps(asdict(result)))
        return document
    raise TypeError(f"not a result: {type(result).__name__}")
