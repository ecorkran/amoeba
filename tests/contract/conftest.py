"""Fixtures for the contract proof."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from contract.harness import ProofHarness
from contract.scenario import ALPHA, BETA


@pytest.fixture
def proof_harness(tmp_path: Path) -> Iterator[ProofHarness]:
    """A harness over throwaway directories, its processes killed on teardown.

    Safety: every directory it creates, and every path it hands a subprocess
    (``HOME`` included), lies under pytest's ``tmp_path``; ``require_under``
    refuses anything else before a process starts.
    """
    harness = ProofHarness(tmp_path, (ALPHA, BETA))
    try:
        yield harness
    finally:
        harness.close()
