"""``amoeba ingest review``: read a Squadron review and submit it as a verdict.

Reads and parses the file with :mod:`amoeba.upstream.squadron`, then submits one
``verdict`` through the inbox exactly as ``amoeba submit verdict`` would. It opens
no store (D6): it checks that the project's store file exists, and prints the
submission id without waiting for the resident process to apply it.

``--node`` is the operator's explicit attribution. It is not checked against the
review's ``slice`` (D7); both are printed on stderr so a wrong node is visible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amoeba.store import paths
from amoeba.store.evidence_models import VerdictInput
from amoeba.upstream.squadron import (
    SquadronReviewError,
    parse_review_artifact,
    parse_review_json,
    to_verdict_input,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: Shown in place of a slice name when the review carries none (a PR review).
NO_SLICE = "-"


def add_ingest_parser(subparsers: Any) -> None:
    """Add ``ingest`` and its ``review`` source.

    ``subparsers`` is typed ``Any`` for the same reason as in ``main.py``.
    """
    ingest = subparsers.add_parser(
        "ingest",
        help="Read output from an upstream tool and submit it.",
        description="Parses a file and submits it through the inbox.",
    )
    sources = ingest.add_subparsers(dest="ingest_source", required=True)
    review = sources.add_parser(
        "review",
        help="Submit a Squadron review as a verdict.",
        description=(
            "Reads a Squadron review file or a captured `sq review --output json` "
            "stdout, and submits one verdict. Prints the submission id. Does not "
            "wait for it to be applied; see `inspect submissions` and `inspect inbox`."
        ),
    )
    review.add_argument("--project", required=True, help="The project.")
    review.add_argument("--node", required=True, help="The node the review is for.")
    review.add_argument("--by", required=True, help="Who is submitting. Free-form.")
    source = review.add_mutually_exclusive_group(required=True)
    source.add_argument("--artifact", metavar="PATH", help="A saved review file.")
    source.add_argument(
        "--stdout-json", metavar="PATH", help="Captured `--output json` stdout."
    )
    review.add_argument(
        "--upstream-version",
        metavar="LABEL",
        help="Squadron's version, for a review that carries no stamp.",
    )
    review.add_argument(
        "--id",
        dest="record_id",
        metavar="ID",
        help="Record and submission id. Defaults to a digest of the parsed review.",
    )


def _fail(message: str) -> None:
    print(f"amoeba: {message}", file=sys.stderr)


def _compose(args: argparse.Namespace, path: Path) -> VerdictInput:
    """Read, parse, and compose; then report what is being attributed where.

    Raises ``OSError``, ``UnicodeDecodeError``, or ``SquadronReviewError``; the
    caller maps each to an exit status.
    """
    text = path.read_text(encoding="utf-8")
    parsed = parse_review_artifact(text) if args.artifact else parse_review_json(text)
    verdict = to_verdict_input(
        parsed,
        node_id=args.node,
        record_id=args.record_id,
        upstream_version=args.upstream_version,
        source_path=str(path),
    )
    print(
        f"ingest: node {args.node}, slice {parsed.slice or NO_SLICE}, "
        f"review type {parsed.review_type}",
        file=sys.stderr,
    )
    return verdict


def run_ingest(args: argparse.Namespace) -> ExitCode:
    """Ingest one review.

    Raises:
        InboxSubmitError: If the inbox refuses the submission. Mapped to an exit
            code by the boundary handler.
    """
    from amoeba.cli.main import ExitCode

    if not paths.store_path(args.project).is_file():
        _fail(f"no store for project {args.project!r}")
        return ExitCode.SUBMISSION_REFUSED
    path = Path(args.artifact or args.stdout_json).resolve()
    try:
        verdict = _compose(args, path)
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"cannot read {path}: {error}")
        return ExitCode.REVIEW_UNREADABLE
    except SquadronReviewError as error:
        _fail(f"{path}: {error}")
        return ExitCode.REVIEW_UNREADABLE
    # TODO(8.4): submit the verdict.
    _fail("ingest: submit step not yet implemented")
    del verdict
    return ExitCode.SUBMISSION_REFUSED
