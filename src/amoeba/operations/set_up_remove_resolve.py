"""``set_up`` removal, step 2: each reference in ``remove`` becomes an id (228 D8).

A reference Context Forge knows resolves to its id. One it does not know is kept as
written and read as a stored member id, so a member whose Context Forge project was
deleted can still be removed by its id; the checks then find or reject it.

The three ways a request can contradict itself are ``malformed`` problems here, with
the path of the offending entry: a member under both ``members`` and
``remove.members``; a pair under both ``depends_on`` and ``remove.pairs``; and a
removed member named as the end of a pair (in ``remove.pairs`` or as a ``depends_on``
provider).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from amoeba.operations.set_up_models import (
    RemoveRequest,
    SetUpProblem,
    SetUpProblemCode,
)
from amoeba.upstream.context_forge.project_of import CFProject, CFProjectNotFound

#: Asks Context Forge about one reference (each reference once per call).
type Lookup = Callable[[str], CFProject | CFProjectNotFound]


@dataclass(frozen=True)
class Reference:
    """A reference as written, its id, and whether Context Forge knew it."""

    text: str
    project_id: str
    known_to_cf: bool


@dataclass(frozen=True)
class RemovedMember:
    #: Position in ``remove.members``, for problem details.
    index: int
    reference: Reference


@dataclass(frozen=True)
class RemovedPair:
    #: Position in ``remove.pairs``.
    index: int
    provider: Reference
    consumer: Reference


@dataclass(frozen=True)
class ResolvedRemoval:
    members: tuple[RemovedMember, ...] = ()
    pairs: tuple[RemovedPair, ...] = ()

    @property
    def member_ids(self) -> frozenset[str]:
        return frozenset(item.reference.project_id for item in self.members)


@dataclass(frozen=True)
class RequestedPair:
    """A ``depends_on`` entry of the request, as resolved."""

    member_index: int
    position: int
    provider_id: str
    consumer_id: str


def _reference(text: str, lookup: Lookup) -> Reference:
    found = lookup(text)
    if isinstance(found, CFProjectNotFound):
        return Reference(text, text, known_to_cf=False)
    return Reference(text, found.id, known_to_cf=True)


def _malformed(detail: str) -> SetUpProblem:
    return SetUpProblem(code=SetUpProblemCode.MALFORMED, detail=detail)


def resolve_removal(
    remove: RemoveRequest,
    lookup: Lookup,
    member_ids: dict[str, int],
    requested_pairs: Sequence[RequestedPair],
) -> tuple[ResolvedRemoval, list[SetUpProblem]]:
    """The removal as ids, and the ways it contradicts the rest of the request.

    ``member_ids`` maps each id under ``members`` to its position there.
    """
    members: dict[str, RemovedMember] = {}
    for index, text in enumerate(remove.members):
        reference = _reference(text, lookup)
        # The same member twice is one removal.
        members.setdefault(reference.project_id, RemovedMember(index, reference))
    pairs = tuple(
        RemovedPair(
            index,
            _reference(entry.provider, lookup),
            _reference(entry.consumer, lookup),
        )
        for index, entry in enumerate(remove.pairs)
    )
    removal = ResolvedRemoval(tuple(members.values()), pairs)
    return removal, _contradictions(removal, member_ids, requested_pairs)


def _contradictions(
    removal: ResolvedRemoval,
    member_ids: dict[str, int],
    requested_pairs: Sequence[RequestedPair],
) -> list[SetUpProblem]:
    problems: list[SetUpProblem] = []
    removed_by = {item.reference.project_id: item.index for item in removal.members}
    for item in removal.members:
        listed = member_ids.get(item.reference.project_id)
        if listed is not None:
            problems.append(
                _malformed(
                    f"remove.members.{item.index}: {item.reference.project_id} is "
                    f"also listed as members.{listed}"
                )
            )
    for pair in removal.pairs:
        for end, reference in (
            ("provider", pair.provider),
            ("consumer", pair.consumer),
        ):
            if reference.project_id in removed_by:
                problems.append(
                    _malformed(
                        f"remove.pairs.{pair.index}.{end}: {reference.project_id} is "
                        f"removed by remove.members.{removed_by[reference.project_id]}"
                    )
                )
        for requested in requested_pairs:
            if (requested.provider_id, requested.consumer_id) == (
                pair.provider.project_id,
                pair.consumer.project_id,
            ):
                problems.append(
                    _malformed(
                        f"remove.pairs.{pair.index}: also given as "
                        f"members.{requested.member_index}.depends_on."
                        f"{requested.position}"
                    )
                )
    for requested in requested_pairs:
        if requested.provider_id in removed_by:
            problems.append(
                _malformed(
                    f"members.{requested.member_index}.depends_on."
                    f"{requested.position}.provider: {requested.provider_id} is "
                    f"removed by remove.members.{removed_by[requested.provider_id]}"
                )
            )
    return problems
