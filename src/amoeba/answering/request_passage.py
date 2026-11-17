"""The ``request_result`` passage: a request's reply given to the answering run
(slice 242, D5).

Plain fields in, so ``answering`` imports nothing from ``store``. The passage goes
after the rules, plan and program passages and is never trimmed; its text is already
bounded by 240's text limit, and a set that is still too large is the existing
``sources_too_large``.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Final

from amoeba.answering.passage_types import Passage, PassageKind

#: The id ``request_passage`` gives; ``add_request_passage`` numbers it in its set.
UNNUMBERED_ID: Final = "unnumbered"
COMMIT_LABEL: Final = "commit:"
VERSION_LABEL: Final = "version:"
#: Every line of the reply is indented by this, so no line of another repo's text can
#: start a ``## Passage`` header or a ``kind:`` line and pass for another passage.
QUOTED_INDENT: Final = "    "


def request_passage(  # noqa: PLR0913 - the request's plain fields, D5
    request_id: str,
    replied_by: str,
    done_at: datetime,
    result: str,
    commit: str | None,
    version: str | None,
) -> Passage:
    """The ``request_result`` passage of a ``done`` request.

    ``replied_by`` is the project that replied; ``done_at`` when it was marked done.
    The text is the result, then ``commit:`` and ``version:`` lines when present,
    every line indented by ``QUOTED_INDENT``.
    """
    lines = [result.rstrip("\n")]
    if commit is not None:
        lines.append(f"{COMMIT_LABEL} {commit}")
    if version is not None:
        lines.append(f"{VERSION_LABEL} {version}")
    return Passage(
        id=UNNUMBERED_ID,
        kind=PassageKind.REQUEST_RESULT,
        source=request_id,
        date=done_at,
        text=textwrap.indent("\n".join(lines) + "\n", QUOTED_INDENT),
        question=None,
        slice_label=None,
        question_id=None,
        member=replied_by,
    )


def add_request_passage(
    kept: Sequence[Passage], request: Passage | None
) -> list[Passage]:
    """``kept`` with ``request`` appended and numbered as the others are."""
    if request is None:
        return list(kept)
    return [*kept, replace(request, id=f"P{len(kept) + 1}")]
