"""The Context Forge read-back observer.

Answers, for a journaled ``cf_write`` command: does Context Forge now hold the
values the write was supposed to leave behind? The question is answered by
reading — ``cf get --json`` — never by re-applying the write.

Unlike Squadron, CF *can* distinguish "did not happen" from "cannot tell": the
project record either holds the expected values or it does not. So this observer
is the one that returns :class:`NotApplied`, when every expected field is
readable and at least one differs.

**Where it reads.** ``cf get`` answers for the checkout it runs in, so an entry
carrying ``checkout`` is read with that directory as the working directory. An
entry from before slice 125 has no ``checkout`` and is read without one. A pointer
write names the slice it sets with ``expected_slice_index``; the check is by index,
parsed from ``fileSlice`` by the shared stem rule, because Amoeba never builds
CF's slug. An entry that expects nothing at all is ``Unknown``: comparing nothing
would adopt vacuously.

**One read-back.** :func:`read_back_cf_write` is the whole comparison. The
recovery observer calls it with ``subprocess.run``; the Runner's tick calls the
same function, so the two can never disagree about what "written" means.

**Provenance.** ``cf get --json`` exposes no version field (verified 20260921:
its keys are project metadata only). The observer therefore records two things
on adoption: the project record's own ``updatedAt``, which is what actually
dates the observed values, and an opaque label from a single ``cf --version``
invocation per recovery pass. Neither is ever compared, parsed for ordering, or
branched on — recording provenance is not the same as depending on a version.
If ``cf --version`` fails, the label is recorded as unavailable and the
adoption still succeeds: provenance capture never turns a clean adoption into an
escalation.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence

from amoeba.process import version_label
from amoeba.process.observers.cf_get import (
    CF_EXECUTABLE,
    CF_FIELD_FILE_SLICE,
    CF_FIELD_PROJECT_PATH,
    CF_FIELD_UPDATED_AT,
    CFProjectRecord,
    CFRun,
    read_project,
)
from amoeba.process.recovery import Adopt, NotApplied, Observation, Unknown
from amoeba.process.version_label import VERSION_UNAVAILABLE
from amoeba.store.journal_models import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED_SLICE_INDEX,
    JournalEntry,
)
from amoeba.upstream.context_forge import parse_slice_stem

#: Journal parameter keys this observer reads. ``project`` and ``expected`` are
#: required at issue time, as is ``checkout`` for entries written since slice 125.
PARAM_PROJECT = "project"
PARAM_EXPECTED = "expected"

#: Result keys recorded on adoption.
RESULT_UPDATED_AT = "cf_updated_at"
RESULT_VERSION_LABEL = "cf_version_label"
RESULT_FILE_SLICE = "file_slice"
RESULT_WORKTREE_ID = "worktree_id"
RESULT_PROJECT_PATH = "project_path"


def capture_version_label(timeout_seconds: float) -> str:
    """Capture ``cf --version`` as an opaque label, once per recovery pass.

    Never raises and never escalates: a failure is recorded as
    :data:`VERSION_UNAVAILABLE`.
    """
    return version_label.capture_version_label(CF_EXECUTABLE, timeout_seconds)


def read_back_cf_write(
    entry: JournalEntry,
    run: CFRun,
    timeout_seconds: float,
    label: Callable[[], str] | None = None,
) -> Observation:
    """Report whether CF holds the values this ``cf_write`` entry intended.

    ``label``, when given, supplies the provenance label recorded on adoption
    and is called only then; the tick passes none.
    """
    parameters = entry.parameters
    project = parameters.get(PARAM_PROJECT)
    expected = parameters.get(PARAM_EXPECTED)
    checkout = parameters.get(PARAM_CHECKOUT)
    raw_index = parameters.get(PARAM_EXPECTED_SLICE_INDEX)
    slice_index = _as_index(raw_index)

    if not isinstance(project, str) or not isinstance(expected, Mapping):
        return Unknown(
            reason="journal entry does not carry a project and expected mapping"
        )
    if checkout is not None and not isinstance(checkout, str):
        return Unknown(reason="journal entry's checkout is not a path")
    if raw_index is not None and slice_index is None:
        return Unknown(reason="journal entry's expected slice index is not an integer")
    if not expected and slice_index is None:
        return Unknown(reason="journal entry expects nothing, so nothing can be read")

    record = read_project(project, checkout, run, timeout_seconds)
    if isinstance(record, Unknown):
        return record

    narrowed_expected: dict[str, object] = dict(expected)  # pyright: ignore[reportUnknownArgumentType]
    mismatch = _mismatch(record, narrowed_expected, slice_index)
    if mismatch is not None:
        return mismatch

    result: dict[str, object] = {
        RESULT_UPDATED_AT: record.field_value(CF_FIELD_UPDATED_AT),
        RESULT_FILE_SLICE: record.field_value(CF_FIELD_FILE_SLICE),
        RESULT_WORKTREE_ID: record.worktree_id(),
        RESULT_PROJECT_PATH: record.field_value(CF_FIELD_PROJECT_PATH),
    }
    if label is not None:
        result[RESULT_VERSION_LABEL] = label()
    return Adopt(result=result)


def _as_index(value: object) -> int | None:
    """The value if it is an integer; ``bool`` is not one, though Python says so."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _mismatch(
    record: CFProjectRecord, expected: Mapping[str, object], slice_index: int | None
) -> Unknown | NotApplied | None:
    """Why the record does not hold what was written, or ``None`` if it does.

    Any *absent* field -> unknown, because a field the record does not carry is
    an incomplete observation rather than a mismatch. Then any present and
    differing -> not applied. ``slice_index`` is compared with the index parsed
    from ``fileSlice``; a ``fileSlice`` that does not parse is unknown.
    """
    missing = {name for name in expected if not record.has_field(name)}
    file_slice = record.field_value(CF_FIELD_FILE_SLICE)
    stem = parse_slice_stem(file_slice if isinstance(file_slice, str) else None)
    if slice_index is not None and stem is None:
        missing.add(CF_FIELD_FILE_SLICE)
    if missing:
        return Unknown(
            reason=(
                "cf get output does not carry the expected field(s): "
                f"{', '.join(sorted(missing))}"
            )
        )

    differing = {
        name for name, value in expected.items() if record.field_value(name) != value
    }
    if slice_index is not None and stem is not None and stem.index != slice_index:
        differing.add(CF_FIELD_FILE_SLICE)
    if differing:
        return NotApplied(
            reason=f"cf holds a different value for: {', '.join(sorted(differing))}"
        )
    return None


class CFReadbackObserver:
    """Compares CF's current project record against a journaled write."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        version_label: str | None = None,
    ) -> None:
        """Build an observer over the ``cf`` CLI.

        Args:
            timeout_seconds: How long to wait for a ``cf`` invocation before
                treating the system as unobservable.
            version_label: The provenance label captured once per recovery
                pass. When omitted, it is captured on first use.
        """
        self._timeout_seconds = timeout_seconds
        self._version_label = version_label

    @property
    def version_label(self) -> str:
        """The provenance label, captured once and reused."""
        if self._version_label is None:
            self._version_label = capture_version_label(self._timeout_seconds)
        return self._version_label

    def observe(self, entry: JournalEntry) -> Observation:
        """Report whether CF holds the values this entry's write intended."""
        # ``subprocess.run`` is looked up here, at call time, never bound earlier.
        return read_back_cf_write(
            entry,
            subprocess.run,
            self._timeout_seconds,
            lambda: self.version_label,
        )


__all__: Sequence[str] = [
    "CF_FIELD_FILE_SLICE",
    "CF_FIELD_PROJECT_PATH",
    "CF_FIELD_UPDATED_AT",
    "PARAM_EXPECTED",
    "PARAM_PROJECT",
    "RESULT_FILE_SLICE",
    "RESULT_PROJECT_PATH",
    "RESULT_UPDATED_AT",
    "RESULT_VERSION_LABEL",
    "RESULT_WORKTREE_ID",
    "VERSION_UNAVAILABLE",
    "CFProjectRecord",
    "CFReadbackObserver",
    "CFRun",
    "capture_version_label",
    "read_back_cf_write",
]
