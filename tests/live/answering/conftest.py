"""Fixtures for the live answering tests (slice 140, Task 9).

``sq run`` refuses to start outside a Context Forge project, so every scratch
directory is a child of one throwaway registered directory: Context Forge finds
a parent registration, and the scratch directory itself stays free of anything
``cf init`` writes. Provider keys come from the environment of the test run.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator

import pytest
from live_settings import LiveSettings

from live.answering.harness import CF_TIMEOUT_SECONDS, LiveHarness


@pytest.fixture(scope="session")
def live_harness(
    live_settings: LiveSettings, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[LiveHarness]:
    parent = tmp_path_factory.mktemp("answering-live")
    data_dir = tmp_path_factory.mktemp("cf-data")
    environ = {**os.environ, "CONTEXT_FORGE_DATA_DIR": str(data_dir)}
    subprocess.run(
        ["cf", "init", "--lite", "--name", "amoeba-live"],
        cwd=parent,
        env=environ,
        capture_output=True,
        text=True,
        timeout=CF_TIMEOUT_SECONDS,
        check=True,
    )
    yield LiveHarness(parent=parent, environ=environ, settings=live_settings)
