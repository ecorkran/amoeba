"""``DirectoryReviewSource``: settling, the listing rule, and every race row."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest

from amoeba.process.review_sources import (
    DirectoryReviewSource,
    ReviewDirectoryUnavailableError,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sq_reviews"
ROUND_ONE = "102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md"
ROUND_TWO = "102-review.tasks.resident-process-and-recovery.part-1.md"


@pytest.fixture
def reviews(tmp_path: Path) -> Path:
    directory = tmp_path / "reviews"
    directory.mkdir()
    return directory


def _copy(name: str, directory: Path, as_name: str | None = None) -> Path:
    return Path(shutil.copy(FIXTURES / name, directory / (as_name or name)))


def _names(source: DirectoryReviewSource) -> list[str]:
    return [detected.path.name for detected in source.poll()]


# --------------------------------------------------------------------------
# Settling
# --------------------------------------------------------------------------


def test_a_first_sighting_is_remembered_not_returned(reviews: Path) -> None:
    _copy(ROUND_ONE, reviews)
    assert DirectoryReviewSource(reviews).poll() == []


def test_an_unchanged_second_poll_returns_the_exact_bytes(reviews: Path) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    [detected] = source.poll()
    assert detected.path == path
    assert detected.content == (FIXTURES / ROUND_ONE).read_bytes()


def test_a_size_change_resets_settling(reviews: Path) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    with path.open("ab") as handle:
        handle.write(b"\nmore")
    assert source.poll() == []
    assert len(source.poll()) == 1


def test_an_mtime_change_resets_settling(reviews: Path) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert source.poll() == []


# --------------------------------------------------------------------------
# The listing rule
# --------------------------------------------------------------------------


def test_only_regular_top_level_markdown_is_considered(reviews: Path) -> None:
    (reviews / "archive").mkdir()
    _copy(ROUND_ONE, reviews / "archive")
    (reviews / "notes.txt").write_text("not markdown")
    (reviews / "x.md").mkdir()
    _copy(ROUND_TWO, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    assert _names(source) == [ROUND_TWO]


# --------------------------------------------------------------------------
# Races
# --------------------------------------------------------------------------


def test_a_file_removed_between_polls_produces_nothing(reviews: Path) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    path.unlink()
    assert source.poll() == []


def test_a_read_that_finds_the_file_gone_drops_it_and_resettles(
    reviews: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    source.poll()
    real_read = Path.read_bytes

    def vanished(self: Path) -> bytes:
        if self == path:
            raise FileNotFoundError(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", vanished)
    assert source.poll() == []
    monkeypatch.setattr(Path, "read_bytes", real_read)
    assert source.poll() == []  # settles from scratch
    assert _names(source) == [ROUND_ONE]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads mode-000 files")
def test_an_unreadable_file_warns_once_then_is_returned_after_chmod(
    reviews: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = _copy(ROUND_ONE, reviews)
    path.chmod(0)
    source = DirectoryReviewSource(reviews)
    try:
        with caplog.at_level(logging.WARNING):
            for _ in range(4):
                assert source.poll() == []
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert path.name in warnings[0].getMessage()
    finally:
        path.chmod(0o644)
    assert _names(source) == [ROUND_ONE]


def test_a_removed_directory_raises_and_polling_resumes_when_restored(
    reviews: Path,
) -> None:
    source = DirectoryReviewSource(reviews)
    reviews.rmdir()
    with pytest.raises(ReviewDirectoryUnavailableError):
        source.poll()
    reviews.mkdir()
    _copy(ROUND_ONE, reviews)
    source.poll()
    assert _names(source) == [ROUND_ONE]


def test_a_settled_file_is_read_once_per_signature(
    reviews: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _copy(ROUND_ONE, reviews)
    source = DirectoryReviewSource(reviews)
    reads: list[Path] = []
    real_read = Path.read_bytes

    def counting(self: Path) -> bytes:
        reads.append(self)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    source.poll()
    assert _names(source) == [ROUND_ONE]
    for _ in range(5):
        assert source.poll() == []
    assert reads == [path]

    with path.open("ab") as handle:
        handle.write(b"\nedited")
    source.poll()
    assert _names(source) == [ROUND_ONE]
    assert DirectoryReviewSource(reviews).poll() == []  # a new source resettles
