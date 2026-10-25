"""``start`` flags for review detection: defaults from ``ProcessSettings``."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.cli.main import build_parser
from amoeba.cli.settings_flags import start_settings
from amoeba.process.settings import DEFAULT_ROUTING_TABLE_PATH, ProcessSettings


def test_detection_defaults_come_from_process_settings() -> None:
    settings = start_settings(build_parser().parse_args(["start"]))
    defaults = ProcessSettings()
    assert settings.review_scan_interval_seconds == (
        defaults.review_scan_interval_seconds
    )
    assert settings.sq_timeout_seconds == defaults.sq_timeout_seconds


def test_each_detection_flag_overrides_its_setting() -> None:
    args = build_parser().parse_args(
        ["start", "--review-scan-interval", "0.5", "--sq-timeout", "3"]
    )
    settings = start_settings(args)
    assert settings.review_scan_interval_seconds == 0.5
    assert settings.sq_timeout_seconds == 3.0


def test_cf_data_dir_defaults_from_process_settings_and_the_flag_overrides_it() -> None:
    default = start_settings(build_parser().parse_args(["start"]))
    assert default.cf_data_dir == ProcessSettings().cf_data_dir
    assert default.cf_data_dir == Path.home() / ".config" / "context-forge"

    args = build_parser().parse_args(["start", "--cf-data-dir", "/scratch/cf"])
    assert start_settings(args).cf_data_dir == Path("/scratch/cf")


def test_the_cf_scan_interval_has_no_flag() -> None:
    assert "--cf-scan-interval" not in build_parser().format_help()
    with pytest.raises(SystemExit):
        build_parser().parse_args(["start", "--cf-scan-interval", "2"])


def test_the_environment_variable_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_FORGE_DATA_DIR", "/from/the/environment")
    settings = start_settings(build_parser().parse_args(["start"]))
    assert settings.cf_data_dir == ProcessSettings().cf_data_dir


def test_launch_grace_defaults_from_process_settings_and_the_flag_overrides_it() -> (
    None
):
    default = start_settings(build_parser().parse_args(["start"]))
    assert default.launch_grace_seconds == ProcessSettings().launch_grace_seconds

    args = build_parser().parse_args(["start", "--launch-grace", "5"])
    assert start_settings(args).launch_grace_seconds == 5.0


def test_the_sq_runs_dir_help_says_it_is_legacy_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["start", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    # The option block (not the usage line) lists each flag with its help.
    legacy_note = help_text.index(
        "Legacy matching only", help_text.index("--sq-runs-dir PATH")
    )
    assert legacy_note < help_text.rindex("--launch-grace")


def test_runner_flags_default_from_process_settings() -> None:
    settings = start_settings(build_parser().parse_args(["start"]))
    defaults = ProcessSettings()
    assert settings.tick_deadline_seconds == defaults.tick_deadline_seconds
    assert settings.tick_call_timeout_seconds == defaults.tick_call_timeout_seconds
    assert settings.run_poll_interval_seconds == defaults.run_poll_interval_seconds
    assert settings.plan_read_interval_seconds == defaults.plan_read_interval_seconds


def test_each_runner_flag_overrides_its_setting() -> None:
    args = build_parser().parse_args(
        [
            "start",
            "--tick-deadline",
            "2",
            "--tick-call-timeout",
            "3.5",
            "--run-poll-interval",
            "9",
            "--plan-read-interval",
            "45",
        ]
    )
    settings = start_settings(args)
    assert settings.tick_deadline_seconds == 2.0
    assert settings.tick_call_timeout_seconds == 3.5
    assert settings.run_poll_interval_seconds == 9.0
    assert settings.plan_read_interval_seconds == 45.0


@pytest.mark.parametrize(
    "flag",
    [
        "--tick-deadline",
        "--tick-call-timeout",
        "--run-poll-interval",
        "--plan-read-interval",
    ],
)
def test_a_non_numeric_runner_flag_is_a_usage_error(flag: str) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(["start", flag, "soon"])
    assert raised.value.code == 2


def test_help_lists_the_runner_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["start", "--help"])
    out = capsys.readouterr().out
    for flag in (
        "--tick-deadline",
        "--tick-call-timeout",
        "--run-poll-interval",
        "--plan-read-interval",
    ):
        assert flag in out


def test_the_routing_table_defaults_to_the_shipped_one_and_the_flag_overrides() -> None:
    default = start_settings(build_parser().parse_args(["start"]))
    assert default.routing_table_path == ProcessSettings().routing_table_path
    assert default.routing_table_path == DEFAULT_ROUTING_TABLE_PATH
    assert default.routing_table_path.is_file()
    assert default.routing_table_path.name == "default.yaml"

    args = build_parser().parse_args(["start", "--routing-table", "/scratch/t.yaml"])
    assert start_settings(args).routing_table_path == Path("/scratch/t.yaml")
