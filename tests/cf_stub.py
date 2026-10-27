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

Pointer commands (slice 125) read and write the project state file named by
``CF_STUB_STATE`` (see ``write_cf_state``), shaped like one ``projects.json`` entry
with ``worktrees`` (``worktreePath``, ``indexRange``, ``activeSlice``) and a
``slices`` map of index to ``NNN-slice.{name}``. CF chooses a worktree by working
directory, and so does the stub: the worktree whose ``worktreePath`` is the longest
prefix of the process's cwd, else the project level.

* ``cf set -p <id> slice <index>`` stores the slice's stem on that worktree
  (``activeSlice``) or on the project (``fileSlice``) and bumps ``updatedAt``. An
  index with no ``slices`` entry exits 1 with ``ARTIFACT_NOT_FOUND`` on stderr. A
  value already stored writes nothing.
* ``cf get --json -p <id>`` prints the project's fields; for a worktree, its path
  as ``projectPath``, its ``activeSlice`` as ``fileSlice`` and a ``worktree`` object,
  as the real ``cf`` does (``tests/fixtures/cf/cf_get_worktree.json``).

``CF_STUB_SET_MODE`` and ``CF_STUB_GET_MODE`` make those commands ``fail`` (exit 1)
or ``sleep``; ``CF_STUB_GET_QUIRK`` bends what ``get`` reports (see ``GetQuirk``).

``status`` fixtures and ``config get`` (slice 128) are in ``cf_stub_gates.py``.

``CF_STUB_MODE`` selects a failure; ``CF_STUB_LOG`` appends each invocation's
arguments. ``write_cf_stub`` is the only definition; a test puts the returned
directory first on ``PATH``.
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from cf_stub_gates import STATE_ENV, gate_commands_script

INITIATIVES_FIXTURE = (
    Path(__file__).parent / "fixtures" / "cf" / "list_initiatives_a.json"
)
SLICE_ERROR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "cf" / "list_slices_error.json"
)
MODE_ENV = "CF_STUB_MODE"
LOG_ENV = "CF_STUB_LOG"
PLAN_DIR_ENV = "CF_STUB_PLAN_DIR"
SET_MODE_ENV = "CF_STUB_SET_MODE"
GET_MODE_ENV = "CF_STUB_GET_MODE"
GET_QUIRK_ENV = "CF_STUB_GET_QUIRK"
STUB_NAME = "cf"

#: What the ``cf set`` error says on stderr when the index has no slice-plan entry.
ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
#: A path and a worktree id the ``get`` quirks report instead of the real ones.
QUIRK_PROJECT_PATH = "/elsewhere/not-this-checkout"
QUIRK_WORKTREE_ID = "wt_not_this_worktree"


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


class PointerMode(StrEnum):
    """How ``cf set`` or ``cf get`` misbehaves; absent means it works."""

    #: Exit 1 with a message on stderr.
    FAIL = "fail"
    #: Sleep far past any timeout a test sets.
    SLEEP = "sleep"


class GetQuirk(StrEnum):
    """What ``cf get`` reports wrongly; absent means the truth."""

    #: No ``fileSlice`` field at all.
    OMIT_FILE_SLICE = "omit_file_slice"
    #: A ``projectPath`` that is not the checkout the call ran in.
    OTHER_PROJECT_PATH = "other_project_path"
    #: A ``worktree.id`` that is not the worktree the call ran in.
    OTHER_WORKTREE_ID = "other_worktree_id"


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

    if arguments[:1] in (["set"], ["get"]):
        import datetime
        import json

        command = arguments[0]
        pointer_mode = os.environ.get(
            {set_mode_env!r} if command == "set" else {get_mode_env!r}
        )
        if pointer_mode == {pointer_fail!r}:
            print("stub cf: " + command + " failed", file=sys.stderr)
            sys.exit(1)
        if pointer_mode == {pointer_sleep!r}:
            time.sleep(600)
        state_path = os.environ[{state_env!r}]
        with open(state_path, encoding="utf-8") as handle:
            entry = json.load(handle)

        # CF chooses a worktree by working directory alone: the longest prefix wins.
        cwd = os.path.realpath(os.getcwd())
        worktree = None
        for candidate in entry.get("worktrees", []):
            root = os.path.realpath(candidate["worktreePath"])
            if cwd == root or cwd.startswith(root + os.sep):
                if worktree is None or len(root) > len(
                    os.path.realpath(worktree["worktreePath"])
                ):
                    worktree = candidate

        if command == "set":
            if len(arguments) != 5 or arguments[3] != "slice":
                print("stub cf: unexpected arguments", arguments, file=sys.stderr)
                sys.exit(2)
            stem = entry.get("slices", dict()).get(arguments[4])
            if stem is None:
                print({not_found!r} + ": no slice " + arguments[4], file=sys.stderr)
                sys.exit(1)
            target = entry if worktree is None else worktree
            field = "fileSlice" if worktree is None else "activeSlice"
            if target.get(field) != stem:
                target[field] = stem
                entry["updatedAt"] = datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat()
                with open(state_path, "w", encoding="utf-8") as handle:
                    json.dump(entry, handle)
            print("slice " + stem)
            sys.exit(0)

        document = dict(
            (key, value)
            for key, value in entry.items()
            if key not in ("worktrees", "slices")
        )
        if worktree is not None:
            document["projectPath"] = worktree["worktreePath"]
            if "activeSlice" in worktree:
                document["fileSlice"] = worktree["activeSlice"]
            document["worktree"] = worktree
        quirk = os.environ.get({quirk_env!r})
        if quirk == {omit_file_slice!r}:
            document.pop("fileSlice", None)
        if quirk == {other_project_path!r}:
            document["projectPath"] = {quirk_path!r}
        if quirk == {other_worktree_id!r} and worktree is not None:
            document["worktree"] = dict(worktree, id={quirk_worktree!r})
        print(json.dumps(document))
        sys.exit(0)

    {gate_commands}
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
            gate_commands=gate_commands_script(),
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
            set_mode_env=SET_MODE_ENV,
            get_mode_env=GET_MODE_ENV,
            pointer_fail=PointerMode.FAIL.value,
            pointer_sleep=PointerMode.SLEEP.value,
            state_env=STATE_ENV,
            not_found=ARTIFACT_NOT_FOUND,
            quirk_env=GET_QUIRK_ENV,
            omit_file_slice=GetQuirk.OMIT_FILE_SLICE.value,
            other_project_path=GetQuirk.OTHER_PROJECT_PATH.value,
            other_worktree_id=GetQuirk.OTHER_WORKTREE_ID.value,
            quirk_path=QUIRK_PROJECT_PATH,
            quirk_worktree=QUIRK_WORKTREE_ID,
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir


def write_cf_state(
    path: Path,
    *,
    cf_project_id: str,
    project_path: Path,
    worktrees: Sequence[Mapping[str, object]] = (),
    slices: Mapping[int, str] | None = None,
    file_slice: str | None = None,
) -> Path:
    """Write the state file ``STATE_ENV`` names: one ``projects.json``-shaped entry.

    ``worktrees`` are entries with ``id``, ``name``, ``worktreePath``, ``indexRange``
    and, once pointed, ``activeSlice``. ``slices`` maps an index to its
    ``NNN-slice.{name}`` stem: what ``cf set`` can point at.
    """
    entry: dict[str, object] = {
        "id": cf_project_id,
        "name": "stub-project",
        "projectPath": str(project_path),
        "updatedAt": "2026-10-24T00:00:00.000Z",
        "slices": {str(index): stem for index, stem in (slices or {}).items()},
    }
    if file_slice is not None:
        entry["fileSlice"] = file_slice
    if worktrees:
        entry["worktrees"] = [dict(worktree) for worktree in worktrees]
    path.write_text(json.dumps(entry), encoding="utf-8")
    return path


def read_cf_state(path: Path) -> dict[str, Any]:
    """The state file as ``cf set`` left it."""
    state: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return state
