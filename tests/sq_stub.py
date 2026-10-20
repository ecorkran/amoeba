"""A stub ``sq`` reproducing the interface pruning depends on (slice 110, D3/D8).

No test runs the real ``sq``: it needs a provider's credentials and is not part
of what these tests prove. The stub reproduces what was observed of
``sq runs prune`` (Squadron 0.23.3, 20261019): it takes run ids and ``--yes``,
deletes ``$HOME/.config/squadron/runs/{id}.json`` for each, exits 1 when a named
file is already gone (that is still the goal state), and refuses a live run with
exit 1, leaving its file.

``write_sq_stub`` is the only definition. A test puts the returned directory
first on ``PATH`` and picks a behavior with the environment variables below.
"""

from __future__ import annotations

import sys
import textwrap
from enum import StrEnum
from pathlib import Path

#: Environment variables the stub reads.
MODE_ENV = "SQ_STUB_MODE"
#: A file the stub appends each invocation's arguments to, one line each.
LOG_ENV = "SQ_STUB_LOG"
#: The one run id the ``refuse`` mode keeps, as a live run would be.
REFUSE_ENV = "SQ_STUB_REFUSE"

STUB_NAME = "sq"


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
    import os
    import sys
    import time
    from pathlib import Path

    mode = os.environ[{mode_env!r}]
    log = os.environ.get({log_env!r})
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(" ".join(sys.argv[1:]) + "\\n")

    arguments = sys.argv[1:]
    if arguments[:2] != ["runs", "prune"]:
        print("stub sq: unexpected arguments", arguments, file=sys.stderr)
        sys.exit(2)
    ids = [argument for argument in arguments[2:] if not argument.startswith("--")]
    runs_dir = Path.home() / ".config" / "squadron" / "runs"

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
            fail=StubMode.FAIL.value,
            sleep=StubMode.SLEEP.value,
            refuse_one=StubMode.REFUSE_ONE.value,
            delete_then_exit_one=StubMode.DELETE_THEN_EXIT_ONE.value,
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir
