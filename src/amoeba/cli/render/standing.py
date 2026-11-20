"""The text of ``standing`` and ``withdraw`` (slice 230, D2, D3).

The first line says what happened and names the id; ``standing`` adds the reach. A
rejection is ``rejected: <code>: <detail>``, as for the other one-result commands.
"""

from __future__ import annotations

from amoeba.cli.render.simple import rejected_text
from amoeba.cli.render.text import indented
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingResult,
    WithdrawOutcome,
    WithdrawResult,
)
from amoeba.store.vocabulary import StandingReach

#: How a person reads reach ``all``.
EVERYTHING: str = "everything"


def reach_text(reach: StandingReach, program: str | None, member: str | None) -> str:
    """``everything``, ``program <id>`` or ``member <member>``."""
    match reach:
        case StandingReach.ALL:
            return EVERYTHING
        case StandingReach.PROGRAM:
            return f"program {program}"
        case StandingReach.MEMBER:
            return f"member {member}"


def render_standing(result: StandingResult) -> str:
    if result.outcome is StandingOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return rejected_text(code, result.problems)
    if result.reach is None:
        raise ValueError(f"a {result.outcome.value} standing result has no reach")
    reach = reach_text(result.reach, result.program, result.member)
    lines = [
        f"{result.outcome.value}: standing answer #{result.standing_id}",
        indented(f"reach: {reach}"),
    ]
    return "\n".join(lines) + "\n"


def render_withdraw(result: WithdrawResult) -> str:
    if result.outcome is WithdrawOutcome.REJECTED:
        code = None if result.rejection is None else result.rejection.value
        return rejected_text(code, result.problems)
    return f"{result.outcome.value}: standing answer #{result.standing_id}\n"
