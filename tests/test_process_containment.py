"""Test processes are file-size capped and never outlive a killed session."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from process_containment import (
    MIN_ORPHAN_AGE_SECONDS,
    contained_popen,
    kill_children,
    leaked_pids,
    reap_orphans,
)

TESTS_DIR = Path(__file__).resolve().parent
ROOT = Path("/tmp/pytest-of-someone")
OLD = "3-06:14:04"
FRESH = "00:10"


def test_a_child_cannot_write_a_file_past_the_cap(tmp_path: Path) -> None:
    """Python ignores SIGXFSZ, so the kernel's answer is a failed write (EFBIG)."""
    target = tmp_path / "flood.log"
    child = contained_popen(
        [
            sys.executable,
            "-c",
            f"open({str(target)!r}, 'w').write('x' * 1_000_000)",
        ],
        file_size_limit_bytes=100_000,
        stderr=subprocess.PIPE,
        text=True,
    )

    _, stderr = child.communicate(timeout=30)

    assert child.returncode != 0
    assert "File too large" in stderr
    assert target.stat().st_size <= 100_000


def test_a_child_under_the_cap_is_unaffected(tmp_path: Path) -> None:
    target = tmp_path / "small.log"
    child = contained_popen(
        [sys.executable, "-c", f"open({str(target)!r}, 'w').write('x' * 1_000)"]
    )

    assert child.wait(timeout=30) == 0
    assert target.stat().st_size == 1_000


def test_children_still_alive_are_killed_on_demand() -> None:
    child = contained_popen([sys.executable, "-c", "import time; time.sleep(600)"])
    assert child.poll() is None

    kill_children()

    assert child.poll() is not None


def _line(pid: int, parent: int, elapsed: str, command: str) -> str:
    return f"{pid:>6} {parent:>6} {elapsed:>12} {command}"


def test_only_old_orphans_naming_the_pytest_root_are_leaked() -> None:
    listing = "\n".join(
        [
            _line(10, 1, OLD, f"python -m leaked_child --dir {ROOT}/p1"),
            _line(11, 1, FRESH, f"python -m leaked_child --dir {ROOT}/p2"),
            _line(12, 4242, OLD, f"python -m leaked_child --dir {ROOT}/p3"),
            _line(13, 1, OLD, "/usr/sbin/cfprefsd agent"),
            _line(14, 1, OLD, "python -m other_tool start --dir /srv/real"),
        ]
    )

    assert leaked_pids(listing, root=ROOT) == [10]


def test_the_age_threshold_is_five_minutes() -> None:
    assert MIN_ORPHAN_AGE_SECONDS == 300
    just_under = _line(20, 1, "04:59", f"python {ROOT}/a")
    just_over = _line(21, 1, "05:00", f"python {ROOT}/a")

    assert leaked_pids(just_under + "\n" + just_over, root=ROOT) == [21]


def test_reap_terminates_exactly_the_leaked_pids() -> None:
    killed: list[int] = []
    listing = _line(30, 1, OLD, f"python {ROOT}/p9")

    reaped = reap_orphans(lambda: listing, killed.append, root=ROOT)

    assert list(reaped) == killed == [30]


def _starts_a_process(node: ast.AST) -> bool:
    """A ``subprocess.Popen(...)`` call, or an import that would allow a bare one."""
    if isinstance(node, ast.ImportFrom):
        return node.module == "subprocess" and any(
            alias.name == "Popen" for alias in node.names
        )
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "Popen"
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
    )


def test_no_test_module_starts_a_process_except_through_the_containment() -> None:
    offenders: list[str] = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.name in {"process_containment.py", Path(__file__).name}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders += [
            f"{path.relative_to(TESTS_DIR)}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call | ast.ImportFrom) and _starts_a_process(node)
        ]

    assert offenders == [], f"use process_containment.contained_popen: {offenders}"


@pytest.mark.parametrize("elapsed", ["00:00", "59:59", "1-00:00:00"])
def test_elapsed_times_parse(elapsed: str) -> None:
    line = _line(40, 1, elapsed, f"python {ROOT}/a")
    expected = {"00:00": [], "59:59": [40], "1-00:00:00": [40]}[elapsed]

    assert leaked_pids(line, root=ROOT) == expected
