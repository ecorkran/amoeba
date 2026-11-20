"""The tool rows of ``standing`` and ``withdraw`` (slice 230, D2, D3, D10).

Appended to ``TOOLS``. Neither takes a ``directory``. Both descriptions carry the rule
``answer`` carries: the text is a ruling the PM actually gave, passed on as given.
"""

from __future__ import annotations

from typing import Final

from amoeba.mcp.tool_spec import WRITE_ADVICE, RunMode, ToolSpec
from amoeba.operations.names import OperationName
from amoeba.operations.standing_models import StandingRequest, WithdrawRequest

#: The rule both tools share with ``answer`` (D2): the agent relays, never composes. It
#: is the only gate on the write. A standing answer reaches further than an ``answer``
#: (every later question of every member in its reach, not one question), but it acts
#: only as a passage: each automatic answer citing it still passes the not-authorized
#: list, the check step and the answer screen (D7, pinned by
#: ``test_an_answer_citing_a_standing_answer_that_authorizes_a_barred_item_declines``).
#: ``list standing`` shows every row and ``decisions`` every answer that cited one.
PM_RULING_RULE: Final = (
    "Call it only for a ruling the PM actually gave, passed on as given, never one "
    "you composed."
)

STANDING_TOOLS: Final = (
    ToolSpec(
        name=OperationName.STANDING,
        request_model=StandingRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Record a standing answer: a ruling the PM gave once, ahead of time, for "
            "every later question it covers. `text` is the PM's words, the situation "
            "and what to do in it. With neither `program` nor `member` it reaches "
            "every member; `program` (a program id) or `member` (a Context Forge "
            "project name or id) limits it to one, never both. From the next question "
            f"on, every answering run it reaches is sent it. {PM_RULING_RULE} The "
            "same call again answers `unchanged` with the same id. Same request and "
            "result as `amoeba standing`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.WITHDRAW,
        request_model=WithdrawRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Take back a standing answer by its `standing_id` (from `list` with "
            "`view` `standing`), with a `reason`. Later questions are no longer sent "
            "it; answers already given from it stay. There is no undo: the PM gives "
            f"the ruling again. {PM_RULING_RULE} The same call again answers "
            "`unchanged`. Same request and result as `amoeba withdraw`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
)
