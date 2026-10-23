"""A stub ``sq`` reproducing the interfaces recovery and pruning depend on.

No test runs the real ``sq``: it needs a provider's credentials and is not part
of what these tests prove. The stub plays Squadron for two commands.

``sq runs prune`` (observed on Squadron 0.23.3, 20261019, slice 110, D3/D8): it
takes run ids and ``--yes``, deletes the named run for each, exits 1 when a
named run is already gone (that is still the goal state), and refuses a live
run with exit 1, leaving it. Since slice 120 "the run" is the outcome document
below, so a pruned id then answers ``not_found`` to ``runs wait``.

``sq runs wait <id> --timeout 0 --json`` (slice 120, D2): it prints the outcome
document kept in the stub's own state directory, ``STUB_STATE_RELATIVE`` under
``$HOME``, and exits with the code for that document's ``outcome``. A missing
id prints ``{"run_id": id, "outcome": "not_found"}`` and exits 5. That directory
is deliberately not ``.config/squadron/runs``, so a test can put contrary files
in the runs directory and show that nothing reads them.

``sq run <pipeline> --run-id <id> -p k=v`` (slice 122): the detached launch. It
refuses an id that is malformed (exit 2) or already has state (exit 1), and an
unknown flag (exit 2). Otherwise it writes the id's document as still running
(``timed_out``), prints ``run_id=<id>`` on stderr, sleeps ``RUN_SECONDS_ENV``,
writes the final document (``RUN_OUTCOME_ENV``, ``completed`` unless set) and
exits 0. ``RUN_MODE_ENV`` forces a failure case; see :class:`RunMode`.

``write_sq_stub`` is the only definition. A test puts the returned directory
first on ``PATH`` and picks a behavior with the environment variables below.
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Final

#: Environment variables the stub reads.
MODE_ENV = "SQ_STUB_MODE"
#: A file the stub appends each invocation's arguments to, one line each.
LOG_ENV = "SQ_STUB_LOG"
#: The one run id the ``refuse`` mode keeps, as a live run would be.
REFUSE_ENV = "SQ_STUB_REFUSE"

#: ``sq run`` settings: how long the run lasts, how it ends, how it misbehaves.
RUN_SECONDS_ENV = "SQ_STUB_RUN_SECONDS"
RUN_OUTCOME_ENV = "SQ_STUB_RUN_OUTCOME"
RUN_MODE_ENV = "SQ_STUB_RUN_MODE"
#: How long ``late_line`` waits before it creates the state and prints the line.
RUN_LATE_SECONDS_ENV = "SQ_STUB_RUN_LATE_SECONDS"

STUB_NAME = "sq"

#: Squadron's run id rule, restated because the stub is a separate program.
STUB_RUN_ID_PATTERN: Final = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"

#: Where the stub keeps one outcome document per run id, relative to ``$HOME``.
STUB_STATE_RELATIVE: Final = Path(".sq-stub") / "runs"

#: The exit code for each ``runs wait`` outcome. This is the stub's own copy of
#: Squadron's rule, written out here and not imported from ``amoeba``.
STUB_EXIT_CODES: Final[Mapping[str, int]] = {
    "completed": 0,
    "failed": 1,
    "paused": 3,
    "timed_out": 4,
    "not_found": 5,
    "unreadable": 6,
    "unknown_status": 7,
    "orphaned": 8,
}


class StubMode(StrEnum):
    """What the stub does when asked to prune."""

    #: Delete each named file; exit 1 if any was already gone.
    DELETE = "delete"
    #: Delete each named file, then exit 1 anyway: another process removed one
    #: first, and sq reported it. The goal state is reached all the same.
    DELETE_THEN_EXIT_ONE = "delete_then_exit_one"
    #: As ``DELETE``, but keep the run named by ``REFUSE_ENV`` and exit 1.
    REFUSE_ONE = "refuse_one"
    #: Delete nothing and exit 1 with a message.
    FAIL = "fail"
    #: Sleep far past any timeout a test sets.
    SLEEP = "sleep"


class RunMode(StrEnum):
    """How ``sq run`` misbehaves; absent means a normal run."""

    #: Exit 1 before any line and before any state.
    EXIT_BEFORE_LINE = "exit_before_line"
    #: Create the state, never print the line.
    NO_LINE = "no_line"
    #: Sleep ``RUN_LATE_SECONDS_ENV``, then create the state and print the line.
    LATE_LINE = "late_line"
    #: Exit 2 with no state.
    USAGE_ERROR = "usage_error"


_SCRIPT = textwrap.dedent(
    """\
    #!{python}
    import json
    import os
    import re
    import sys
    import time
    from pathlib import Path

    log = os.environ.get({log_env!r})
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(" ".join(sys.argv[1:]) + "\\n")

    arguments = sys.argv[1:]
    exit_codes = {exit_codes!r}

    if arguments[:2] == ["runs", "wait"]:
        # runs wait works without a mode: it only reads the stub's state files.
        if len(arguments) != 6 or arguments[3:] != ["--timeout", "0", "--json"]:
            print("stub sq: unexpected arguments", arguments, file=sys.stderr)
            sys.exit(2)
        run_id = arguments[2]
        state_file = Path.home().joinpath(*{state_parts!r}) / (run_id + ".json")
        if not state_file.exists():
            print(json.dumps(dict(run_id=run_id, outcome="not_found")))
            sys.exit(exit_codes["not_found"])
        text = state_file.read_text(encoding="utf-8")
        outcome = json.loads(text).get("outcome")
        if outcome not in exit_codes:
            print("stub sq: no exit code for outcome", repr(outcome), file=sys.stderr)
            sys.exit(2)
        print(text)
        sys.exit(exit_codes[outcome])

    state_dir = Path.home().joinpath(*{state_parts!r})

    if arguments[:1] == ["run"]:
        run_mode = os.environ.get({run_mode_env!r})
        if run_mode == {usage_error!r}:
            print("stub sq: usage error", file=sys.stderr)
            sys.exit(2)
        pipelines = []
        run_id = None
        rest = iter(arguments[1:])
        for argument in rest:
            if argument == "--run-id":
                run_id = next(rest, None)
            elif argument == "-p":
                next(rest, None)
            elif argument.startswith("-"):
                print("stub sq: unknown flag", argument, file=sys.stderr)
                sys.exit(2)
            else:
                pipelines.append(argument)
        if len(pipelines) != 1 or run_id is None:
            print("stub sq: need a pipeline and --run-id", file=sys.stderr)
            sys.exit(2)
        if not re.fullmatch({run_id_pattern!r}, run_id):
            print("stub sq: invalid run id", repr(run_id), file=sys.stderr)
            sys.exit(2)
        if run_mode == {exit_before_line!r}:
            sys.exit(1)
        if run_mode == {late_line!r}:
            time.sleep(float(os.environ[{run_late_env!r}]))
        state_file = state_dir / (run_id + ".json")
        if state_file.exists():
            print("stub sq: run already exists", run_id, file=sys.stderr)
            sys.exit(1)

        def write_state(outcome):
            state_dir.mkdir(parents=True, exist_ok=True)
            document = dict(run_id=run_id, outcome=outcome, status=outcome)
            state_file.write_text(json.dumps(document), encoding="utf-8")

        write_state("timed_out")
        if run_mode != {no_line!r}:
            print("run_id=" + run_id, file=sys.stderr, flush=True)
        time.sleep(float(os.environ[{run_seconds_env!r}]))
        write_state(os.environ.get({run_outcome_env!r}, "completed"))
        sys.exit(0)

    mode = os.environ[{mode_env!r}]
    if arguments[:2] != ["runs", "prune"]:
        print("stub sq: unexpected arguments", arguments, file=sys.stderr)
        sys.exit(2)
    ids = [argument for argument in arguments[2:] if not argument.startswith("--")]
    runs_dir = Path.home().joinpath(*{state_parts!r})

    if mode == {fail!r}:
        print("stub sq: prune failed", file=sys.stderr)
        sys.exit(1)
    if mode == {sleep!r}:
        time.sleep(600)
    refused = os.environ.get({refuse_env!r})
    status = 1 if mode == {delete_then_exit_one!r} else 0
    for run_id in ids:
        target = runs_dir / (run_id + ".json")
        if mode == {refuse_one!r} and run_id == refused:
            print("stub sq: run is live: " + run_id, file=sys.stderr)
            status = 1
        elif target.exists():
            target.unlink()
        else:
            status = 1
    sys.exit(status)
    """
)


def write_sq_stub(bin_dir: Path) -> Path:
    """Write an executable ``sq`` into ``bin_dir`` and return ``bin_dir``."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / STUB_NAME
    script.write_text(
        _SCRIPT.format(
            python=sys.executable,
            mode_env=MODE_ENV,
            log_env=LOG_ENV,
            refuse_env=REFUSE_ENV,
            exit_codes=dict(STUB_EXIT_CODES),
            state_parts=STUB_STATE_RELATIVE.parts,
            fail=StubMode.FAIL.value,
            sleep=StubMode.SLEEP.value,
            refuse_one=StubMode.REFUSE_ONE.value,
            run_mode_env=RUN_MODE_ENV,
            run_seconds_env=RUN_SECONDS_ENV,
            run_outcome_env=RUN_OUTCOME_ENV,
            run_late_env=RUN_LATE_SECONDS_ENV,
            run_id_pattern=STUB_RUN_ID_PATTERN,
            usage_error=RunMode.USAGE_ERROR.value,
            exit_before_line=RunMode.EXIT_BEFORE_LINE.value,
            no_line=RunMode.NO_LINE.value,
            late_line=RunMode.LATE_LINE.value,
            delete_then_exit_one=StubMode.DELETE_THEN_EXIT_ONE.value,
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir


def write_outcome_document(home: Path, document: Mapping[str, object]) -> Path:
    """Write ``document`` as the stub's outcome document for its ``run_id``.

    The caller passes every field; this adds nothing. ``home`` is the ``HOME``
    the stub will run under.
    """
    state_dir = home / STUB_STATE_RELATIVE
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / f"{document['run_id']}.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target
