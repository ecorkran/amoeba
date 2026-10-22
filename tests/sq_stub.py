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

STUB_NAME = "sq"

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


_SCRIPT = textwrap.dedent(
    """\
    #!{python}
    import json
    import os
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
