"""The rotating hub log (slice 260, D16)."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from amoeba.hub.hub_log import refusal_line, start_hub_log

MAX_BYTES = 400
KEPT = 3


@pytest.fixture
def handler(tmp_path: Path) -> Iterator[RotatingFileHandler]:
    root = logging.getLogger()
    level = root.level
    started = start_hub_log(tmp_path / "logs" / "hub" / "hub.log", MAX_BYTES, KEPT)
    yield started
    root.removeHandler(started)
    root.setLevel(level)
    started.close()


def test_writing_past_the_limit_leaves_at_most_kept_files(
    tmp_path: Path, handler: RotatingFileHandler
) -> None:
    logger = logging.getLogger("amoeba.test")

    for number in range(200):
        logger.info("a line of some length to fill the file %s", number)
    handler.flush()

    files = sorted((tmp_path / "logs" / "hub").iterdir())
    assert len(files) == KEPT
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == KEPT - 1


def test_the_librarys_own_loggers_land_in_the_file(
    tmp_path: Path, handler: RotatingFileHandler
) -> None:
    logging.getLogger("uvicorn.error").warning("Invalid HTTP request received.")
    logging.getLogger("asyncio").error("SSL handshake failed")
    handler.flush()

    text = (tmp_path / "logs" / "hub" / "hub.log").read_text(encoding="utf-8")
    assert "Invalid HTTP request received." in text
    assert "SSL handshake failed" in text


def test_a_refusal_line_has_the_time_peer_code_and_machine() -> None:
    line = refusal_line(
        datetime(2026, 11, 21, 9, 0, tzinfo=UTC), "10.0.0.5", "bad_token", "alpha"
    )

    assert "2026-11-21T09:00:00+00:00" in line
    assert "10.0.0.5" in line
    assert "bad_token" in line
    assert "machine=alpha" in line


def test_a_refusal_line_has_no_machine_for_a_bad_token() -> None:
    line = refusal_line(
        datetime(2026, 11, 21, tzinfo=UTC), "10.0.0.5", "bad_token", None
    )

    assert "machine=-" in line


def test_a_refusal_line_cannot_be_given_a_token_body_or_document() -> None:
    parameters = set(inspect.signature(refusal_line).parameters)

    assert parameters == {"time", "peer", "code", "machine"}
