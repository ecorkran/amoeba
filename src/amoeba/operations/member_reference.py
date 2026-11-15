"""A member reference: a Context Forge name or id, as ``rm`` and ``send`` read it.

The rule (slice 228, used again by slice 240): ask ``cf`` for the project; one ``cf``
does not know is read as an id, because a removed member's project may be gone from
``cf`` while its row remains.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.operations.members import ContextForgeError
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import CFProject, project_of


@dataclass(frozen=True)
class Anchor:
    """A named member (or pair end): as written, and its stored id."""

    text: str
    project_id: str


def anchor(text: str, run: CfRun) -> Anchor:
    """A reference as its Context Forge id; one cf does not know is read as an id.

    Raises:
        ContextForgeError: ``cf`` failed or timed out; nothing should be written.
    """
    found = project_of(reference=text, run=run)
    if isinstance(found, CfCallFailed):
        raise ContextForgeError(found.detail)
    return Anchor(text, found.id if isinstance(found, CFProject) else text)
