"""``cf get --json``: the one command that reads a project's record, and its parse.

Each external failure mode gets a distinguishable :class:`Unknown` reason, so the
human reading a blocked state knows whether ``cf`` is missing, hung, failing, or
emitting something unparseable. Nothing here compares anything: the read-back
observer (``cf_readback``) does that.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable, Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.process.recovery import Unknown

logger = logging.getLogger(__name__)

#: Runs ``cf``: ``subprocess.run`` in production, a fake in unit tests.
type CFRun = Callable[..., subprocess.CompletedProcess[str]]

#: The executable, and the argument vectors used. Defined once so no call site
#: assembles a command line of its own.
CF_EXECUTABLE: Final = "cf"

#: CF record fields the read-back reads besides the ones an entry expects.
CF_FIELD_UPDATED_AT: Final = "updatedAt"
CF_FIELD_FILE_SLICE: Final = "fileSlice"
CF_FIELD_PROJECT_PATH: Final = "projectPath"
CF_FIELD_WORKTREE: Final = "worktree"
CF_FIELD_WORKTREE_ID: Final = "id"


def _cf_get_args(project: str) -> tuple[str, ...]:
    """The argument vector reading one project's record as JSON."""
    return (CF_EXECUTABLE, "get", "--json", "-p", project)


class CFProjectRecord(BaseModel):
    """A ``cf get --json`` project record.

    Every field is optional and unknown fields are ignored: the observer reads
    whichever fields the entry's ``expected`` mapping names, and CF's record
    shape is not this project's to fix. ``updatedAt`` is read separately as
    provenance, and ``projectPath`` and ``worktree.id`` identify the checkout
    the record answers for.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    def field_value(self, name: str) -> object | None:
        """Return a field's value, or ``None`` when the record has no such key."""
        extra = self.model_extra or {}
        return extra.get(name)

    def has_field(self, name: str) -> bool:
        """Whether the record carries this key at all.

        Distinguished from a field whose value is ``None``: an absent field
        means the observation is incomplete and must escalate, while a present
        null is a value that can be compared.
        """
        return name in (self.model_extra or {})

    def worktree_id(self) -> str | None:
        """The id of the worktree the record answers for, ``None`` without one."""
        worktree = self.field_value(CF_FIELD_WORKTREE)
        if not isinstance(worktree, Mapping):
            return None
        found = worktree.get(CF_FIELD_WORKTREE_ID)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        return found if isinstance(found, str) else None


def read_project(
    project: str, checkout: str | None, run: CFRun, timeout_seconds: float
) -> CFProjectRecord | Unknown:
    """Run ``cf get --json``, returning the record or why it is unobservable.

    Runs in ``checkout`` when one is given, and with no working directory
    otherwise (entries written before slice 125).
    """
    options: dict[str, object] = {} if checkout is None else {"cwd": checkout}
    try:
        completed = run(
            _cf_get_args(project),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            check=False,
            **options,
        )
    except FileNotFoundError:
        # Specific: cf is not on PATH. An answer, not a bug.
        logger.warning("cf is not on PATH")
        return Unknown(reason="cf is not available on PATH")
    except subprocess.TimeoutExpired:
        # Specific: cf hung. Never retried here; recovery escalates.
        logger.warning("cf get timed out after %ss", timeout_seconds)
        return Unknown(reason=f"cf get timed out after {timeout_seconds}s")
    except OSError:
        # Specific: the process could not be launched at all.
        logger.warning("cannot invoke cf", exc_info=True)
        return Unknown(reason="cf could not be invoked")

    if completed.returncode != 0:
        logger.warning("cf get exited %d", completed.returncode)
        return Unknown(
            reason=(
                f"cf get exited {completed.returncode}: "
                f"{completed.stderr.strip() or 'no stderr'}"
            )
        )

    return _parse(completed.stdout)


def _parse(output: str) -> CFProjectRecord | Unknown:
    """Parse ``cf get --json`` output, or say why it could not be read."""
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        # Specific: cf emitted something that is not JSON.
        logger.warning("cf get emitted unparseable output")
        return Unknown(reason="cf get emitted unparseable output")

    try:
        return CFProjectRecord.model_validate(payload)
    except ValidationError:
        # Specific: the output is JSON but not a project record object.
        logger.warning("cf get output is not a project record")
        return Unknown(reason="cf get output is not a project record")
