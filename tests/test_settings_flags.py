"""``start`` flags for review detection: defaults from ``ProcessSettings``."""

from __future__ import annotations

from amoeba.cli.main import build_parser
from amoeba.cli.settings_flags import start_settings
from amoeba.process.settings import ProcessSettings


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
