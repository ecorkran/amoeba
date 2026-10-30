"""The stub ``sq``'s ``run --resume`` mode (slice 127, D4 and D6).

``sq run --resume <id> [--decision retry|accept] [--instructions T]``: resumes a paused
run. The stub keeps no more of Squadron than the Runner reads. A run that does not
exist exits 1; a run that is not paused exits 1; a bad flag or decision exits 2.
Otherwise it claims the run (its document goes to ``timed_out``, as a running run's
does), lasts ``RESUME_SECONDS_ENV``, and writes the final document: ``completed``, or
``paused`` again with a new ``checkpoint.paused_at``.

``RESUME_MODE_ENV`` forces a failure case; see :class:`ResumeMode`.
``RESUME_CLAIM_SECONDS_ENV`` is the delay before the claim, and
``RESUME_EXIT_CODE_ENV`` the code ``exit_before_claim`` exits with.
``RESUME_ARGV_LOG_ENV`` names a file the stub appends each resume's argv to as one
JSON list per line, so a test can read an instructions element byte for byte (the
main log joins arguments with spaces).

The code lives here, as text, so ``tests/sq_stub.py`` stays near 300 lines.
"""

from __future__ import annotations

import textwrap
from enum import StrEnum
from typing import Final

#: Environment variables the resume mode reads.
RESUME_MODE_ENV: Final = "SQ_STUB_RESUME_MODE"
RESUME_CLAIM_SECONDS_ENV: Final = "SQ_STUB_RESUME_CLAIM_SECONDS"
RESUME_SECONDS_ENV: Final = "SQ_STUB_RESUME_SECONDS"
RESUME_OUTCOME_ENV: Final = "SQ_STUB_RESUME_OUTCOME"
RESUME_EXIT_CODE_ENV: Final = "SQ_STUB_RESUME_EXIT_CODE"
RESUME_ARGV_LOG_ENV: Final = "SQ_STUB_RESUME_ARGV_LOG"

#: What a resume leaves its run as, when it claims it and finishes.
OUTCOME_COMPLETED: Final = "completed"
OUTCOME_PAUSED_AGAIN: Final = "paused"


class ResumeMode(StrEnum):
    """How ``run --resume`` misbehaves; absent means a normal resume."""

    #: Exit 2 and leave the run alone: accept at a non-loop, a held lock.
    REFUSE = "refuse"
    #: Exit ``RESUME_EXIT_CODE_ENV`` (default 1) without claiming the run.
    EXIT_BEFORE_CLAIM = "exit_before_claim"
    #: Exit 0 without ever touching the run: its state stays the old pause.
    NEVER_CLAIM = "never_claim"


_BRANCH = textwrap.dedent(
    """\
    if arguments[:2] == ["run", "--resume"]:
        from datetime import datetime, timezone

        argv_log = os.environ.get({argv_log_env!r})
        if argv_log:
            with open(argv_log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(sys.argv[1:]) + "\\n")
        resume_id = arguments[2] if len(arguments) > 2 else None
        options = dict()
        rest = iter(arguments[3:])
        for argument in rest:
            if argument in ("--decision", "--instructions"):
                options[argument] = next(rest, None)
            else:
                print("stub sq: unknown flag", argument, file=sys.stderr)
                sys.exit(2)
        # A plain --resume is Squadron's retry; a given --decision must be one it knows.
        if resume_id is None or options.get("--decision", "retry") not in (
            "retry",
            "accept",
        ):
            print("stub sq: need a run id and a known decision", file=sys.stderr)
            sys.exit(2)
        resume_mode = os.environ.get({mode_env!r})
        if resume_mode == {refuse!r}:
            print("stub sq: refused", file=sys.stderr)
            sys.exit(2)
        resume_file = state_dir / (resume_id + ".json")
        if not resume_file.exists():
            print("stub sq: no such run", resume_id, file=sys.stderr)
            sys.exit(1)
        document = json.loads(resume_file.read_text(encoding="utf-8"))
        if document.get("outcome") != "paused":
            print("stub sq: run is not paused", resume_id, file=sys.stderr)
            sys.exit(1)
        if resume_mode == {exit_before_claim!r}:
            sys.exit(int(os.environ.get({exit_code_env!r}, "1")))
        time.sleep(float(os.environ.get({claim_env!r}, "0")))
        if resume_mode == {never_claim!r}:
            sys.exit(0)
        running = dict(document, outcome="timed_out", status="timed_out")
        resume_file.write_text(json.dumps(running), encoding="utf-8")
        time.sleep(float(os.environ.get({seconds_env!r}, "0")))
        final = dict(document)
        if os.environ.get({outcome_env!r}, {completed!r}) == {paused_again!r}:
            checkpoint = dict(document.get("checkpoint") or dict())
            checkpoint["paused_at"] = datetime.now(timezone.utc).isoformat()
            final["checkpoint"] = checkpoint
        else:
            final.pop("checkpoint", None)
            final.update(outcome="completed", status="completed")
        resume_file.write_text(json.dumps(final), encoding="utf-8")
        sys.exit(0)
    """
)


def resume_branch() -> str:
    """The stub's resume code, ready to splice into its script at column zero."""
    return _BRANCH.format(
        argv_log_env=RESUME_ARGV_LOG_ENV,
        mode_env=RESUME_MODE_ENV,
        refuse=ResumeMode.REFUSE.value,
        exit_before_claim=ResumeMode.EXIT_BEFORE_CLAIM.value,
        never_claim=ResumeMode.NEVER_CLAIM.value,
        exit_code_env=RESUME_EXIT_CODE_ENV,
        claim_env=RESUME_CLAIM_SECONDS_ENV,
        seconds_env=RESUME_SECONDS_ENV,
        outcome_env=RESUME_OUTCOME_ENV,
        completed=OUTCOME_COMPLETED,
        paused_again=OUTCOME_PAUSED_AGAIN,
    )
