"""``amoeba resume-run ANSWER_SEQ CLAIM_ID``: internal, started by the after-step
(slice 262, D10). Registered beside ``wake-run``, CLI only: no operation, no tool."""

from __future__ import annotations

import argparse
from typing import Any

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.config.home import StateLayout
from amoeba.operations.resume_run import RESUME_RUN_COMMAND, run_resume
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.wiring import default_deps, load_config, open_store


def register_resume_run(commands: Any) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        RESUME_RUN_COMMAND,
        help="internal: resume one answered run (started by Amoeba, not for people)",
    )
    parser.set_defaults(cli_only=RESUME_RUN_COMMAND)
    parser.add_argument("answer_seq", type=int, help="the answer's number")
    parser.add_argument("claim_id", help="the resume claim's id, from claim_work")
    return parser


def run_resume_run(layout: StateLayout, answer_seq: int, claim_id: str) -> int:
    """Resume the answer and return the exit code for how it was recorded: 0 for
    ``resumed``, ``not_delivered`` and a claim that is no longer the answer's, 1 for
    ``refused``.

    Raises:
        SquadronError: The first poll could not be read and nothing was recorded, or
            ``sq`` could not be used.
        StoreError: The store cannot be used.
    """
    deps = default_deps(layout)
    with open_store(layout) as store:
        steps = LocalSteps(store, StepEdges(deps.clock, load_config))
        result = run_resume(steps, deps, answer_seq, claim_id)
    if result is None or result.outcome is not ResumeOutcome.REFUSED:
        return EXIT_OK
    return EXIT_REJECTED
