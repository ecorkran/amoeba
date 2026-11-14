"""Which renderer a result gets (slice 229, D2), chosen by the result's type.

``status`` and the default view of ``list`` share one renderer, so what a person reads
cannot disagree between them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from amoeba.cli.render.registration import render_registration
from amoeba.cli.render.registry import (
    render_dependencies,
    render_members,
    render_programs,
)
from amoeba.cli.render.releases import render_changes, render_report_release
from amoeba.cli.render.simple import (
    render_answer,
    render_decisions,
    render_dismiss,
    render_mark_read,
    render_retract,
)
from amoeba.cli.render.waiting import render_waiting
from amoeba.operations.answer import AnswerResult
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.decisions_models import DecisionsResult
from amoeba.operations.dismiss import DismissResult
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
)
from amoeba.operations.list_view import ListResult
from amoeba.operations.mark_read import MarkReadResult
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.operations.retract import RetractResult
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.status_models import StatusResult
from amoeba.wiring import OperationResult


def render_result(
    result: OperationResult,
    *,
    now: datetime,
    names: Mapping[str, str],
    default_rules: tuple[str, ...],
    removing: bool = False,
) -> str:
    """The text of ``result``.

    ``names``, ``default_rules`` and ``removing`` are for ``add`` and ``rm`` (Context
    Forge names by id, the config's default rules, and whether it was ``rm``); the
    others ignore them.
    """
    match result:
        case SetUpResult():
            return render_registration(
                result, names=names, default_rules=default_rules, removing=removing
            )
        case ListResult():
            return render_waiting(result.status, now=now, settled=result.settled)
        case StatusResult():
            return render_waiting(result, now=now)
        case ProgramsView():
            return render_programs(result)
        case MembersView():
            return render_members(result)
        case DependenciesView():
            return render_dependencies(result)
        case AnswerResult():
            return render_answer(result)
        case DecisionsResult():
            return render_decisions(result)
        case MarkReadResult():
            return render_mark_read(result)
        case DismissResult():
            return render_dismiss(result)
        case RetractResult():
            return render_retract(result)
        case ReportReleaseResult():
            return render_report_release(result)
        case ChangesResult():
            return render_changes(result)
