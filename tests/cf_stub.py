"""A stub ``cf`` for the Runner's per-link shape probes (slice 122, D9).

No test runs the real ``cf``. The stub answers the two probe commands, in the
shapes observed on Context Forge 0.19.x (20261020):

* ``cf status --json -p <id>`` prints a JSON object.
* ``cf list initiatives --json -a -p <id>`` prints the captured initiatives
  array (``tests/fixtures/cf/list_initiatives_a.json``); without ``-a`` it
  exits 2, as an unexpected invocation.

Plan reads (slice 123) answer from the directory ``CF_STUB_PLAN_DIR``:

* ``cf list initiatives --json -a`` prints ``initiatives.json`` (the captured
  fixture when the directory has none).
* ``cf list slices <index> --json`` prints ``slices-<index>.json``. When there is
  none, it prints the captured error document on **stderr** and exits 1, as the
  real ``cf`` does for an initiative without a slice plan.
* ``<name>.<n>.json`` files (``slices-120.1.json``, ``slices-120.2.json``) answer
  successive calls in order, the last repeating, so a test can change the plan
  between reads. A ``<name>.count`` file in the directory holds the call count.

``CF_STUB_MODE`` selects a failure; ``CF_STUB_LOG`` appends each invocation's
arguments. ``write_cf_stub`` is the only definition; a test puts the returned
directory first on ``PATH``.
"""

from __future__ import annotations

import sys
import textwrap
from enum import StrEnum
from pathlib import Path

INITIATIVES_FIXTURE = (
    Path(__file__).parent / "fixtures" / "cf" / "list_initiatives_a.json"
)
SLICE_ERROR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "cf" / "list_slices_error.json"
)
MODE_ENV = "CF_STUB_MODE"
LOG_ENV = "CF_STUB_LOG"
PLAN_DIR_ENV = "CF_STUB_PLAN_DIR"
STUB_NAME = "cf"


class CfMode(StrEnum):
    """What the stub answers."""

    #: The healthy shapes.
    GOOD = "good"
    #: Exit 0 with no output, as a deleted CF project does.
    EMPTY = "empty"
    #: An array for status and an object for initiatives.
    WRONG_FORM = "wrong_form"
    #: Exit 1 with a message on stderr.
    FAIL = "fail"
    #: Sleep far past any timeout a test sets.
    SLEEP = "sleep"


_SCRIPT = textwrap.dedent(
    """\
    #!{python}
    import os
    import sys
    import time

    log = os.environ.get({log_env!r})
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(" ".join(sys.argv[1:]) + "\\n")

    arguments = sys.argv[1:]
    mode = os.environ.get({mode_env!r}, {good!r})
    if len(arguments) < 3 or arguments[-2] != "-p" or "--json" not in arguments:
        print("stub cf: unexpected arguments", arguments, file=sys.stderr)
        sys.exit(2)
    is_status = arguments[0] == "status"
    is_slices = arguments[:2] == ["list", "slices"]
    if not is_status and not is_slices and "-a" not in arguments:
        print("stub cf: initiatives needs -a", arguments, file=sys.stderr)
        sys.exit(2)
    if mode == {fail!r}:
        print("stub cf: failed", file=sys.stderr)
        sys.exit(1)
    if mode == {sleep!r}:
        time.sleep(600)
    if mode == {empty!r}:
        sys.exit(0)
    wrong = mode == {wrong_form!r}
    plan_dir = os.environ.get({plan_env!r})

    def plan_text(name):
        # name.<n>.json files answer in order, one per call, the last one
        # repeating; else name.json. None when the plan dir has neither.
        if not plan_dir:
            return None
        numbered = sorted(
            (entry for entry in os.listdir(plan_dir)
             if entry.startswith(name + ".") and entry.endswith(".json")
             and entry[len(name) + 1:-5].isdigit()),
            key=lambda entry: int(entry[len(name) + 1:-5]),
        )
        if numbered:
            counter = os.path.join(plan_dir, name + ".count")
            seen = int(open(counter).read()) if os.path.exists(counter) else 0
            with open(counter, "w") as handle:
                handle.write(str(seen + 1))
            chosen = numbered[min(seen, len(numbered) - 1)]
            return open(os.path.join(plan_dir, chosen), encoding="utf-8").read()
        path = os.path.join(plan_dir, name + ".json")
        return open(path, encoding="utf-8").read() if os.path.exists(path) else None

    if is_status:
        print("[]" if wrong else '{{"project": "stub"}}')
    elif is_slices:
        text = plan_text("slices-" + arguments[2])
        if text is None:
            # CF prints this document on stderr, and exits 1.
            print(
                open({error_fixture!r}, encoding="utf-8").read(),
                end="",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[]" if wrong else text)
    else:
        text = plan_text("initiatives")
        if text is None:
            text = open({fixture!r}, encoding="utf-8").read()
        print("{{}}" if wrong else text, end="")
    """
)


def write_cf_stub(bin_dir: Path) -> Path:
    """Write an executable ``cf`` into ``bin_dir`` and return ``bin_dir``."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / STUB_NAME
    script.write_text(
        _SCRIPT.format(
            python=sys.executable,
            log_env=LOG_ENV,
            mode_env=MODE_ENV,
            good=CfMode.GOOD.value,
            fail=CfMode.FAIL.value,
            sleep=CfMode.SLEEP.value,
            empty=CfMode.EMPTY.value,
            wrong_form=CfMode.WRONG_FORM.value,
            fixture=str(INITIATIVES_FIXTURE),
            error_fixture=str(SLICE_ERROR_FIXTURE),
            plan_env=PLAN_DIR_ENV,
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir
