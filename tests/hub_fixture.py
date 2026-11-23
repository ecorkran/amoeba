"""The two-machine fixture: a real hub process and two joined client homes (slice 260).

``amoeba hub serve`` runs as a subprocess on a hub home, on loopback and a free port,
with a ``PATH`` on which neither ``cf`` nor ``sq`` exists, so an accidental hub-side
call to either fails a test. Two machines are invited with the real CLI and joined from
two client homes with ``amoeba join``. The fixture can stop, kill (``SIGKILL``) and
restart the hub, and while it is stopped a test can seed its store with the store's own
functions, acting as the first invited machine (never as ``local``). Later slices reuse
it. It spends nothing, so it runs in the normal tier and in CI.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Final

import yaml
from hub.start_support import free_port
from hub_clients import (
    BIN_DIRECTORY,
    add_worktree,
    cf_calls,
    clone_repo,
    install_client_tools,
    set_runs,
)
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.config.home import StateLayout, layout_under
from amoeba.hub.store_open import open_hub_store
from amoeba.store.machines import hash_token, machine_for_token
from amoeba.store.store import Store
from amoeba.wire.join_line import parse_join_line

SERVING_MARKER: Final = "serving on"
START_TIMEOUT_SECONDS: Final = 30.0
STOP_TIMEOUT_SECONDS: Final = 30.0
COMMAND_TIMEOUT_SECONDS: Final = 120.0
#: The names of the two machines and the home each is joined from.
FIRST: Final = "alpha"
SECOND: Final = "beta"
#: Programs that are not on a client's ``PATH`` but its own stubs (``cf``, ``sq``).
FORBIDDEN_PROGRAMS: Final = ("cf", "sq")
#: Programs that are not on the fixture hub's ``PATH`` at all: the hub never runs any
#: of them (slice 261, D5).
HUB_FORBIDDEN_PROGRAMS: Final = ("cf", "sq", "git")


def amoeba_script() -> str:
    """The venv's ``amoeba`` console script."""
    return str(Path(sys.executable).parent / "amoeba")


def safe_path() -> str:
    """A ``PATH`` on which ``shutil.which`` finds neither ``cf`` nor ``sq``."""
    keep = [
        entry
        for entry in os.environ["PATH"].split(os.pathsep)
        if not any((Path(entry) / program).exists() for program in FORBIDDEN_PROGRAMS)
    ]
    path = os.pathsep.join([str(Path(sys.executable).parent), *keep])
    for program in FORBIDDEN_PROGRAMS:
        assert shutil.which(program, path=path) is None, f"{program} is on the PATH"
    return path


def hub_path() -> str:
    """The hub's ``PATH``: the venv's ``bin`` only, so ``cf``, ``sq`` and ``git`` are
    all missing there."""
    path = str(Path(sys.executable).parent)
    for program in HUB_FORBIDDEN_PROGRAMS:
        assert shutil.which(program, path=path) is None, f"{program} is on the hub PATH"
    return path


def hub_layout(home: Path) -> StateLayout:
    """The layout of a home where config and state are one directory (AMOEBA_HOME)."""
    return layout_under(home, home, None)


@dataclass
class Completed:
    """One CLI run: its exit code, stdout, stderr and the JSON stdout holds."""

    code: int
    out: str
    err: str

    @property
    def json(self) -> object:
        return json.loads(self.out)


@dataclass
class ClientHome:
    """A client machine's ``AMOEBA_HOME``, with its own stub ``cf`` and ``sq``."""

    name: str
    home: Path
    hub: FixtureHub = field(repr=False)

    def run(self, *args: str, timeout: float = COMMAND_TIMEOUT_SECONDS) -> Completed:
        return self.hub.run_in(self.home, *args, timeout=timeout)

    def run_in(
        self, directory: Path, *args: str, timeout: float = COMMAND_TIMEOUT_SECONDS
    ) -> Completed:
        """``amoeba <args>`` with ``directory`` as the working directory."""
        return self.hub.run_in(self.home, *args, timeout=timeout, cwd=directory)

    def clone(
        self,
        name: str,
        origin: str | None,
        project_id: str,
        project_name: str | None = None,
    ) -> Path:
        """A repo of this machine with ``origin`` and its Context Forge project id."""
        return clone_repo(self.home, name, origin, project_id, project_name)

    def worktree(self, repo: Path, name: str) -> Path:
        return add_worktree(self.home, repo, name)

    def set_runs(self, runs: list[dict[str, object]]) -> None:
        set_runs(self.home, runs)

    def cf_calls(self) -> list[str]:
        """What the stub ``cf`` of this machine has been asked so far."""
        return cf_calls(self.home)


class FixtureHub:
    """A hub process on a hub home, and the machines joined to it."""

    def __init__(
        self,
        root: Path,
        *,
        backup_hours: float = 24,
        backups_kept: int = 3,
        hub_log_max_bytes: int = 100_000,
        hub_logs_kept: int = 3,
    ) -> None:
        self.root = root
        self.home = root / "hub-home"
        self.backup_dir = root / "hub-backups"
        self.home.mkdir()
        self.backup_dir.mkdir()
        self.layout = hub_layout(self.home)
        self.port = free_port()
        self.settings: dict[str, object] = {
            "bind": "127.0.0.1",
            "port": self.port,
            "address": f"127.0.0.1:{self.port}",
            "backup_dir": str(self.backup_dir),
            "backup_hours": backup_hours,
            "backups_kept": backups_kept,
            "hub_log_max_bytes": hub_log_max_bytes,
            "hub_logs_kept": hub_logs_kept,
        }
        self.write_hub_yaml()
        (self.home / "config.yaml").write_text(example_config_text(), encoding="utf-8")
        self.process: subprocess.Popen[str] | None = None
        self.stderr_lines: list[str] = []
        self.stdout_lines: list[str] = []
        self.tokens: dict[str, str] = {}
        self.clients: dict[str, ClientHome] = {}
        #: Variables set last in a home's environment, replacing its stubs (the live
        #: tier gives a client the real ``cf`` and its own data directory).
        self.home_environment: dict[Path, dict[str, str]] = {}

    def write_hub_yaml(self) -> None:
        self.layout.hub_file.write_text(yaml.safe_dump(self.settings), encoding="utf-8")

    @property
    def address(self) -> str:
        return str(self.settings["address"])

    def env_for(self, home: Path) -> dict[str, str]:
        """The hub's environment for the hub home; a client's, with its own stub
        ``cf`` and ``sq`` first on the ``PATH``, for any other."""
        if home == self.home:
            path = hub_path()
        else:
            path = os.pathsep.join([str(home / BIN_DIRECTORY), safe_path()])
        base = {"AMOEBA_HOME": str(home), "PATH": path, "HOME": str(self.root)}
        return {**base, **self.home_environment.get(home, {})}

    def run_in(
        self,
        home: Path,
        *args: str,
        timeout: float = COMMAND_TIMEOUT_SECONDS,
        cwd: Path | None = None,
    ) -> Completed:
        child = contained_popen(
            [amoeba_script(), *args],
            cwd=cwd,
            env=self.env_for(home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = child.communicate(timeout=timeout)
        return Completed(child.returncode, out, err)

    # --- the hub process -------------------------------------------------------

    def start(self, *extra: str) -> None:
        """Start ``amoeba hub serve`` and wait for its serving line."""
        assert self.process is None, "the hub is already running"
        self.stderr_lines, self.stdout_lines = [], []
        child = contained_popen(
            [amoeba_script(), "hub", "serve", *extra],
            env=self.env_for(self.home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.process = child
        for stream, lines in (
            (child.stdout, self.stdout_lines),
            (child.stderr, self.stderr_lines),
        ):
            threading.Thread(target=_drain, args=(stream, lines), daemon=True).start()
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while not any(SERVING_MARKER in line for line in self.stderr_lines):
            if child.poll() is not None:
                time.sleep(0.2)
                self.process = None
                raise RuntimeError(
                    f"the hub exited with {child.returncode}: {self.stderr_lines}"
                )
            if time.monotonic() > deadline:
                self.kill()
                raise TimeoutError(f"the hub never served: {self.stderr_lines}")
            time.sleep(0.02)

    def start_expecting_failure(self, *extra: str) -> Completed:
        """Run ``hub serve`` for a start that must stop; returns how it ended."""
        return self.run_in(self.home, "hub", "serve", *extra)

    def stop(self) -> None:
        """SIGTERM, as ``docker stop`` sends it."""
        child = self.process
        if child is None:
            return
        child.send_signal(signal.SIGTERM)
        child.wait(timeout=STOP_TIMEOUT_SECONDS)
        self.process = None

    def kill(self) -> None:
        child = self.process
        if child is None:
            return
        child.kill()
        child.wait(timeout=STOP_TIMEOUT_SECONDS)
        self.process = None

    def restart(self, *extra: str) -> None:
        self.stop()
        self.start(*extra)

    def kill_and_restart(self) -> None:
        self.kill()
        self.start()

    def move_to_new_home(self, name: str) -> Path:
        """Point the fixture at a new, empty hub home (same port and settings), for a
        start that restores a backup into a new state directory. The hub must be
        stopped."""
        assert self.process is None, "stop the hub before it moves"
        self.home = self.root / name
        self.home.mkdir()
        self.layout = hub_layout(self.home)
        self.write_hub_yaml()
        (self.home / "config.yaml").write_text(example_config_text(), encoding="utf-8")
        return self.home

    # --- machines ---------------------------------------------------------------

    def invite(self, machine: str) -> str:
        """`amoeba hub invite` in the hub home; returns the join line."""
        done = self.run_in(self.home, "hub", "invite", machine, "-j")
        assert done.code == 0, done.err
        document: dict[str, object] = json.loads(done.out)
        line = str(document["join_line"])
        self.tokens[machine] = parse_join_line(line).token
        return line

    def join(self, machine: str, home_name: str | None = None) -> ClientHome:
        """Invite ``machine`` and join a fresh client home from it."""
        line = self.invite(machine)
        home = self.root / f"client-{home_name or machine}"
        home.mkdir()
        install_client_tools(home)
        client = ClientHome(home_name or machine, home, self)
        done = client.run("join", line, "-j")
        assert done.code == 0, done.err
        self.clients[client.name] = client
        return client

    @contextmanager
    def seeded_store(self, acting_as: str = FIRST) -> Generator[Store]:
        """The hub's store, opened while the hub is stopped, acting as an invited
        machine, never as ``local`` (D12, D18)."""
        assert self.process is None, "seed the store while the hub is stopped"
        with open_hub_store(self.layout) as store:
            with store.read() as transaction:
                machine = machine_for_token(
                    transaction, hash_token(self.tokens[acting_as])
                )
            assert machine is not None
            store.act_as(machine)
            yield store

    def seed(self, seeder: Callable[[Store], None], acting_as: str = FIRST) -> None:
        with self.seeded_store(acting_as) as store:
            seeder(store)

    def close(self) -> None:
        self.stop()


def _drain(stream: IO[str] | None, lines: list[str]) -> None:
    """Collect a child's output line by line, so its pipe never fills."""
    if stream is None:
        return
    for line in stream:
        lines.append(line.rstrip("\n"))


@contextmanager
def two_machine_hub(
    root: Path,
    *,
    backup_hours: float = 24,
    backups_kept: int = 3,
    hub_log_max_bytes: int = 100_000,
    hub_logs_kept: int = 3,
) -> Generator[FixtureHub]:
    """A hub serving, with ``alpha`` and ``beta`` joined from their own homes."""
    hub = FixtureHub(
        root,
        backup_hours=backup_hours,
        backups_kept=backups_kept,
        hub_log_max_bytes=hub_log_max_bytes,
        hub_logs_kept=hub_logs_kept,
    )
    try:
        hub.start()
        hub.join(FIRST)
        hub.join(SECOND)
        yield hub
    finally:
        hub.close()
