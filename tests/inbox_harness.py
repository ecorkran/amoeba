"""Envelope fixtures derived from real ``submit()`` output.

Per the parsing rules, a parser's fixtures must include the format it will
consume in production. So the base fixture is a file the real ``submit()``
wrote, and every damaged variant is derived from those bytes rather than
hand-written to look like them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from amoeba.inbox import layout, submit
from amoeba.store import SubmissionKind
from amoeba.store.inbox_models import INTENT_BODY

FIXTURE_PROJECT = "demo"
FIXTURE_SUBMISSION_ID = "fixture-1"

#: Names of the damaged variants, so tests refer to them by constant.
TRUNCATED = "truncated"
WRONG_VERSION = "wrong_version"
EXTRA_FIELDS = "extra_fields"


@dataclass(frozen=True)
class RealSubmission:
    """One file exactly as ``submit()`` wrote it."""

    supervisor_dir: Path
    path: Path
    content: bytes


def write_real_submission(
    supervisor_dir: Path, submission_id: str = FIXTURE_SUBMISSION_ID
) -> RealSubmission:
    """Submit one intent through the real ``submit()`` and return its file."""
    submit(
        project_id=FIXTURE_PROJECT,
        kind=SubmissionKind.INTENT,
        payload={INTENT_BODY: {"want": "fixture"}},
        submitted_by="fixture",
        submission_id=submission_id,
        store_dir=supervisor_dir,
    )
    suffix = f"-{submission_id}{layout.SUBMISSION_SUFFIX}"
    [path] = [
        candidate
        for candidate in layout.submission_files(layout.new_dir(supervisor_dir))
        if candidate.name.endswith(suffix)
    ]
    return RealSubmission(
        supervisor_dir=supervisor_dir, path=path, content=path.read_bytes()
    )


def damaged_variants(real: RealSubmission) -> dict[str, bytes]:
    """Hand-damaged copies of a real submission's bytes."""
    decoded = json.loads(real.content)
    return {
        TRUNCATED: real.content[: len(real.content) // 2],
        WRONG_VERSION: json.dumps(decoded | {"envelope_version": 99}).encode(),
        EXTRA_FIELDS: json.dumps(
            decoded
            | {"added_by_a_newer_submitter": True}
            | {"payload": decoded["payload"] | {"unknown_payload_key": 1}}
        ).encode(),
    }
