"""``run_step``: the one entry the hub and the local way both use (262 D3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from pydantic import ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models import STEP_MODELS, StepModel
from amoeba.operations.steps.pause import (
    question_claim_held,
    question_hold,
    question_insert,
    question_replace_claim,
    question_wait,
)
from amoeba.operations.steps.resume import resume_claim, resume_read, resume_record
from amoeba.operations.steps.settle import question_settle
from amoeba.operations.steps.sources import pause_sources
from amoeba.store.store import Store

type StepFunction = Callable[[StepContext, Any], StepModel]

#: Each step's function; ``STEP_MODELS`` holds its models and how it runs.
STEP_FUNCTIONS: Final[dict[str, StepFunction]] = {
    "resume_claim": resume_claim,
    "resume_read": resume_read,
    "resume_record": resume_record,
    "question_insert": question_insert,
    "question_hold": question_hold,
    "question_claim_held": question_claim_held,
    "question_replace_claim": question_replace_claim,
    "question_wait": question_wait,
    "question_settle": question_settle,
    "pause_sources": pause_sources,
}


class UnknownStepError(Exception):
    """A step name that is not in ``STEP_MODELS`` (a caller bug: the hub refuses it)."""


class StepDocumentError(Exception):
    """A step document that does not fit its request model."""


@dataclass(frozen=True)
class StepEdges:
    """What a step reads from outside the store."""

    clock: Callable[[], datetime]
    #: Called only for a step whose ``STEP_MODELS`` row needs config.
    load_config: Callable[[], UserConfig]


def run_step(name: str, store: Store, document: object, edges: StepEdges) -> StepModel:
    """Validate ``document``, run the step in its own transaction, return its reply.

    A writing step runs in ``store.write()`` and any other in ``store.read()``; inside
    the hub's call scope either is a savepoint, so the step and its kept result commit
    together.

    Raises:
        UnknownStepError: ``name`` is not a step.
        StepDocumentError: ``document`` does not validate against the request model.
        ConfigError: The step needs the config and it cannot be loaded.
        StoreError: The store cannot be used.
    """
    spec = STEP_MODELS.get(name)
    if spec is None:
        raise UnknownStepError(f"{name!r} is not a step")
    try:
        request = spec.request.model_validate(document)
    except ValidationError as error:
        raise StepDocumentError(f"step {name}: {error}") from error
    config = edges.load_config() if spec.needs_config else None
    function = STEP_FUNCTIONS[name]
    transaction_scope = store.write() if spec.writes else store.read()
    with transaction_scope as transaction:
        reply = function(StepContext(transaction, edges.clock(), config), request)
    return reply
