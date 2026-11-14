"""A provider repo and a consumer repo, both members of one program, for the flow test
(slice 227, D7): real git repositories, a replayed ``cf``, the real operations.

``since_from_block`` runs the consumer rule block's own git commands, so the test
exercises what an agent pasted into its rules file, not a copy of it.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from git_repo import git, head_of, make_repo
from operations.release_support import SettableClock, release_deps
from operations.status_support import FakeCf
from rule_blocks import real_rule_blocks
from store.seed import insert_member, insert_pair, insert_program

from amoeba.operations.changes import changes
from amoeba.operations.changes_models import ChangesResult
from amoeba.operations.deps import Deps
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportReleaseResult
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode

PROGRAM = "flow-program"
PROVIDER_ID = "flow-provider-id"
CONSUMER_ID = "flow-consumer-id"
SLICES_PATH = "project-documents/user/slices"
_GIT_SPAN = re.compile(r"`(git [^`]+)`")


def day(number: int, hour: int = 12) -> datetime:
    """A UTC time on a day of November 2026."""
    return datetime(2026, 11, number, hour, tzinfo=UTC)


@dataclass
class FlowRig:
    """The two repos, the store, the operations' ``Deps`` and the clock."""

    store: Store
    deps: Deps
    clock: SettableClock
    provider_repo: Path
    consumer_repo: Path


@contextmanager
def flow_rig(
    tmp_path: Path, consumed: ConsumedMode, *, extra_directories: tuple[Path, ...] = ()
) -> Generator[FlowRig]:
    """Both repos exist and are members; ``extra_directories`` are more checkouts of
    the consumer (``cf`` gives them the consumer's one project id)."""
    provider_repo = make_repo(tmp_path / "provider")
    consumer_repo = make_repo(tmp_path / "consumer")
    cf = FakeCf(
        {
            provider_repo: PROVIDER_ID,
            consumer_repo: CONSUMER_ID,
            **{directory: CONSUMER_ID for directory in extra_directories},
        }
    )
    clock = SettableClock(day(1))
    names = {PROVIDER_ID: "provider", CONSUMER_ID: "consumer"}
    deps = release_deps(tmp_path, clock, cf=cf, names=names)
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        _seed(store, consumed)
        yield FlowRig(store, deps, clock, provider_repo, consumer_repo)


def _seed(store: Store, consumed: ConsumedMode) -> None:
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id=PROGRAM,
            concept_member=None,
            concept_path=None,
            registered_at=day(1),
            updated_at=day(1),
        )
        for member in (PROVIDER_ID, CONSUMER_ID):
            insert_member(
                transaction,
                project_id=member,
                program_id=PROGRAM,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=day(1),
                updated_at=day(1),
            )
        insert_pair(
            transaction,
            program_id=PROGRAM,
            provider_id=PROVIDER_ID,
            consumer_id=CONSUMER_ID,
            consumed=consumed,
            registered_at=day(1),
            updated_at=day(1),
        )


def commit_design(
    repo: Path,
    name: str,
    *,
    author: str,
    committer: str | None = None,
) -> str:
    """Commit a slice design with separate author and committer dates (ISO 8601);
    the committer date defaults to the author date."""
    path = repo / SLICES_PATH / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"design {name}\n")
    git(repo, "add", "-f", "--", f"{SLICES_PATH}/{name}")
    dates = {
        "GIT_AUTHOR_DATE": author,
        "GIT_COMMITTER_DATE": committer or author,
    }
    git(repo, "commit", "-q", "-m", f"design {name}", env=dates)
    return head_of(repo)


def block_commands() -> list[str]:
    """The consumer block's git commands: its inline-code spans that start ``git``."""
    commands = _GIT_SPAN.findall(real_rule_blocks().consumer)
    assert len(commands) == 2, commands
    return commands


def since_from_block(repo: Path) -> str:
    """What an agent in ``repo`` gets from the block: the first command's stripped
    output, or the second's only when the first printed nothing. Empty when both
    printed nothing."""
    outputs = [
        subprocess.run(
            ["sh", "-c", command],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        for command in block_commands()
    ]
    return outputs[0] or outputs[1]


def report(
    rig: FlowRig, document: dict[str, object], *, at: datetime
) -> ReportReleaseResult:
    """``report_release`` from the provider repo with the clock at ``at``."""
    rig.clock.now = at
    return report_release(
        rig.store, document, directory=rig.provider_repo, deps=rig.deps
    )


def changes_for(rig: FlowRig, since: str, directory: Path) -> ChangesResult:
    return changes(rig.store, {"since": since}, directory=directory, deps=rig.deps)
