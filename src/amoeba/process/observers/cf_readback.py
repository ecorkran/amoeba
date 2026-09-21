"""The Context Forge read-back observer.

Answers, for a journaled ``cf_write`` command: does Context Forge now hold the
values the write was supposed to leave behind? The question is answered by
reading — ``cf get --json`` — never by re-applying the write.

Unlike Squadron, CF *can* distinguish "did not happen" from "cannot tell": the
project record either holds the expected values or it does not. So this observer
is the one that returns :class:`NotApplied`, when every expected field is
readable and at least one differs.

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

import json
import logging
import subprocess
from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.process.recovery import Adopt, NotApplied, Observation, Unknown
from amoeba.store.journal_models import JournalEntry

logger = logging.getLogger(__name__)

#: Journal parameter keys this observer reads. Both are required at issue time.
PARAM_PROJECT = "project"
PARAM_EXPECTED = "expected"

#: Result keys recorded on adoption.
RESULT_UPDATED_AT = "cf_updated_at"
RESULT_VERSION_LABEL = "cf_version_label"

#: Recorded in place of the version label when ``cf --version`` is unavailable.
#: An explicit, obviously-non-version marker rather than an empty string or a
#: plausible-looking number.
VERSION_UNAVAILABLE: Final = "unavailable"

#: The CF field carrying the record's own last-modified timestamp.
CF_FIELD_UPDATED_AT = "updatedAt"

#: The executable, and the argument vectors used. Defined once so no call site
#: assembles a command line of its own.
CF_EXECUTABLE: Final = "cf"
CF_VERSION_ARGS: Final = ("--version",)


def _cf_get_args(project: str) -> tuple[str, ...]:
    """The argument vector reading one project's record as JSON."""
    return (CF_EXECUTABLE, "get", "--json", "-p", project)


class CFProjectRecord(BaseModel):
    """A ``cf get --json`` project record.

    Every field is optional and unknown fields are ignored: the observer reads
    whichever fields the entry's ``expected`` mapping names, and CF's record
    shape is not this project's to fix. ``updatedAt`` is read separately as
    provenance.
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


def capture_version_label(timeout_seconds: float) -> str:
    """Capture ``cf --version`` as an opaque label, once per recovery pass.

    Never raises and never escalates: a failure is recorded as
    :data:`VERSION_UNAVAILABLE`. The returned string is stored and never
    compared, parsed, or ordered.
    """
    try:
        completed = subprocess.run(
            (CF_EXECUTABLE, *CF_VERSION_ARGS),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # Specific: cf missing from PATH, or the call timed out. Provenance
        # capture must never turn a clean adoption into an escalation, so this
        # is recorded rather than propagated.
        logger.warning("cannot capture cf version label", exc_info=True)
        return VERSION_UNAVAILABLE

    if completed.returncode != 0:
        logger.warning(
            "cf --version exited %d; recording the label as unavailable",
            completed.returncode,
        )
        return VERSION_UNAVAILABLE

    label = completed.stdout.strip()
    return label if label else VERSION_UNAVAILABLE


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
        project = entry.parameters.get(PARAM_PROJECT)
        expected = entry.parameters.get(PARAM_EXPECTED)

        if not isinstance(project, str) or not isinstance(expected, Mapping):
            return Unknown(
                reason="journal entry does not carry a project and expected mapping"
            )

        record = self._read_project(project)
        if isinstance(record, Unknown):
            return record

        narrowed_expected: dict[str, object] = dict(expected)  # pyright: ignore[reportUnknownArgumentType]
        return self._compare(record, narrowed_expected)

    def _read_project(self, project: str) -> CFProjectRecord | Unknown:
        """Run ``cf get --json``, returning the record or why it is unobservable.

        Each external failure mode gets a distinguishable reason, so the human
        reading the blocked state knows whether ``cf`` is missing, hung,
        failing, or emitting something unparseable.
        """
        try:
            completed = subprocess.run(
                _cf_get_args(project),
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            # Specific: cf is not on PATH. An answer, not a bug.
            logger.warning("cf is not on PATH")
            return Unknown(reason="cf is not available on PATH")
        except subprocess.TimeoutExpired:
            # Specific: cf hung. Never retried here; recovery escalates.
            logger.warning("cf get timed out after %ss", self._timeout_seconds)
            return Unknown(reason=f"cf get timed out after {self._timeout_seconds}s")
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

        return self._parse(completed.stdout)

    def _parse(self, output: str) -> CFProjectRecord | Unknown:
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

    def _compare(
        self, record: CFProjectRecord, expected: Mapping[str, object]
    ) -> Observation:
        """Compare the record against the expected values.

        All present and equal -> adopt. Any present and differing ->
        not applied. Any *absent* -> unknown, because a field the record does
        not carry is an incomplete observation rather than a mismatch.
        """
        missing = [name for name in expected if not record.has_field(name)]
        if missing:
            return Unknown(
                reason=(
                    "cf get output does not carry the expected field(s): "
                    f"{', '.join(sorted(missing))}"
                )
            )

        differing = [
            name
            for name, value in expected.items()
            if record.field_value(name) != value
        ]
        if differing:
            return NotApplied(
                reason=(
                    f"cf holds a different value for: {', '.join(sorted(differing))}"
                )
            )

        return Adopt(
            result={
                RESULT_UPDATED_AT: record.field_value(CF_FIELD_UPDATED_AT),
                RESULT_VERSION_LABEL: self.version_label,
            }
        )


__all__: Sequence[str] = [
    "CF_FIELD_UPDATED_AT",
    "PARAM_EXPECTED",
    "PARAM_PROJECT",
    "RESULT_UPDATED_AT",
    "RESULT_VERSION_LABEL",
    "VERSION_UNAVAILABLE",
    "CFProjectRecord",
    "CFReadbackObserver",
    "capture_version_label",
]
