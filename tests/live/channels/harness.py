"""A real interactive Claude Code session in a pseudo-terminal (slice 241, D10).

The session runs ``claude --dangerously-load-development-channels server:<name>`` in
a fixture directory, in its own process group so the whole tree can be killed. Its
output goes to a ``ScreenLog``; tests wait for text and send keystrokes. Start-up
screens are answered by their text, never by their position.

Claude Code's login lives in the operator's own config (a throwaway config directory
has none), so the session uses it, with ``--setting-sources project,local`` so the
operator's user settings (hooks, permission mode) do not apply and the project-server
consent screen is shown as an operator sees it. The server is registered in the
fixture directory or a file under it, never in the operator's config. The
auto-updater is off, so a test run never updates the installed Claude Code.
"""

from __future__ import annotations

import fcntl
import os
import pty
import signal
import struct
import subprocess
import termios
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from live_environment import process_environment
from process_containment import contained_popen

from live.channels.registration import SessionSpec, register
from live.channels.screen import ScreenLog, normalized

#: How long each start-up screen, and the ready prompt after the last, may take.
STARTUP_SCREEN_WAIT_SECONDS: Final = 60
#: How long an event may take to become an ``inbox`` call: a poll plus a model turn.
INBOX_CALL_WAIT_SECONDS: Final = 120
#: Added to a heartbeat or stale interval when waiting for its effect to show.
STALE_MARGIN_SECONDS: Final = 5
#: How long a prompted tool call may take: one model turn.
PROMPTED_CALL_WAIT_SECONDS: Final = 120
#: How long a menu takes to redraw after a key.
MENU_REDRAW_SECONDS: Final = 0.5
#: How many arrow presses a menu choice may take before it fails.
MENU_MAX_MOVES: Final = 6
#: How long a clean ``/exit`` may take before the process group is killed.
EXIT_WAIT_SECONDS: Final = 30
#: How often a wait looks at the screen again.
POLL_SECONDS: Final = 0.2
#: The pseudo-terminal's size: wide enough that menu lines do not wrap.
TERMINAL_ROWS: Final = 50
TERMINAL_COLUMNS: Final = 160
READ_CHUNK_BYTES: Final = 65536

KEY_DOWN: Final = "\x1b[B"
KEY_ENTER: Final = "\r"
#: Marks the highlighted line of a menu.
MENU_POINTER: Final = "❯"
#: Every confirmation screen's footer.
CONFIRM_FOOTER: Final = "Enter to confirm"
#: The input box's footer, shown once the session takes prompts.
READY_TEXT: Final = "shift+tab to cycle"
CHANNEL_FLAG: Final = "--dangerously-load-development-channels"
EXIT_COMMAND: Final = "/exit"
#: The variables the session gets beyond the named process variables.
SESSION_TERM: Final = "xterm-256color"
AUTOUPDATER_OFF: Final = {"DISABLE_AUTOUPDATER": "1"}


class SessionError(AssertionError):
    """A wait failed; the message names what was awaited and the last screen."""


@dataclass(frozen=True)
class StartupScreen:
    """A known start-up screen: the text that identifies it and the option chosen."""

    marker: str
    choice: str


#: Read from Claude Code 2.1.318 and 2.1.325 (20261116), in the order they appear.
KNOWN_SCREENS: Final = (
    StartupScreen("Quick safety check", "Yes, I trust this folder"),
    StartupScreen("New MCP server found in this project", "Use this MCP server"),
    StartupScreen(
        "WARNING: Loading development channels",
        "I am using this for local development",
    ),
)


class ClaudeSession:
    """One interactive session; ``start`` it, then wait, send and terminate."""

    def __init__(self, spec: SessionSpec) -> None:
        self.spec = spec
        self.screen = ScreenLog()
        self._process: subprocess.Popen[bytes] | None = None
        self._master: int | None = None
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        """Launch the session and answer the start-up screens until it is ready."""
        extra_args, variables = register(self.spec)
        name = self.spec.registration.name
        channel_args = [CHANNEL_FLAG, f"server:{name}"] if self.spec.as_channel else []
        command = [
            "claude",
            *channel_args,
            "--model",
            self.spec.model,
            "--setting-sources",
            "project,local",
            "--allowedTools",
            *self.spec.allowed_tools,
            *extra_args,
        ]
        environment = process_environment(
            self.spec.environ,
            TERM=SESSION_TERM,
            **AUTOUPDATER_OFF,
            **variables,
            **self.spec.extra_environment,
        )
        master, slave = pty.openpty()
        size = struct.pack("HHHH", TERMINAL_ROWS, TERMINAL_COLUMNS, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, size)
        self._process = contained_popen(
            command,
            cwd=self.spec.cwd,
            env=environment,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave)
        self._master = master
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._answer_startup_screens()

    def _read(self) -> None:
        assert self._master is not None
        while True:
            try:
                data = os.read(self._master, READ_CHUNK_BYTES)
            except OSError:
                # EIO: the session closed its terminal, which ends the output.
                return
            if not data:
                return
            self.screen.append(data.decode("utf-8", "replace"))

    def _answer_startup_screens(self) -> None:
        position = 0
        deadline = time.monotonic() + STARTUP_SCREEN_WAIT_SECONDS
        while True:
            text = self.screen.text_since(position)
            screen = next((s for s in KNOWN_SCREENS if s.marker in text), None)
            if screen is not None:
                position = self.screen.mark()
                self.choose(screen.choice)
                deadline = time.monotonic() + STARTUP_SCREEN_WAIT_SECONDS
            elif READY_TEXT in text:
                return
            elif CONFIRM_FOOTER in text:
                self._fail("a known start-up screen (this one is unknown)")
            elif time.monotonic() > deadline:
                self._fail("the next start-up screen or the ready prompt")
            self._check_running("the start-up screens")
            time.sleep(POLL_SECONDS)

    def choose(self, option: str) -> None:
        """Move the menu pointer to ``option`` by its text, then confirm."""
        wanted = normalized(f"{MENU_POINTER} {option}")
        for _ in range(MENU_MAX_MOVES + 1):
            time.sleep(MENU_REDRAW_SECONDS)
            text = self.screen.text_since(0)
            if text.rfind(wanted) >= 0 and text.rfind(wanted) == text.rfind(
                MENU_POINTER
            ):
                self.send(KEY_ENTER)
                return
            self.send(KEY_DOWN)
        self._fail(f"the menu pointer on {option!r}")

    def send(self, keys: str) -> None:
        assert self._master is not None
        os.write(self._master, keys.encode("utf-8"))

    def type_prompt(self, prompt: str) -> None:
        """Type ``prompt`` and submit it."""
        self.send(prompt)
        time.sleep(MENU_REDRAW_SECONDS)
        self.send(KEY_ENTER)

    def wait_for(self, text: str, timeout: float, *, since: int = 0) -> None:
        """Wait until ``text`` is printed after position ``since``."""
        wanted = normalized(text)
        deadline = time.monotonic() + timeout
        while wanted not in self.screen.text_since(since):
            if time.monotonic() > deadline:
                self._fail(f"{text!r} on the screen within {timeout}s")
            self._check_running(f"{text!r} on the screen")
            time.sleep(POLL_SECONDS)

    def terminate(self) -> int:
        """End the session with ``/exit``; kill the group if it does not leave."""
        process = self._running()
        if process.poll() is None:
            self.type_prompt(EXIT_COMMAND)
            try:
                process.wait(timeout=EXIT_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.kill()
        self._close()
        return process.returncode

    def kill(self) -> None:
        """SIGKILL the whole process group, the session and its servers."""
        process = self._running()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            # The group is already gone, which is what killing it wanted.
            pass
        process.wait(timeout=EXIT_WAIT_SECONDS)
        self._close()

    def kill_server(self, pid_file: Path) -> None:
        """SIGKILL the server whose launcher wrote its pid to ``pid_file``."""
        os.kill(int(pid_file.read_text(encoding="utf-8").strip()), signal.SIGKILL)

    def last_screen(self) -> str:
        return self.screen.last_screen()

    def _running(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise SessionError("the session was never started")
        return self._process

    def _check_running(self, what: str) -> None:
        if self._running().poll() is not None:
            self._fail(f"{what} (the session exited)")

    def _fail(self, what: str) -> None:
        raise SessionError(f"waited for {what}; last screen:\n{self.last_screen()}")

    def _close(self) -> None:
        if self._master is not None:
            os.close(self._master)
            self._master = None
