"""The stub ``cf``'s gate and config modes (slice 128, D1, D5).

``cf_stub.py`` renders ``gate_commands_script()`` into the stub, so the stub answers:

* ``cf status --json [-p <id>] [--worktree <id>]`` with a captured fixture, byte for
  byte. ``CF_STUB_STATUS_MAP`` names a JSON file mapping a working directory (a real
  path) to a fixture path, so two checkouts can stand at different gate positions.
  ``CF_STUB_STATUS_FIXTURE`` is the answer for any other directory. With neither set
  (or no entry for the directory), the stub gives its probe answer, unchanged.
* ``cf config get <key> --json`` from the JSON file ``CF_STUB_CONFIG`` (key to string
  value); a key it does not hold answers the empty string, as CF does for an unset key.

``CF_STUB_STATUS_MODE`` and ``CF_STUB_CONFIG_MODE`` bend those commands (``GateMode``).
Every call is logged by the stub, as before.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

STATUS_FIXTURE_ENV = "CF_STUB_STATUS_FIXTURE"
STATUS_MAP_ENV = "CF_STUB_STATUS_MAP"
STATUS_MODE_ENV = "CF_STUB_STATUS_MODE"
CONFIG_ENV = "CF_STUB_CONFIG"
CONFIG_MODE_ENV = "CF_STUB_CONFIG_MODE"


class GateMode(StrEnum):
    """How ``status`` or ``config get`` misbehaves; absent means it answers."""

    #: Exit 1 with a message on stderr.
    FAIL = "fail"
    #: Sleep far past any timeout a test sets.
    SLEEP = "sleep"
    #: Exit 0 printing text that is not JSON.
    NOT_JSON = "not_json"
    #: ``config get`` only: a JSON object with no ``value``.
    NO_VALUE = "no_value"


_SCRIPT = textwrap.dedent(
    """\
    if arguments[:1] == ["status"] or arguments[:2] == ["config", "get"]:
        import json

        is_status = arguments[0] == "status"
        gate_mode = os.environ.get(
            {status_mode_env!r} if is_status else {config_mode_env!r}
        )
        if gate_mode == {fail!r}:
            print("stub cf: " + arguments[0] + " failed", file=sys.stderr)
            sys.exit(1)
        if gate_mode == {sleep!r}:
            time.sleep(600)
        if gate_mode == {not_json!r}:
            print("this is not json")
            sys.exit(0)
        if is_status:
            fixture = None
            map_path = os.environ.get({status_map_env!r})
            if map_path:
                with open(map_path, encoding="utf-8") as handle:
                    fixture = json.load(handle).get(os.path.realpath(os.getcwd()))
            fixture = fixture or os.environ.get({status_fixture_env!r})
            if fixture:
                with open(fixture, "rb") as handle:
                    sys.stdout.buffer.write(handle.read())
                sys.stdout.flush()
                sys.exit(0)
            # No fixture: fall through to the probe answer below.
        else:
            key = arguments[2]
            values = dict()
            config_path = os.environ.get({config_env!r})
            if config_path:
                with open(config_path, encoding="utf-8") as handle:
                    values = json.load(handle)
            document = dict(key=key)
            if gate_mode != {no_value!r}:
                document["value"] = values.get(key, "")
                document["source"] = "project" if key in values else "default"
                document["description"] = "stub config key"
            print(json.dumps(document, indent=2))
            sys.exit(0)
    """
)


def gate_commands_script() -> str:
    """The stub code for ``status`` fixtures and ``config get``, ready to embed."""
    return _SCRIPT.format(
        status_mode_env=STATUS_MODE_ENV,
        config_mode_env=CONFIG_MODE_ENV,
        status_map_env=STATUS_MAP_ENV,
        status_fixture_env=STATUS_FIXTURE_ENV,
        config_env=CONFIG_ENV,
        fail=GateMode.FAIL.value,
        sleep=GateMode.SLEEP.value,
        not_json=GateMode.NOT_JSON.value,
        no_value=GateMode.NO_VALUE.value,
    )


def write_status_map(path: Path, fixtures_by_directory: Mapping[Path, Path]) -> Path:
    """Write the ``STATUS_MAP_ENV`` file: each directory's status fixture."""
    path.write_text(
        json.dumps(
            {
                str(directory.resolve()): str(fixture)
                for directory, fixture in fixtures_by_directory.items()
            }
        ),
        encoding="utf-8",
    )
    return path


def write_config_values(path: Path, values: Mapping[str, str]) -> Path:
    """Write the ``CONFIG_ENV`` file: the value each config key answers."""
    path.write_text(json.dumps(dict(values)), encoding="utf-8")
    return path
