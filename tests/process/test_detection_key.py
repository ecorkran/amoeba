"""``detection_key``: the one place detection's ledger key is formed (slice 125, D7)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from amoeba.process import detection_key
from amoeba.process.review_scan import content_digest, examine
from amoeba.store import ReviewWatch, Store
from amoeba.store.review_sources import DetectedFile

PROJECT = "demo"
NOW = datetime(2026, 10, 24, tzinfo=UTC)
CONTENT = b"not a review, but bytes are bytes\n"


def _watch(reviews_dir: str) -> ReviewWatch:
    return ReviewWatch(
        project_id=PROJECT,
        reviews_dir=reviews_dir,
        active=True,
        registered_at=NOW,
        baselined_at=NOW,
        updated_at=NOW,
    )


def test_a_file_in_a_watched_directory_gets_the_joined_path_and_the_digest(
    tmp_path: Path,
) -> None:
    reviews = tmp_path / "reviews"
    other = tmp_path / "elsewhere"
    file = reviews / "125-review.tasks.foo.md"

    key = detection_key([_watch(str(other)), _watch(str(reviews))], file, CONTENT)

    assert key == (str(file), content_digest(CONTENT))


def test_a_file_outside_every_watch_has_no_key(tmp_path: Path) -> None:
    watches = [_watch(str(tmp_path / "reviews"))]

    assert detection_key(watches, tmp_path / "other" / "a.md", CONTENT) is None
    assert detection_key([], tmp_path / "reviews" / "a.md", CONTENT) is None


def test_a_subdirectory_of_a_watch_is_not_covered(tmp_path: Path) -> None:
    """Detection lists the top level only, so a nested file never reaches it."""
    watches = [_watch(str(tmp_path / "reviews"))]

    assert (
        detection_key(watches, tmp_path / "reviews" / "archive" / "a.md", CONTENT)
        is None
    )


def test_a_watch_given_with_a_trailing_separator_still_matches(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    file = reviews / "a.md"

    key = detection_key([_watch(f"{reviews}/")], file, CONTENT)

    assert key == (str(file), content_digest(CONTENT))


def test_detection_files_a_row_under_the_key_detection_key_names(
    tmp_path: Path,
) -> None:
    """Agreement: what ``examine`` records is found by ``detection_key``."""
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    file = reviews / "a.md"
    watches = [_watch(f"{reviews}/")]

    with Store.open_temporary() as store:
        examine(store, PROJECT, DetectedFile(file, CONTENT, NOW), "label")
        key = detection_key(watches, file, CONTENT)

        assert key is not None
        assert store.detection(PROJECT, *key) is not None
