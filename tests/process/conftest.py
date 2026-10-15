"""Fixtures for driving the inbox tenant in-process."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from detection_harness import DetectionRig
from local_host_harness import LocalHost

from amoeba.process.settings import ProcessSettings


@pytest.fixture
def local_host(supervisor_dir: Path) -> Iterator[LocalHost]:
    """A ``LocalHost`` over ``supervisor_dir``, its stores closed on teardown.

    Safety: every store it opens lies under pytest's ``tmp_path``.
    """
    host = LocalHost(supervisor_dir, ProcessSettings())
    try:
        yield host
    finally:
        host.stores.close_all()


@pytest.fixture
def reviews_dir(tmp_path: Path) -> Path:
    """An empty directory to register as a watch. Under ``tmp_path``."""
    directory = tmp_path / "reviews"
    directory.mkdir()
    return directory


@pytest.fixture
def rig(local_host: LocalHost, reviews_dir: Path) -> DetectionRig:
    """A detection rig over ``local_host`` with an empty reviews directory."""
    return DetectionRig(local_host, reviews_dir)
