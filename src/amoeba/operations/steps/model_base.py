"""The base every step model and the typed step handle are made from (262 D3).

Apart from ``models`` so the step modules that define their models (``models_pause``,
``models_resume``) and ``models`` itself, which builds the one table from all of them,
do not import each other in a ring.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


class StepModel(BaseModel):
    """Base of every step document: closed (no unknown field) and frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class Step[Request: StepModel, Reply: StepModel]:
    """A step: its name, its two models and how the hub runs it. The type
    parameters let ``Steps.run`` return the reply type of the request it was given."""

    name: str
    request: type[Request]
    reply: type[Reply]
    #: Its transaction is a write; this is all ``run_step`` reads.
    writes: bool
    #: Through the door its reply is kept for a repeated call. A step that writes
    #: but is safe to run twice (a session tick or end) keeps none.
    keeps_result: bool
    #: It reads the hub's ``config.yaml``. The steps that record an end (a resume's
    #: outcome, a wake's pid and end) load none on purpose: a broken config must not
    #: stop an outcome from being recorded (D10).
    needs_config: bool
