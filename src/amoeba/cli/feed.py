"""``amoeba feed``: print a project's changes as JSON lines.

Takes no lock and opens the store read-only, so it works with the resident
process running or stopped. Store failures go through the boundary mapping in
``main.py``.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Iterable, Iterator
from types import FrameType
from typing import TYPE_CHECKING, Any

from amoeba.feed import FeedSettings, follow
from amoeba.store import Change, Store, paths

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode


def add_feed_parser(subparsers: Any) -> None:
    """Add ``feed``. ``subparsers`` is typed ``Any`` for the reason in ``main.py``."""
    feed = subparsers.add_parser(
        "feed",
        help="Print a project's changes as JSON lines.",
        description=(
            "Prints one JSON object per change. Without --follow, prints what "
            "exists and exits. With --follow, waits for new changes until "
            "interrupted. Read-only; works with the process running or stopped."
        ),
    )
    feed.add_argument("--project", required=True, help="The project.")
    feed.add_argument(
        "--after",
        type=_non_negative,
        default=0,
        metavar="SEQ",
        help="Print only changes after this seq (default 0: all).",
    )
    feed.add_argument(
        "--follow", action="store_true", help="Keep printing new changes."
    )


def _non_negative(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {value}")
    return value


def change_line(change: Change) -> str:
    """One change as a JSON object, keys as in :class:`Change`."""
    return json.dumps(
        {
            "seq": change.seq,
            "project_id": change.project_id,
            "kind": change.kind.value,
            "node_id": change.node_id,
            "subject_id": change.subject_id,
            "payload": dict(change.payload),
            "recorded_at": change.recorded_at.isoformat(),
        }
    )


def _print_all(changes: Iterable[Change]) -> None:
    for change in changes:
        print(change_line(change), flush=True)


def _existing(project_id: str, after: int, settings: FeedSettings) -> Iterator[Change]:
    """Every change after ``after`` that exists now, streamed batch by batch."""
    path = paths.project_store_path(paths.store_dir(), project_id)
    cursor = after
    with Store.open_read_only(path) as store:
        while batch := store.changes(
            project_id, after=cursor, limit=settings.feed_batch_size
        ):
            yield from batch
            cursor = batch[-1].seq


def run_feed(args: argparse.Namespace) -> ExitCode:
    """Run ``amoeba feed``."""
    from amoeba.cli.main import ExitCode

    settings = FeedSettings()
    if not args.follow:
        _print_all(_existing(args.project, args.after, settings))
        return ExitCode.OK

    terminated = threading.Event()

    def on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        terminated.set()

    signal.signal(signal.SIGTERM, on_sigterm)
    try:
        _print_all(
            follow(
                paths.store_dir(),
                args.project,
                after=args.after,
                settings=settings,
                stop=terminated.is_set,
            )
        )
    except KeyboardInterrupt:
        # Specific: Ctrl-C is how a follower is meant to end; a clean stop.
        sys.stdout.flush()
    return ExitCode.OK
