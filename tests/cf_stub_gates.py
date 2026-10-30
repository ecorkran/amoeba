"""The stub ``cf``'s ``config get`` mode (slice 128, D5).

``cf_stub.py`` renders ``gate_commands_script()`` into the stub, so the stub answers
``cf config get <key> --json`` from the JSON file ``CF_STUB_CONFIG`` (key to string
value); a key it does not hold answers the empty string, as CF does for an unset key.

``CF_STUB_CONFIG_MODE`` bends that command (``GateMode``). Every call is logged by the
stub, as before.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

CONFIG_ENV = "CF_STUB_CONFIG"
CONFIG_MODE_ENV = "CF_STUB_CONFIG_MODE"


class GateMode(StrEnum):
    """How ``config get`` misbehaves; absent means it answers."""

    #: Exit 1 with a message on stderr.
    FAIL = "fail"
    #: Sleep far past any timeout a test sets.
    SLEEP = "sleep"
    #: Exit 0 printing text that is not JSON.
    NOT_JSON = "not_json"
    #: A JSON object with no ``value``.
    NO_VALUE = "no_value"


_SCRIPT = textwrap.dedent(
    """\
    if arguments[:2] == ["config", "get"]:
        import json

        gate_mode = os.environ.get({config_mode_env!r})
        if gate_mode == {fail!r}:
            print("stub cf: " + arguments[0] + " failed", file=sys.stderr)
            sys.exit(1)
        if gate_mode == {sleep!r}:
            time.sleep(600)
        if gate_mode == {not_json!r}:
            print("this is not json")
            sys.exit(0)
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
    """The stub code for ``config get``, ready to embed."""
    return _SCRIPT.format(
        config_mode_env=CONFIG_MODE_ENV,
        config_env=CONFIG_ENV,
        fail=GateMode.FAIL.value,
        sleep=GateMode.SLEEP.value,
        not_json=GateMode.NOT_JSON.value,
        no_value=GateMode.NO_VALUE.value,
    )


def write_config_values(path: Path, values: Mapping[str, str]) -> Path:
    """Write the ``CONFIG_ENV`` file: the value each config key answers."""
    path.write_text(json.dumps(dict(values)), encoding="utf-8")
    return path
