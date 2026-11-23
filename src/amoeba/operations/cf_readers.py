"""The local way's readers for ``decisions`` and ``standing``: Context Forge's names
(slice 260, D11).

``decisions`` takes a names reader and ``standing`` a member resolver, so the hub can
give its own. These two build the `cf`-backed ones the CLI and MCP always used.
"""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.operations.decisions import NamesReader
from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.standing import MemberResolver
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import CFProjectNotFound, project_of


def cf_names(deps: Deps) -> NamesReader:
    """Every project's name from one `cf` call, whatever ids are asked for.

    Raises (when called): ContextForgeError: ``cf`` gave no names.
    """

    def read(_member_ids: tuple[str, ...]) -> Mapping[str, str]:
        names = deps.project_names()
        if isinstance(names, CfCallFailed):
            raise ContextForgeError(names.detail)
        return names

    return read


def cf_member_resolver(run: CfRun) -> MemberResolver:
    """Resolve a member reference (id or name) through `cf`, with no directory.

    Raises (when called): ContextForgeError: ``cf`` failed.
    """

    def resolve(reference: str) -> str | None:
        found = project_of(reference=reference, run=run)
        if isinstance(found, CfCallFailed):
            raise ContextForgeError(found.detail)
        if isinstance(found, CFProjectNotFound):
            return None
        return found.id

    return resolve
