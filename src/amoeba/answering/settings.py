"""The answerer's settings: what one answering run may do, all stated, none defaulted.

``AnswererSettings`` has no default values: whoever builds it states every key, so a
missing key fails loudly instead of becoming a quiet magic value. Where the values
come from (a user-level config and per-member settings) is the loader's business, not
this module's.
"""

from __future__ import annotations

from functools import partial
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
)

from amoeba.answering.values import GLOB_WILDCARD
from amoeba.upstream.squadron.launch import param_problem


def validate_repo_relative_path(entry: str, *, glob_allowed: bool) -> str:
    """The entry, when it names a file inside a repository.

    The one definition of the rule for every repo-relative path the system
    accepts: a ``rules_paths`` entry (a ``*`` is allowed in the last segment)
    and a program concept path (no wildcard at all).

    Args:
        entry: The path, already stripped.
        glob_allowed: Whether ``*`` may appear in the last segment.

    Raises:
        ValueError: The entry is absolute, has a ``..`` segment, names a
            directory, or has a ``*`` where none is allowed.
    """
    segments = entry.split("/")
    if entry.startswith("/"):
        raise ValueError("must be relative to the repository, not absolute")
    if ".." in segments:
        raise ValueError("must not contain a `..` segment")
    if not segments[-1]:
        raise ValueError("must name a file, not a directory")
    if not glob_allowed and GLOB_WILDCARD in entry:
        raise ValueError(f"must not contain `{GLOB_WILDCARD}`")
    if any(GLOB_WILDCARD in segment for segment in segments[:-1]):
        raise ValueError(f"`{GLOB_WILDCARD}` is allowed in the last segment only")
    return entry


#: One ``rules_paths`` entry: stripped, non-blank, relative, contained (slice 143, D10).
RulesPath = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(partial(validate_repo_relative_path, glob_allowed=True)),
]


def _checked_model_alias(alias: str) -> str:
    """The alias, when Squadron would not split it as a ``-p`` value.

    Raises:
        ValueError: it contains a ``,`` (the same refusal ``build_argv`` makes).
    """
    problem = param_problem("model", alias)
    if problem is not None:
        raise ValueError(problem)
    return alias


#: A Squadron model alias: stripped, non-blank, no ``,`` (slice 144, D12).
ModelAlias = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_checked_model_alias),
]


class AnswererSettings(BaseModel):
    """How the answerer is configured.

    All seven keys are required with no defaults: the operator states how many
    answers a run may take and which terms stay the PM's to decide (slice 142, D7),
    which files are the project's rules and how large the rendered passages may be
    (slice 143, D10), and which models run the answering pipeline and what one run
    may cost (slice 144, D12), so an empty mapping fails.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Most answers the answerer may give in one run, from one up.
    answer_limit: Annotated[StrictInt, Field(ge=1)]
    #: Terms whose presence in a question or answer declines it. May be empty.
    reserved_terms: tuple[
        Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)],
        ...,
    ]
    #: Repo-relative rules files read at the target commit; ``*`` in the last segment
    #: only. May be empty; an entry that matches nothing fails assembly.
    rules_paths: tuple[RulesPath, ...]
    #: Most characters of rendered ``passages.md`` an answering run is sent.
    passages_max_chars: Annotated[StrictInt, Field(ge=1)]
    #: Squadron model aliases for the answer step and the check step. A comma would
    #: split a ``-p`` value, so none is allowed.
    answer_model: ModelAlias
    check_model: ModelAlias
    #: Cost cap of one answering run, in US dollars; above zero.
    max_cost_usd: Annotated[StrictInt | StrictFloat, Field(gt=0)]
