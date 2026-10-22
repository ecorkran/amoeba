"""Start, crash, stop, and restart the contract proof's resident process.

Everything here is real: signals, the instance lock, SQLite, the inbox
directory. Nothing is mocked. The harness fails loudly rather than hanging: every
wait is a predicate with a timeout, and a timeout reports the step number and the
captured stdout and stderr of every subprocess.

``host_harness.HostProcess`` supplies the process handle (signal, wait, kill).
Its blocking ``await_line`` is not used: a bootstrap that never prints would
block it past any timeout, so a reader thread feeds the predicates here instead.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from host_harness import HostProcess
from review_fixtures import STAMPED_REVIEW_106
from sq_stub import MODE_ENV, StubMode, write_sq_stub

from amoeba.inbox import submit
from amoeba.store import ChangeKind, Store, SubmissionKind, project_store_path
from contract.launched import LaunchedProcess
from contract.runner_tenant import INTENT_CRASH_AT, INTENT_STEP, CrashPoint, ProofStep
from contract.subscriber import BackgroundReader, Subscriber

TESTS_DIR = Path(__file__).resolve().parent.parent

WAIT_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.05
COMMAND_TIMEOUT_SECONDS = 30.0

#: Payload keys of the inbox submissions the harness writes, as the inbox
#: contract documents them.
PAYLOAD_BODY = "body"
PAYLOAD_REVIEWS_DIR = "reviews_dir"
PAYLOAD_ACTIVE = "active"

BOOTSTRAP_PREFIX = "bootstrap"

PM_ACTOR = "proof-pm"


class HarnessFailure(AssertionError):
    """A wait timed out or a subprocess misbehaved. The message names the step."""


def require_under(root: Path, path: Path, label: str) -> Path:
    """Refuse any path outside ``root``: the proof never touches a real directory."""
    if root.resolve() not in path.resolve().parents:
        raise ValueError(f"{label} {path} is not under {root}")
    return path


class ProofHarness:
    """The resident process, its directories, and the way tests wait on it."""

    def __init__(
        self,
        tmp_path: Path,
        project_ids: Sequence[str],
        *,
        review_fixture: Path = STAMPED_REVIEW_106,
    ) -> None:
        self.tmp_path = tmp_path
        self.review_fixture = review_fixture
        self.home = require_under(tmp_path, tmp_path / "home", "HOME")
        self.supervisor_dir = require_under(tmp_path, tmp_path / "store", "store")
        self.cf_data_dir = require_under(tmp_path, tmp_path / "cf", "CF data")
        self._logs = tmp_path / "logs"
        self.reviews_dirs: dict[str, Path] = {
            project_id: require_under(
                tmp_path, tmp_path / "reviews" / project_id, "reviews"
            )
            for project_id in project_ids
        }
        for directory in (
            self.home,
            self.cf_data_dir,
            self._logs,
            *self.reviews_dirs.values(),
        ):
            directory.mkdir(parents=True)
        self.stub_dir = write_sq_stub(tmp_path / "stub-bin")
        self._launched: list[LaunchedProcess] = []
        self._resident: LaunchedProcess | None = None
        self._subscribers: dict[str, Subscriber] = {}
        self._readers: list[BackgroundReader] = []

    # -- environment and processes ------------------------------------------

    def environment(self) -> dict[str, str]:
        """An explicit environment: nothing is inherited but ``PATH``.

        The stub ``sq`` is first on ``PATH``, so recovery and pruning poll the
        stub's outcome documents and never the real Squadron.
        """
        return {
            "PATH": f"{self.stub_dir}{os.pathsep}{os.environ['PATH']}",
            MODE_ENV: StubMode.DELETE.value,
            "HOME": str(self.home),
            "AMOEBA_STORE_DIR": str(self.supervisor_dir),
            "PYTHONPATH": str(TESTS_DIR),
            "PYTHONUNBUFFERED": "1",
        }

    @property
    def process(self) -> HostProcess:
        """The most recently started resident process."""
        assert self._resident is not None, "no resident process has been started"
        return self._resident.host

    def track(self, launched: LaunchedProcess) -> LaunchedProcess:
        """Register a subprocess: failures report its output; teardown kills it."""
        self._launched.append(launched)
        return launched

    def _count_of(self, prefix: str) -> int:
        return sum(
            1 for launched in self._launched if launched.label.startswith(prefix)
        )

    def next_label(self, prefix: str) -> str:
        """``prefix-N``, numbering each kind of subprocess separately."""
        return f"{prefix}-{self._count_of(prefix) + 1}"

    def stderr_path_for(self, label: str) -> Path:
        return self._logs / f"{label}.stderr.log"

    def start(self, step: int) -> None:
        """Launch the resident process and wait until it reports ready."""
        label = self.next_label(BOOTSTRAP_PREFIX)
        command = [
            sys.executable,
            "-m",
            "contract.bootstrap",
            "--supervisor-dir",
            str(self.supervisor_dir),
            "--cf-data-dir",
            str(self.cf_data_dir),
            "--review-fixture",
            str(self.review_fixture),
        ]
        for project_id, directory in self.reviews_dirs.items():
            command += ["--reviews-dir", f"{project_id}={directory}"]
        self._resident = self.track(
            LaunchedProcess(
                label,
                command,
                environment=self.environment(),
                working_dir=self.tmp_path,
                stderr_path=self.stderr_path_for(label),
            )
        )
        self.wait_until(step, "the process to report ready", self._ready_or_dead)

    def _ready_or_dead(self) -> bool:
        launched = self._resident
        assert launched is not None
        if launched.is_ready:
            return True
        if not launched.host.is_running():
            raise HarnessFailure(f"{launched.label} exited before it was ready")
        return False

    def wait_for_sigkill(self, step: int) -> None:
        """Wait for the process to die, and require that it died by SIGKILL."""
        self.wait_until(
            step, "the process to exit", lambda: not self.process.is_running()
        )
        if self.process.returncode != -signal.SIGKILL:
            raise HarnessFailure(
                f"step {step}: expected SIGKILL, got exit {self.process.returncode}"
                f"\n{self.captured_output()}"
            )

    def stop(self, step: int) -> None:
        """``amoeba stop``, then wait for a clean exit."""
        completed = subprocess.run(
            [sys.executable, "-m", "amoeba.cli.main", "stop"],
            env=self.environment(),
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0:
            raise HarnessFailure(
                f"step {step}: `amoeba stop` exited {completed.returncode}: "
                f"{completed.stderr}\n{self.captured_output()}"
            )
        self.wait_until(
            step, "the process to exit", lambda: not self.process.is_running()
        )
        if self.process.returncode != 0:
            raise HarnessFailure(
                f"step {step}: expected a clean exit, got {self.process.returncode}"
                f"\n{self.captured_output()}"
            )

    # -- waiting --------------------------------------------------------------

    def wait_until(
        self,
        step: int,
        description: str,
        predicate: Callable[[], bool],
        *,
        timeout: float = WAIT_TIMEOUT_SECONDS,
    ) -> None:
        """Poll ``predicate``; fail with the step and all captured output."""
        deadline = time.monotonic() + timeout
        while True:
            self._raise_subscriber_errors()
            try:
                if predicate():
                    return
            except HarnessFailure as failure:
                raise HarnessFailure(
                    f"step {step}: {failure}\n{self.captured_output()}"
                ) from failure
            if time.monotonic() >= deadline:
                raise HarnessFailure(
                    f"step {step}: timed out after {timeout}s waiting for "
                    f"{description}\n{self.captured_output()}"
                )
            time.sleep(POLL_INTERVAL_SECONDS)

    def captured_output(self) -> str:
        """Stdout and stderr of every subprocess started so far."""
        sections = [launched.captured() for launched in self._launched]
        return "\n".join(sections)

    # -- the feed ----------------------------------------------------------------

    def follow_project(self, step: int, project_id: str) -> Subscriber:
        """Start recording ``project_id``'s feed, once its store exists."""
        path = project_store_path(self.supervisor_dir, project_id)
        self.wait_until(step, f"the {project_id} store to exist", path.exists)
        return self.add_subscriber(Subscriber(self.supervisor_dir, project_id))

    def add_subscriber(self, subscriber: Subscriber) -> Subscriber:
        """Register a subscriber, so its failure surfaces at the next wait."""
        self._subscribers[subscriber.project_id] = subscriber
        self.add_reader(subscriber)
        return subscriber

    def add_reader(self, reader: BackgroundReader) -> None:
        """Watch a background reader: its failure is re-raised at the next wait."""
        self._readers.append(reader)

    def wait_for_changes(
        self,
        step: int,
        project_id: str,
        expected: Sequence[ChangeKind],
        *,
        since: int = 0,
    ) -> int:
        """Wait until changes after index ``since`` hold every expected kind.

        Returns the number of changes seen, the ``since`` for the next step.
        """
        subscriber = self._subscribers[project_id]
        wanted = Counter(expected)

        def seen() -> bool:
            kinds = Counter(change.kind for change in subscriber.changes[since:])
            return not wanted - kinds

        self.wait_until(step, f"{project_id} changes {sorted(wanted)}", seen)
        return len(subscriber.changes)

    def _raise_subscriber_errors(self) -> None:
        for reader in self._readers:
            if reader.error is not None:
                raise RuntimeError(f"the {reader.name} failed") from reader.error

    # -- submissions and reads -----------------------------------------------------

    def submit(
        self,
        project_id: str,
        kind: SubmissionKind,
        payload: Mapping[str, object],
        *,
        submitted_by: str = PM_ACTOR,
        submission_id: str | None = None,
    ) -> str:
        return submit(
            project_id=project_id,
            kind=kind,
            payload=payload,
            submitted_by=submitted_by,
            submission_id=submission_id,
            store_dir=self.supervisor_dir,
        )

    def create_project(self, project_id: str) -> str:
        return self.submit(project_id, SubmissionKind.CREATE_PROJECT, {})

    def watch_reviews(self, project_id: str) -> str:
        return self.submit(
            project_id,
            SubmissionKind.WATCH_REVIEWS,
            {
                PAYLOAD_REVIEWS_DIR: str(self.reviews_dirs[project_id]),
                PAYLOAD_ACTIVE: True,
            },
        )

    def intent(
        self, project_id: str, step: ProofStep, crash_at: CrashPoint | None = None
    ) -> str:
        body: dict[str, object] = {INTENT_STEP: step.value}
        if crash_at is not None:
            body[INTENT_CRASH_AT] = crash_at.value
        return self.submit(project_id, SubmissionKind.INTENT, {PAYLOAD_BODY: body})

    @contextmanager
    def read(self, project_id: str) -> Generator[Store]:
        """A read-only view of one project's store, the way a consumer opens it."""
        with Store.open_read_only(
            project_store_path(self.supervisor_dir, project_id)
        ) as store:
            yield store

    def close(self) -> None:
        # Processes first: a stream reader only ends once its server is gone.
        for launched in self._launched:
            launched.close()
        for reader in self._readers:
            reader.close()
