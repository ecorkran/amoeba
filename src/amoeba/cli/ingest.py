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

from amoeba.inbox import submit
from amoeba.store import SubmissionKind, paths
from amoeba.store.evidence_models import VerdictInput
from amoeba.store.verdict_payload import verdict_to_payload
from amoeba.upstream.squadron import (
    ParsedReview,
    SquadronReviewError,
    parse_review_artifact,
    parse_review_json,
    review_record_id,
    to_verdict_input,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from amoeba.cli.main import ExitCode

#: Shown in place of a slice name when the review carries none (a PR review).
NO_SLICE = "-"

#: The id does not include the node (D5), so this cannot be detected without
#: opening the store (D6); say it every time instead of staying silent.
NODE_NOT_IN_ID_NOTE = (
    "ingest: note: the id does not include the node; a review already ingested "
    "onto another node is not recorded again unless a new --id is given"
)


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
        "--judge-invocation-id",
        metavar="ID",
        help=(
            "Mark the review as one judge sample of this invocation. Without "
            "--id the record id is the digest followed by '.' and this id."
        ),
    )
    review.add_argument(
        "--id",
        dest="record_id",
        metavar="ID",
        help=(
            "Record and submission id. Defaults to a digest of the parsed review, "
            "which does not include the node: ingesting the same review onto "
            "another node is a no-op unless a new --id is given."
        ),
    )


def _sample_record_id(args: argparse.Namespace, parsed: ParsedReview) -> str | None:
    """The record id for this ingest, or ``None`` to take 105's default digest.

    An explicit ``--id`` is used as given. A judge sample's default id is the
    digest followed by ``.`` and its invocation id, so the same file under one
    invocation is a no-op replay and under a second invocation is a new sample.
    """
    if args.record_id is not None or args.judge_invocation_id is None:
        return args.record_id
    return f"{review_record_id(parsed)}.{args.judge_invocation_id}"


def _fail(message: str) -> None:
    print(f"amoeba: {message}", file=sys.stderr)


def _compose(args: argparse.Namespace, path: Path) -> tuple[ParsedReview, VerdictInput]:
    """Read, parse, and compose.

    Raises ``OSError``, ``UnicodeDecodeError``, or ``SquadronReviewError``; the
    caller maps each to an exit status.
    """
    text = path.read_text(encoding="utf-8")
    parsed = (
        parse_review_artifact(text)
        if args.artifact is not None
        else parse_review_json(text)
    )
    verdict = to_verdict_input(
        parsed,
        node_id=args.node,
        record_id=_sample_record_id(args, parsed),
        upstream_version=args.upstream_version,
        source_path=str(path),
        judge_invocation_id=args.judge_invocation_id,
    )
    return parsed, verdict


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
    source = args.artifact if args.artifact is not None else args.stdout_json
    path = Path(source).resolve()
    try:
        parsed, verdict = _compose(args, path)
    except (OSError, UnicodeDecodeError) as error:
        _fail(f"cannot read {path}: {error}")
        return ExitCode.REVIEW_UNREADABLE
    except SquadronReviewError as error:
        _fail(f"{path}: {error}")
        return ExitCode.REVIEW_UNREADABLE
    # Informational only (D7): shown just before the submission is made.
    print(
        f"ingest: node {args.node}, slice {parsed.slice or NO_SLICE}, "
        f"review type {parsed.review_type}, id {verdict.id}",
        file=sys.stderr,
    )
    print(NODE_NOT_IN_ID_NOTE, file=sys.stderr)
    # The digest (or --id) is both the record id and the submission id, so a
    # second ingest of the same review is a no-op replay (103's D2), even onto a
    # different node: the id does not include the node.
    print(
        submit(
            project_id=args.project,
            kind=SubmissionKind.VERDICT,
            payload=verdict_to_payload(verdict),
            submitted_by=args.by,
            submission_id=verdict.id,
        )
    )
    return ExitCode.OK
