"""The tool table (slice 226, D2, D5): one row per operation, and each row's input.

``TOOLS`` is the one list of what the server offers. A tool's name is its
operation's name, its schema is the operation's own request model, and its arguments
reach the operation unvalidated (the operation validates, 222 D7). The only thing
this module adds to a request is ``directory``, for the operations that need
the caller's checkout, because an MCP session can start anywhere and the server never
reads its own working directory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from amoeba.operations.add import AddRequest
from amoeba.operations.answer import AnswerRequest
from amoeba.operations.changes_models import ChangesRequest
from amoeba.operations.decisions import DecisionsRequest
from amoeba.operations.dismiss import DismissRequest
from amoeba.operations.handle_pause_call import HandlePauseCall
from amoeba.operations.list_view import ListRequest
from amoeba.operations.mark_read import MarkReadRequest
from amoeba.operations.names import OperationName
from amoeba.operations.report_release_models import ReportReleaseRequest
from amoeba.operations.retract import RetractRequest
from amoeba.operations.rm import RmRequest
from amoeba.operations.status import StatusRequest

#: The argument that names the caller's checkout, for the tools that take one.
DIRECTORY_FIELD: Final = "directory"
DIRECTORY_DESCRIPTION: Final = (
    "Absolute path of the caller's checkout (the repository the run or program "
    "belongs to). Never relative."
)

#: What an agent does when ``status`` or ``decisions`` timed out (D12): the CLI has no
#: deadline, so it is the way through; never the tool that just timed out.
READ_ADVICE: Final = (
    "it was abandoned and may still finish; run the `amoeba` command of the same "
    "name in a shell, which has no deadline, instead of calling this tool again"
)
#: What an agent does when a write tool timed out (D12): the work may have happened.
WRITE_ADVICE: Final = (
    "it may still complete; check `status` or `decisions` before repeating it"
)


class RunMode(StrEnum):
    """How a tool runs: in a worker thread of the server, or as a detached child."""

    IN_PROCESS = "in_process"
    DETACHED = "detached"


class RequestError(Exception):
    """The call cannot form an operation request; the message names the field."""


@dataclass(frozen=True)
class ToolSpec:
    """One tool: its operation, input, run mode, description and timeout advice."""

    name: OperationName
    request_model: type[BaseModel]
    takes_directory: bool
    mode: RunMode
    description: str
    #: What the agent does when the call times out; ``None`` for a detached tool,
    #: which returns a receipt at once and has no deadline to hit.
    timeout_advice: str | None


TOOLS: Final = (
    ToolSpec(
        name=OperationName.ADD,
        request_model=AddRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Register a repository so Amoeba answers its runs' questions. The repo is "
            "the one at `directory` (or the Context Forge project `project` names). "
            "It becomes a member of a program, a group of related repos Amoeba "
            "answers across; `program` names it, and with none the repo joins its "
            "current program or starts a one-member program. Nothing else is "
            "needed: the repo's CLAUDE.md and AGENTS.md are read as its rules. "
            "Optional `rules_paths` (or `rules_default`), `authorize_allow` and "
            "`authorize_deny`, `depends_on` (another member this one consumes) and "
            "`concept` refine that. `bulk` takes a whole multi-member request "
            "instead of the single-member fields. Same request and result as "
            "`amoeba add`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.RM,
        request_model=RmRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Remove members, dependency pairs or a program's concept; with nothing "
            "named, the repository at `directory`. Same request and result as "
            "`amoeba rm`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.LIST,
        request_model=ListRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "With no `subject`, what needs the PM: the same result as `status`, and "
            "with `all` also what settled recently. `programs`, `members` or "
            "`dependencies` show what is registered. Same request and result as "
            "`amoeba list -j`."
        ),
        timeout_advice=READ_ADVICE,
    ),
    ToolSpec(
        name=OperationName.STATUS,
        request_model=StatusRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Runs, pauses and questions waiting on the PM, per program and member. "
            "Its listing gives the `run_id` and `directory` for `handle_pause` and "
            "the question key for `answer`."
        ),
        timeout_advice=READ_ADVICE,
    ),
    ToolSpec(
        name=OperationName.DECISIONS,
        request_model=DecisionsRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "What was decided while the PM was away: answers recorded since the "
            "PM's read marker (the point they last marked as read), or since a "
            "time, with who gave each and through which door. Give its "
            "`read_through` to `mark_read`."
        ),
        timeout_advice=READ_ADVICE,
    ),
    ToolSpec(
        name=OperationName.MARK_READ,
        request_model=MarkReadRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Move the PM's marker forward to the `read_through` of a `decisions` call."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.ANSWER,
        request_model=AnswerRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Record the PM's answer to a question, then resume the run. `text` must "
            "be a decision the PM actually gave, passed on as given, never one you "
            "composed: it becomes precedent for later questions. The question key "
            "(`run_id`, optionally `paused_at`) comes from `status`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.DISMISS,
        request_model=DismissRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Close a question that has no answer to deliver; the run stays paused."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.RETRACT,
        request_model=RetractRequest,
        takes_directory=False,
        mode=RunMode.IN_PROCESS,
        description=(
            "Stop a PM answer being precedent; it stays delivered and listed."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.REPORT_RELEASE,
        request_model=ReportReleaseRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "Report what a merge or release in the repo at `directory` changed for "
            "the repos that depend on it. `commit` is the full hash, `changed` says "
            "what changed for someone using the repo, and `touched` lists each thing "
            "changed. Give `version` (the tag name) for a release. With `mode` "
            "`correct` it replaces the text of a report already made; with "
            "`withdraw` it takes the report back. Same request and result as "
            "`amoeba report-release`."
        ),
        timeout_advice=WRITE_ADVICE,
    ),
    ToolSpec(
        name=OperationName.CHANGES,
        request_model=ChangesRequest,
        takes_directory=True,
        mode=RunMode.IN_PROCESS,
        description=(
            "What the repos that the repo at `directory` depends on have reported "
            "since `since` (an ISO-8601 time with a UTC offset): one entry per "
            "provider, each with the reports that provider's pair shows. Writes "
            "nothing and marks nothing read. Same request and result as `amoeba "
            "changes`."
        ),
        timeout_advice=READ_ADVICE,
    ),
    ToolSpec(
        name=OperationName.HANDLE_PAUSE,
        request_model=HandlePauseCall,
        takes_directory=True,
        mode=RunMode.DETACHED,
        description=(
            "Answer a paused run's question and resume it, or record it as waiting "
            "on the PM. Starts the work and returns a receipt at once; the result "
            "lands in the receipt's stdout log. An empty log may mean the work is "
            "still running or was killed: confirm through `status` or `decisions`."
        ),
        timeout_advice=None,
    ),
)


def input_schema(spec: ToolSpec) -> dict[str, Any]:
    """The tool's published input schema: its request model's, plus ``directory``.

    ``directory`` is added, required, for the tools that take one.
    """
    schema: dict[str, Any] = spec.request_model.model_json_schema()
    if not spec.takes_directory:
        return schema
    properties: dict[str, Any] = dict(schema.get("properties", {}))
    properties[DIRECTORY_FIELD] = {
        "type": "string",
        "description": DIRECTORY_DESCRIPTION,
    }
    required: list[str] = list(schema.get("required", []))
    if DIRECTORY_FIELD not in required:
        required.append(DIRECTORY_FIELD)
    return {**schema, "properties": properties, "required": required}


def _directory_from(raw: Mapping[str, object]) -> Path:
    """The absolute ``directory`` argument.

    Raises:
        RequestError: Missing, not a string, or not absolute.
    """
    if DIRECTORY_FIELD not in raw:
        raise RequestError(f"{DIRECTORY_FIELD} is required: an absolute path")
    value = raw[DIRECTORY_FIELD]
    if not isinstance(value, str):
        raise RequestError(f"{DIRECTORY_FIELD} must be a string, got {value!r}")
    directory = Path(value)
    if not directory.is_absolute():
        raise RequestError(f"{DIRECTORY_FIELD} must be an absolute path, got {value!r}")
    return directory


def prepare_arguments(
    spec: ToolSpec, raw: Mapping[str, object] | None
) -> tuple[dict[str, object], Path | None]:
    """The operation's document and the caller's directory, from a call's arguments.

    A tool that takes a directory has it checked and removed. Everything else passes
    through unvalidated, unknown keys and bad values included: the operation
    validates its own request, so both doors get the same ``rejected`` result.

    Raises:
        RequestError: A directory tool got no usable ``directory``.
    """
    document = {} if raw is None else dict(raw)
    if not spec.takes_directory:
        return document, None
    directory = _directory_from(document)
    del document[DIRECTORY_FIELD]
    return document, directory
