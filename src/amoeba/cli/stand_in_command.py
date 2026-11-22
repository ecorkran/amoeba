"""``amoeba stand-in``: the Claude Code ``Stop`` hook's command line.

Claude Code runs it at the end of every agent turn, with the hook's JSON on stdin. When
the closing message hands the PM something his rules settle, it prints a ``block``
decision whose reason is the stand-in's instruction, and the agent keeps working.
Otherwise it prints nothing and the turn ends. Every judgement is a line in
``<logs>/stand-in/<day>.jsonl``.

A failure (no model, a timeout, an unreadable reply) is one line on stderr and exit 1,
which Claude Code shows without stopping the session; the turn ends as it would have.
CLI-only: no ``OperationName``, no tool, no ``-j``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, cast

from amoeba.config.home import claude_home, logs_dir, state_layout, user_home
from amoeba.operations.answer_first import (
    ANSWER_FIRST_PREFIX,
    last_stop_block_reasons,
    recent_pm_requests,
)
from amoeba.operations.stand_in import (
    CHILD_ENV_VAR,
    PM_REQUESTS_SHOWN,
    REASON_PREFIX,
    Judgement,
    Verdict,
    VerdictError,
    build_prompt,
    hands_off,
    read_verdict,
)
from amoeba.store.errors import StoreError
from amoeba.store.standing import list_standing
from amoeba.wiring import open_store

logger = logging.getLogger(__name__)

STAND_IN_COMMAND: Final = "stand-in"

#: The model the stand-in asks, and the longest it waits for the reply. The hook's
#: own timeout in settings.json must be above this.
JUDGE_MODEL: Final = "sonnet"
JUDGE_TIMEOUT_SECONDS: Final = 90

#: Judgement log day files older than this are deleted at each write.
LOG_KEEP_DAYS: Final = 30
LOG_DIR_NAME: Final = "stand-in"

RULE_FILE_NAMES: Final = ("CLAUDE.md", "AGENTS.md")
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1


class StandInError(Exception):
    """The judgement could not be made; the turn ends as it would have."""


def register_stand_in(commands: Any) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        STAND_IN_COMMAND,
        help="internal: the end-of-turn hook that settles what agents hand the PM",
    )
    parser.set_defaults(cli_only=STAND_IN_COMMAND)
    return parser


def _text_blocks(entry: object) -> list[str]:
    """The text blocks of one transcript entry's message; none for any other shape."""
    if not isinstance(entry, dict):
        return []
    message = cast("dict[str, Any]", entry).get("message")
    content = (
        cast("dict[str, Any]", message).get("content")
        if isinstance(message, dict)
        else None
    )
    if not isinstance(content, list):
        return []
    texts: list[str] = []
    for block in cast("list[Any]", content):
        if isinstance(block, dict):
            typed = cast("dict[str, Any]", block)
            if typed.get("type") == "text" and isinstance(typed.get("text"), str):
                texts.append(typed["text"])
    return texts


def _last_message_from_transcript(transcript_path: str) -> str:
    """The text of the last assistant entry in a session transcript (JSONL)."""
    last = ""
    with Path(transcript_path).open(encoding="utf-8") as transcript:
        for line in transcript:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # a partly written last line; earlier entries still count
            if not isinstance(entry, dict):
                continue
            if cast("dict[str, Any]", entry).get("type") != "assistant":
                continue
            texts = _text_blocks(cast("object", entry))
            if any(texts):
                last = "\n".join(texts)
    return last


def closing_message(hook_input: dict[str, Any]) -> str:
    """The agent's closing message, from the hook's field or its transcript."""
    direct = hook_input.get("last_assistant_message")
    if isinstance(direct, str) and direct.strip():
        return direct
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str):
        raise StandInError("the hook gave no closing message and no transcript path")
    return _last_message_from_transcript(transcript_path)


def _read_if_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def gather_rules(cwd: Path) -> str:
    """The global CLAUDE.md, then every rules file from ``cwd`` up to the home."""
    home = user_home()
    parts: list[str] = []
    global_rules = _read_if_file(claude_home() / "CLAUDE.md")
    if global_rules:
        parts.append(f"--- {claude_home() / 'CLAUDE.md'} ---\n{global_rules}")
    for directory in (cwd, *cwd.parents):
        for name in RULE_FILE_NAMES:
            text = _read_if_file(directory / name)
            if text:
                parts.append(f"--- {directory / name} ---\n{text}")
        if directory == home:
            break
    return "\n\n".join(parts)


def gather_memory(cwd: Path) -> str:
    """The session's auto-memory files for this working directory."""
    slug = str(cwd).replace("/", "-")
    memory_dir = claude_home() / "projects" / slug / "memory"
    if not memory_dir.is_dir():
        return ""
    files = sorted(memory_dir.glob("*.md"), key=lambda path: path.name != "MEMORY.md")
    return "\n\n".join(
        f"--- {path.name} ---\n{path.read_text('utf-8')}" for path in files
    )


def gather_standing() -> str:
    """The PM's active standing answers, or a line saying why none could be read."""
    try:
        with open_store(state_layout()) as store, store.read() as transaction:
            rows = list_standing(transaction, include_withdrawn=False)
    except StoreError as error:
        logger.exception("stand-in could not read standing answers")
        return f"(the store could not be read: {error})"
    return "\n".join(f"- [{row.reach.value}] {row.text}" for row in rows)


def ask_model(prompt: str) -> Judgement:
    """One tool-less model call in an empty directory; its verdict.

    Raises:
        StandInError: The call failed, timed out, or gave no readable verdict.
    """
    environment = {**os.environ, CHILD_ENV_VAR: "1"}
    argv = [
        "claude",
        "-p",
        "--model",
        JUDGE_MODEL,
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "text",
    ]
    with tempfile.TemporaryDirectory() as empty:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, prompt on stdin
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=empty,
                env=environment,
                timeout=JUDGE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise StandInError(f"the model call failed: {error}") from error
    if completed.returncode != 0:
        raise StandInError(
            f"the model call exited {completed.returncode}: {completed.stderr[-500:]}"
        )
    try:
        return read_verdict(completed.stdout)
    except VerdictError as error:
        raise StandInError(str(error)) from error


def write_log(record: dict[str, Any]) -> None:
    """Append one judgement line, and delete day files past the keep time."""
    directory = logs_dir() / LOG_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    with (directory / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"at": now.isoformat(), **record}) + "\n")
    cutoff = f"{now - timedelta(days=LOG_KEEP_DAYS):%Y-%m-%d}.jsonl"
    for old in directory.glob("*.jsonl"):
        if old.name < cutoff:
            old.unlink(missing_ok=True)


def _transcript_newest_first(hook_input: dict[str, Any]) -> list[str]:
    """The session transcript's lines, newest first; none when the hook names none."""
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str):
        return []
    lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    lines.reverse()
    return lines


def _kept_going_by_answer_first_alone(newest_first: list[str]) -> bool:
    """Whether the turn was last kept going only so the PM could see a reply.

    The answer-first hook keeps a turn going once after each PM message. That is not a
    stand-in decision, so the end of the work that follows is still judged.
    """
    reasons = last_stop_block_reasons(newest_first)
    return bool(reasons) and all(
        reason.startswith(ANSWER_FIRST_PREFIX) and REASON_PREFIX not in reason
        for reason in reasons
    )


def judge(hook_input: dict[str, Any]) -> Judgement | None:
    """The judgement for one turn's end, or ``None`` when there is nothing to judge."""
    newest_first = _transcript_newest_first(hook_input)
    if hook_input.get("stop_hook_active") and not _kept_going_by_answer_first_alone(
        newest_first
    ):
        return None  # one stand-in decision per stop: the agent's next end goes through
    message = closing_message(hook_input)
    if not hands_off(message):
        return None
    requests = recent_pm_requests(newest_first, PM_REQUESTS_SHOWN)
    if not requests:
        return None  # the PM asked this session for nothing: nothing of his to settle
    cwd = Path(str(hook_input.get("cwd") or Path.cwd()))
    prompt = build_prompt(
        requests=requests,
        message=message,
        rules=gather_rules(cwd),
        memory=gather_memory(cwd),
        standing=gather_standing(),
        cwd=str(cwd),
    )
    judgement = ask_model(prompt)
    write_log(
        {
            "cwd": str(cwd),
            "session": hook_input.get("session_id"),
            "verdict": judgement.verdict.value,
            "text": judgement.text,
            "request": requests[-1][:2000],
            "message": message[:2000],
        }
    )
    return judgement


def run_stand_in() -> int:
    """Read the hook's input, judge, print the decision; the process exit code."""
    if os.environ.get(CHILD_ENV_VAR):
        return EXIT_OK  # the judge's own session ending: never judged
    try:
        hook_input = json.loads(sys.stdin.read())
        judgement = judge(hook_input)
    except (StandInError, OSError, json.JSONDecodeError) as error:
        # The process boundary: report once, and let the turn end as it would have.
        sys.stderr.write(f"amoeba stand-in: {error}\n")
        return EXIT_FAILED
    if judgement is not None and judgement.verdict is Verdict.SETTLED:
        decision = {"decision": "block", "reason": REASON_PREFIX + judgement.text}
        sys.stdout.write(json.dumps(decision))
    return EXIT_OK
