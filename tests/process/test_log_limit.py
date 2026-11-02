"""The log byte budget: a loop that logs forever stops at the limit."""

from __future__ import annotations

import io
import logging

from amoeba.process.log_limit import BoundedStreamHandler

LIMIT = 2_000
#: Room for the one notice line written when the limit is reached.
NOTICE_ALLOWANCE = 200


def _logger(stream: io.StringIO, limit: int = LIMIT) -> logging.Logger:
    logger = logging.getLogger(f"log-limit-test-{id(stream)}")
    logger.handlers = [BoundedStreamHandler(stream, limit)]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


def test_output_stops_at_the_limit_and_says_so_once() -> None:
    stream = io.StringIO()
    logger = _logger(stream)

    for number in range(10_000):
        logger.error("a record that repeats forever, number %d", number)

    written = stream.getvalue()
    assert len(written.encode()) <= LIMIT + NOTICE_ALLOWANCE
    assert written.count("log output limit") == 1
    assert written.rstrip().endswith("until this process restarts")


def test_a_process_under_the_limit_is_untouched() -> None:
    stream = io.StringIO()
    logger = _logger(stream)

    logger.info("first")
    logger.info("second")

    assert stream.getvalue() == "first\nsecond\n"


def test_an_exception_traceback_counts_toward_the_limit() -> None:
    stream = io.StringIO()
    logger = _logger(stream)

    for _ in range(1_000):
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logger.exception("tick failed")

    assert len(stream.getvalue().encode()) <= LIMIT + NOTICE_ALLOWANCE
