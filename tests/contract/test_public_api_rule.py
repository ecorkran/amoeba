"""The contract proof's import rule catches each violation, and passes the proof."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract.public_api import PUBLIC_ROOTS, ViolationKind, import_violations

CONTRACT_DIR = Path(__file__).parent


def _source(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "candidate.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_there_are_exactly_the_seven_public_roots() -> None:
    assert PUBLIC_ROOTS == {
        "amoeba.store",
        "amoeba.inbox",
        "amoeba.feed",
        "amoeba.process",
        "amoeba.upstream.squadron",
        "amoeba.upstream.context_forge",
        "amoeba.inspection",
    }


@pytest.mark.parametrize(
    ("source", "imported"),
    [
        ("from amoeba.store.paths import store_dir\n", "amoeba.store.paths.store_dir"),
        ("import amoeba.store.paths\n", "amoeba.store.paths"),
        ("from amoeba.store import paths\n", "amoeba.store.paths"),
    ],
)
def test_a_submodule_of_a_root_is_reported(
    tmp_path: Path, source: str, imported: str
) -> None:
    [violation] = import_violations(_source(tmp_path, source))

    assert violation.imported == imported
    assert violation.kind in {ViolationKind.SUBMODULE, ViolationKind.UNEXPORTED_NAME}


def test_a_name_the_root_does_not_export_is_reported(tmp_path: Path) -> None:
    source = "from amoeba.process import SquadronRun\n"

    [violation] = import_violations(_source(tmp_path, source))

    assert violation.kind is ViolationKind.UNEXPORTED_NAME
    assert violation.imported == "amoeba.process.SquadronRun"


@pytest.mark.parametrize(
    "source",
    [
        "from amoeba.cli.main import ExitCode\n",
        "import amoeba.cli.main\n",
        "import amoeba\n",
        "from amoeba import cli\n",
    ],
)
def test_a_module_outside_the_roots_is_reported(tmp_path: Path, source: str) -> None:
    [violation] = import_violations(_source(tmp_path, source))

    assert violation.kind is ViolationKind.OUTSIDE_ROOTS


def test_a_violation_carries_its_file_and_line(tmp_path: Path) -> None:
    path = _source(tmp_path, "import os\n\nfrom amoeba.cli.main import ExitCode\n")

    [violation] = import_violations(path)

    assert (violation.path, violation.line) == (path, 3)


@pytest.mark.parametrize(
    "source",
    [
        "import json\nimport pytest\nimport httpx\n",
        "from evidence_harness import PROJECT\n",
        "from amoeba.store import Store, store_dir\n",
        "import amoeba.store\n",
        "from amoeba.upstream import squadron\n",
        "from amoeba.upstream.squadron import parse_review_artifact\n",
        "from amoeba.process import standard_tenants\n",
        "from . import sibling\n",
    ],
)
def test_allowed_imports_are_not_reported(tmp_path: Path, source: str) -> None:
    assert import_violations(_source(tmp_path, source)) == []


def test_every_module_in_the_contract_directory_passes() -> None:
    offenders = [
        violation
        for path in sorted(CONTRACT_DIR.glob("*.py"))
        for violation in import_violations(path)
    ]

    assert offenders == []
