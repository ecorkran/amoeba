"""The tool rows of ``send``, ``inbox``, ``reply`` and ``cancel`` (slice 240, D11).

Appended to ``TOOLS``. Each description carries the quoted-data notice, and each write
tool says what a rejection after a timeout means (the first call took effect, and
``inbox`` shows the state) and its worst-case wait.
"""

from __future__ import annotations

from typing import Final

from amoeba.mcp.tool_spec import READ_ADVICE, RunMode, ToolSpec
from amoeba.operations.message_models import (
    MAX_BODY_LENGTH,
    MAX_ID_LENGTH,
    MAX_REASON_LENGTH,
    MAX_RESULT_LENGTH,
    MAX_SUBJECT_LENGTH,
    CancelRequest,
    InboxRequest,
    ReplyRequest,
    SendRequest,
)
from amoeba.operations.names import OperationName
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.wiring_messages import MessageOperation, worst_case_seconds

#: What an agent does when ``send`` timed out: the request may have been stored, and
#: sending it again under the same id is safe.
SEND_ADVICE: Final = (
    "it may still complete; call `inbox` to see the request's state before repeating "
    "it. A repeated `send` with the same `id` is safe"
)
#: What an agent does when ``reply`` or ``cancel`` timed out: the change may have been
#: made, and a repeat is refused naming the state the first call reached.
STATE_CHANGE_ADVICE: Final = (
    "it may still complete; call `inbox` to see the request's state before repeating "
    "it. A repeat is rejected naming the state the first call reached"
)


def _wait(name: MessageOperation) -> str:
    return f"It can take up to {worst_case_seconds(name):g} s."


def _after_timeout(name: str) -> str:
    return (
        f"If `{name}` is rejected after a timeout, the first call took effect: "
        "`inbox` shows the state."
    )


MESSAGE_TOOLS: Final = (
    ToolSpec(
        name=OperationName.SEND,
        request_model=SendRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Ask another repo (a member of any program) for work. `to` is the "
            "addressee, a Context Forge project name or id. `id` is yours to choose "
            f"(letters, digits, `.`, `_`, `-`; at most {MAX_ID_LENGTH} characters): "
            "sending the same `id` with the same content again changes nothing, so a "
            f"retry is safe. `subject` (at most {MAX_SUBJECT_LENGTH} characters) and "
            f"`body` (at most {MAX_BODY_LENGTH}) say what you need; `parent` names "
            "the request this one serves. The sender is the repo at `directory`; "
            "from outside any repo, name it with `member`. "
            f"{QUOTED_DATA_NOTICE} {_after_timeout('send')} "
            f"{_wait(OperationName.SEND)} Same request and result as `amoeba send`."
        ),
        timeout_advice=SEND_ADVICE,
    ),
    ToolSpec(
        name=OperationName.INBOX,
        request_model=InboxRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "The requests the repo at `directory` has sent and received. Without "
            "`since`, every one still held. With `since`, what changed after that "
            "delivery number: `deliveries` in order and the `requests` they concern. "
            "Keep `as_of_seq` and pass it as the next `since`. Writes nothing and "
            f"marks nothing read. {QUOTED_DATA_NOTICE} {_wait(OperationName.INBOX)} "
            "Same request and result as `amoeba inbox`."
        ),
        timeout_advice=READ_ADVICE,
    ),
    ToolSpec(
        name=OperationName.REPLY,
        request_model=ReplyRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Answer a request sent to the repo at `directory`: `action` `accept` "
            "takes it (the first accept wins); `decline` ends it and `done` finishes "
            f"it, each with `text` (at most {MAX_RESULT_LENGTH} characters, the "
            "reason or the result); `done` may add `commit` (a full hash) and "
            "`version`. Only the addressee may reply. "
            f"{QUOTED_DATA_NOTICE} {_after_timeout('reply')} "
            f"{_wait(OperationName.REPLY)} Same request and result as `amoeba reply`."
        ),
        timeout_advice=STATE_CHANGE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.CANCEL,
        request_model=CancelRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "End a request that is open or accepted, naming its `id`, with an "
            f"optional `reason` (at most {MAX_REASON_LENGTH} characters). Nothing "
            "checks who calls: whoever names the id may cancel. "
            f"{QUOTED_DATA_NOTICE} {_after_timeout('cancel')} "
            f"{_wait(OperationName.CANCEL)} Same request and result as "
            "`amoeba cancel`."
        ),
        timeout_advice=STATE_CHANGE_ADVICE,
    ),
)
