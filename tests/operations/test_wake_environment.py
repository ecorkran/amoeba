"""The wake command's environment and the one ``detail`` text (slice 244, D1, D6)."""

from __future__ import annotations

from amoeba.operations.wake_environment import (
    WAKE_ENV_NAMES,
    build_wake_environment,
    wake_detail,
)

MARKER = "SENDER_SECRET_MARKER"
MARKER_VALUE = "sender-only-value"


def test_only_the_set_names_of_the_constant_are_copied() -> None:
    environ = {name: f"value-of-{name}" for name in WAKE_ENV_NAMES}
    environ[MARKER] = MARKER_VALUE
    environ["AWS_SECRET_ACCESS_KEY"] = "another-sender-value"

    built = build_wake_environment(environ)

    assert built == {name: f"value-of-{name}" for name in WAKE_ENV_NAMES}
    assert MARKER not in built
    assert MARKER_VALUE not in built.values()


def test_an_unset_name_is_absent_not_empty() -> None:
    built = build_wake_environment({"PATH": "/bin", "AMOEBA_HOME": "/state"})

    assert built == {"PATH": "/bin", "AMOEBA_HOME": "/state"}
    assert "HOME" not in built


def test_the_context_forge_data_directory_reaches_the_command() -> None:
    # The woken agent's `amoeba` calls resolve its project through Context Forge,
    # which must look in the same data directory as the sender's did.
    built = build_wake_environment({"CONTEXT_FORGE_DATA_DIR": "/cf-data"})

    assert built == {"CONTEXT_FORGE_DATA_DIR": "/cf-data"}


def test_an_empty_value_that_is_set_is_kept() -> None:
    assert build_wake_environment({"LANG": ""}) == {"LANG": ""}


def test_an_os_error_gives_its_class_and_strerror_without_the_filename() -> None:
    error = FileNotFoundError(2, "No such file or directory", f"/bin/{MARKER}-agent")

    detail = wake_detail(error)

    assert detail == "FileNotFoundError: No such file or directory"
    assert MARKER not in detail


def test_another_exception_gives_its_class_name_only() -> None:
    assert wake_detail(ValueError(f"bad {MARKER}")) == "ValueError"


def test_an_os_error_without_strerror_gives_its_class_name() -> None:
    assert wake_detail(OSError(f"{MARKER} only")) == "OSError"
