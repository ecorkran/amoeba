"""The listing registry's types: what a listing declares, and what it is asked.

A :class:`Listing` declares its rows, its columns, and its options. An option's
``name`` is the one declared label: the CLI derives ``--flag`` from it, and the
server derives its query parameter from it. A :class:`ListingRequest` carries
the values a caller supplied, keyed by that ``name``.

These types live apart from the registry (``amoeba.inspection``) because the
row modules need the option objects at runtime, and the package imports the
row modules.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.store import Store

#: One row of a listing: ordered column name/value pairs, so the table and the
#: JSON forms cannot disagree about either content or order.
type Row = dict[str, object]

#: A value a caller supplied for one option.
type OptionValue = str | bool | None


class ListingScope(StrEnum):
    """Whether a listing reads one project's store or the supervisor directory."""

    PROJECT = "project"
    SUPERVISOR = "supervisor"


def _flag_for(name: str) -> str:
    """The CLI flag derived from an option name: ``node_id`` -> ``--node-id``."""
    return "--" + name.replace("_", "-")


@dataclass(frozen=True)
class FlagOption:
    """A boolean flag, e.g. ``--unresolved``."""

    name: str
    help_text: str

    @property
    def flag(self) -> str:
        return _flag_for(self.name)


@dataclass(frozen=True)
class ChoiceOption:
    """An optional option taking one value from a closed set, e.g. ``--channel``."""

    name: str
    help_text: str
    choices: tuple[str, ...]

    @property
    def flag(self) -> str:
        return _flag_for(self.name)


@dataclass(frozen=True)
class ValueOption:
    """An option taking one free value, e.g. ``--node ID``."""

    name: str
    help_text: str
    metavar: str
    required: bool = False

    @property
    def flag(self) -> str:
        return _flag_for(self.name)


type ListingOption = FlagOption | ChoiceOption | ValueOption


@dataclass(frozen=True)
class ListingRequest:
    """What a caller asked one listing for.

    Attributes:
        project_id: The project, for a project-scoped listing; else ``None``.
        options: Supplied option values, keyed by option ``name``.
        compact: Whether rows may abbreviate for a table. The CLI's table form
            sets it; ``--json`` and the server never do.
    """

    project_id: str | None
    options: Mapping[str, OptionValue]
    compact: bool

    def require_project_id(self) -> str:
        """The project id, for a project-scoped row function.

        Raises:
            ValueError: If the request carries no project.
        """
        if self.project_id is None:
            raise ValueError("a project-scoped listing needs a project id")
        return self.project_id

    @overload
    def option(self, opt: FlagOption) -> bool: ...
    @overload
    def option(self, opt: ChoiceOption | ValueOption) -> str | None: ...
    def option(self, opt: ListingOption) -> OptionValue:
        """The supplied value of ``opt``.

        Raises:
            KeyError: If the request carries no value for ``opt``. There is no
                default: the caller builds the request from the declared options.
            TypeError: If the stored value's type does not fit the option.
        """
        if opt.name not in self.options:
            raise KeyError(f"listing request carries no value for {opt.name!r}")
        value = self.options[opt.name]
        is_flag = isinstance(opt, FlagOption)
        if is_flag != isinstance(value, bool):
            raise TypeError(f"option {opt.name!r} has a {type(value).__name__} value")
        return value


@dataclass(frozen=True)
class Listing:
    """One inspection listing: its name, its query, and its columns.

    Exactly one of ``rows`` and ``supervisor_rows`` is set. Which one is what
    makes a listing project-scoped or supervisor-level — never its name.

    Attributes:
        name: The subcommand name and URL segment. Derived *from* this entry.
        help_text: One line, shown by ``--help``.
        columns: Column order for the table form.
        rows: For a project-scoped listing: receives an open **read-only**
            store and the request.
        supervisor_rows: For a supervisor-level listing: receives the
            supervisor directory, and opens no store.
        flags: Boolean flags.
        choice_options: Options taking one value from a set.
        value_options: Options taking one free value. The three stay separate
            because the CLI adds them in this order, and ``--help`` shows it.
    """

    name: str
    help_text: str
    columns: tuple[str, ...]
    rows: Callable[[Store, ListingRequest], list[Row]] | None = None
    supervisor_rows: Callable[[Path], list[Row]] | None = None
    flags: tuple[FlagOption, ...] = field(default_factory=tuple)
    choice_options: tuple[ChoiceOption, ...] = field(default_factory=tuple)
    value_options: tuple[ValueOption, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (self.rows is None) == (self.supervisor_rows is None):
            raise ValueError(
                f"listing {self.name!r} must set exactly one of rows and "
                "supervisor_rows"
            )

    @property
    def scope(self) -> ListingScope:
        """Project-scoped when ``rows`` is set, supervisor-level otherwise."""
        if self.supervisor_rows is None:
            return ListingScope.PROJECT
        return ListingScope.SUPERVISOR


#: Shared by every listing that can narrow to one node.
NODE_OPTION = ValueOption(name="node", help_text="Only this node.", metavar="ID")
