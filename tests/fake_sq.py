"""A fake ``sq`` for the pause-handling tests (slice 223, D15).

``write_fake_sq`` writes an executable ``sq`` that replays recorded documents:

- ``sq runs wait <id> ...`` prints the document registered for ``<id>`` and exits
  with the code its ``outcome`` maps to. An unregistered id prints a ``not_found``
  document and exits 5, as the real ``sq`` does.
- ``sq run ...`` appends its argv, as one JSON array per line, to the argv record,
  prints nothing and exits with the configured code. ``--resume <id> --instructions
  <text>`` is just such a call, so the record shows the text as one element.
- Anything else exits 2.

The documents are the recordings in ``tests/fixtures/squadron``. A test registers a
recording under the run id it wants; the helper rewrites the document's ``run_id``
to that id (the one change, because ``poll_run`` rejects a document for another id).

``fake_poller`` is the in-process counterpart: a ``poll_run`` stand-in that returns
a scripted sequence per run id.
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.upstream.squadron.run_outcome import (
    OUTCOME_EXIT_CODES,
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)

SQUADRON_FIXTURES: Final = Path(__file__).parent / "fixtures" / "squadron"
PAUSED_AGENT_QUESTION: Final = "wait_paused_agent_question.json"
PAUSED_INTERACTIVE: Final = "wait_paused_interactive_checkpoint.json"
RUNNING: Final = "wait_running.json"
COMPLETED: Final = "wait_completed.json"
RUN_FILE: Final = "run_file_schema5.json"

CONFIG_FILE: Final = "fake_sq.json"
ARGV_RECORD_FILE: Final = "sq_argv.jsonl"
NOT_FOUND_EXIT_CODE: Final = OUTCOME_EXIT_CODES[RunOutcome.NOT_FOUND]
USAGE_EXIT_CODE: Final = 2

_SCRIPT = textwrap.dedent(
    """\
    #!{python}
    import json
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    config = json.loads((here / {config!r}).read_text(encoding="utf-8"))
    arguments = sys.argv[1:]

    if arguments[:2] == ["runs", "wait"] and len(arguments) > 2:
        run_id = arguments[2]
        entry = config["waits"].get(run_id)
        if entry is None:
            print(json.dumps({{"run_id": run_id, "outcome": "not_found"}}))
            sys.exit({not_found})
        print(json.dumps(entry["document"], indent=2))
        sys.exit(entry["exit_code"])
    if arguments[:1] == ["run"]:
        with open(here / {record!r}, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(arguments) + "\\n")
        if config["run_stderr"]:
            print(config["run_stderr"], file=sys.stderr)
        sys.exit(config["run_exit_code"])
    print("fake sq: unsupported command", arguments, file=sys.stderr)
    sys.exit({usage})
    """
)


def recorded_document(name: str, run_id: str) -> dict[str, object]:
    """A recording from ``tests/fixtures/squadron``, re-addressed to ``run_id``."""
    document = json.loads((SQUADRON_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return {**document, "run_id": run_id}  # pyright: ignore[reportUnknownVariableType]


def exit_code_for(document: Mapping[str, object]) -> int:
    """The exit code ``sq runs wait`` gives a document with this outcome."""
    return OUTCOME_EXIT_CODES[RunOutcome(str(document["outcome"]))]


@dataclass(frozen=True)
class FakeSq:
    """The written fake: put ``directory`` first on ``PATH``."""

    directory: Path

    @property
    def argv_record(self) -> Path:
        return self.directory / ARGV_RECORD_FILE

    def run_calls(self) -> list[list[str]]:
        """The argv (without ``sq``) of every ``sq run`` call, in order."""
        if not self.argv_record.exists():
            return []
        return [
            json.loads(line)
            for line in self.argv_record.read_text(encoding="utf-8").splitlines()
        ]


def write_fake_sq(
    directory: Path,
    *,
    waits: Mapping[str, str],
    run_exit_code: int,
    run_stderr: str,
) -> FakeSq:
    """Write the fake into ``directory``.

    Args:
        waits: Run id to the name of the recording ``sq runs wait`` replays for it.
        run_exit_code: What every ``sq run ...`` call exits with.
        run_stderr: What every ``sq run ...`` call prints on stderr (may be empty).
    """
    directory.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict[str, object]] = {}
    for run_id, name in waits.items():
        document = recorded_document(name, run_id)
        entries[run_id] = {"document": document, "exit_code": exit_code_for(document)}
    config = {
        "waits": entries,
        "run_exit_code": run_exit_code,
        "run_stderr": run_stderr,
    }
    (directory / CONFIG_FILE).write_text(json.dumps(config), encoding="utf-8")
    script = directory / "sq"
    script.write_text(
        _SCRIPT.format(
            python=sys.executable,
            config=CONFIG_FILE,
            record=ARGV_RECORD_FILE,
            not_found=NOT_FOUND_EXIT_CODE,
            usage=USAGE_EXIT_CODE,
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return FakeSq(directory)


def poll_result(name: str, run_id: str) -> RunOutcomeDocument:
    """A recording as the ``RunOutcomeDocument`` ``poll_run`` would return."""
    return RunOutcomeDocument.model_validate(recorded_document(name, run_id))


@dataclass
class FakePoller:
    """A ``poll_run`` stand-in: each call returns the next scripted result for the
    run id, repeating the last. An unscripted id is a test bug and raises."""

    script: Mapping[str, Sequence[RunPoll]]
    calls: list[str]

    def __call__(self, run_id: str, *, timeout_seconds: float) -> RunPoll:
        del timeout_seconds
        results = self.script[run_id]
        position = min(self.calls.count(run_id), len(results) - 1)
        self.calls.append(run_id)
        return results[position]


def fake_poller(script: Mapping[str, Sequence[RunPoll]]) -> FakePoller:
    return FakePoller(script=script, calls=[])


def failing_poll(reason: str) -> Callable[..., RunPoll]:
    """A ``poll_run`` stand-in that always fails."""

    def poll(run_id: str, *, timeout_seconds: float) -> RunPoll:
        del run_id, timeout_seconds
        return PollFailure(reason)

    return poll


def poll_not_found(run_id: str) -> RunOutcomeDocument:
    """What ``sq runs wait`` reports for a run it has no state for."""
    return RunOutcomeDocument(run_id=run_id, outcome=RunOutcome.NOT_FOUND)
