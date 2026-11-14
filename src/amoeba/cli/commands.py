"""One runner per ``amoeba`` command (slices 222 to 229): build the request, call the
operation through ``wiring.invoke``, print the result.

The runners are the process boundary's body: they read request text, hand each
operation its document and turn its result into output and an exit code. Errors the
operations raise are reported by ``cli.main``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.cli.registration_arguments import add_document, list_document, rm_document
from amoeba.cli.render.dispatch import render_result
from amoeba.cli.render.simple import render_handle_pause
from amoeba.config.home import StateLayout
from amoeba.operations.calls_log import append_call, error_entry, result_entry
from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.names import Door, OperationName
from amoeba.operations.report_release_models import ReportMode
from amoeba.operations.set_up_models import SetUpOutcome, SetUpResult
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import project_names
from amoeba.wiring import (
    OperationResult,
    default_deps,
    invoke,
    is_rejected,
    load_config,
    open_store,
    result_document,
)

STDIN_SOURCE: Final = "-"
STDIN_NAME: Final = "<stdin>"
JSON_INDENT: Final = 2


class RequestDocumentError(Exception):
    """The request cannot be read, is not UTF-8, or is not YAML; names the source."""


def read_request_document(source: str) -> object:
    """The parsed YAML of the file at ``source``, or of stdin when it is ``-``.

    A document that parses but has the wrong shape is returned as is; the operation
    reports it as ``malformed``.

    Raises:
        RequestDocumentError: Unreadable, not UTF-8 or not YAML.
    """
    name = STDIN_NAME if source == STDIN_SOURCE else source
    try:
        raw = (
            sys.stdin.buffer.read()
            if source == STDIN_SOURCE
            else Path(source).read_bytes()
        )
    except OSError as error:
        raise RequestDocumentError(f"{name}: cannot read: {error}") from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RequestDocumentError(f"{name}: not UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise RequestDocumentError(f"{name}: not YAML: {error}") from error


def _print_json(document: object) -> None:
    """A JSON document on stdout."""
    sys.stdout.write(json.dumps(document, indent=JSON_INDENT, ensure_ascii=False))
    sys.stdout.write("\n")


def _with_optional(
    document: dict[str, object], **optional: object
) -> dict[str, object]:
    """``document`` plus each optional value that was given."""
    return {**document, **{k: v for k, v in optional.items() if v is not None}}


def _report_release_document(arguments: argparse.Namespace) -> dict[str, object]:
    """The ``report_release`` document: the flags given, ``mode`` only for
    ``--correct`` or ``--withdraw`` (the default mode is ``report``)."""
    mode = (
        ReportMode.CORRECT
        if arguments.correct
        else ReportMode.WITHDRAW
        if arguments.withdraw
        else None
    )
    return _with_optional(
        {},
        mode=None if mode is None else mode.value,
        commit=arguments.commit,
        version=arguments.version,
        changed=arguments.changed,
        touched=arguments.touched,
    )


def _document_for(name: OperationName, arguments: argparse.Namespace) -> object:
    """The request document an in-process operation is given, from its arguments."""
    match name:
        case OperationName.ADD:
            return add_document(arguments, read_request_document)
        case OperationName.RM:
            return rm_document(arguments)
        case OperationName.LIST:
            return list_document(arguments)
        case OperationName.ANSWER:
            return _with_optional(
                {"run_id": arguments.run_id, "text": arguments.text},
                paused_at=arguments.paused_at,
            )
        case OperationName.STATUS:
            return _with_optional({}, program=arguments.program)
        case OperationName.DECISIONS:
            return _with_optional({}, since=arguments.since, program=arguments.program)
        case OperationName.MARK_READ:
            return {"through": arguments.through}
        case OperationName.DISMISS:
            return _with_optional(
                {"run_id": arguments.run_id, "reason": arguments.reason},
                paused_at=arguments.paused_at,
            )
        case OperationName.RETRACT:
            return {"answer_seq": arguments.answer_seq, "reason": arguments.reason}
        case OperationName.REPORT_RELEASE:
            return _report_release_document(arguments)
        case OperationName.CHANGES:
            return _with_optional({}, since=arguments.since)
        case OperationName.HANDLE_PAUSE:
            raise ValueError(f"{name.value} has no request document")


def run_invoked(name: OperationName, arguments: argparse.Namespace) -> int:
    """Run an in-process operation through ``wiring.invoke``; print its result.

    The result is JSON with ``-j``, else the text of its renderer.
    """
    result: OperationResult = invoke(
        name, _document_for(name, arguments), Path.cwd(), Door.CLI
    )
    if arguments.json:
        _print_json(result_document(result))
    else:
        sys.stdout.write(_text_of(result, removing=name is OperationName.RM))
    return EXIT_REJECTED if is_rejected(result) else EXIT_OK


def _text_of(result: OperationResult, *, removing: bool) -> str:
    """The text of a result; ``add`` and ``rm`` also read Context Forge's names."""
    names: dict[str, str] = {}
    default_rules: tuple[str, ...] = ()
    if isinstance(result, SetUpResult):
        default_rules = load_config().default_rules_paths
        if result.outcome is not SetUpOutcome.UNCHANGED:
            names = _project_names()
    return render_result(
        result,
        now=datetime.now(UTC),
        names=names,
        default_rules=default_rules,
        removing=removing,
    )


def _project_names() -> dict[str, str]:
    """Names by id for the text; when ``cf`` cannot give them, ids print and stderr
    says so (the write already happened, so this is not an error exit)."""
    found = project_names(subprocess.run)
    if isinstance(found, CfCallFailed):
        sys.stderr.write(f"note: Context Forge names unavailable: {found.detail}\n")
        return {}
    return found


def run_handle_pause(layout: StateLayout, run_id: str, *, as_json: bool) -> int:
    config = load_config()
    deps = default_deps(layout)
    directory = Path.cwd()
    with open_store(layout) as store:
        result = handle_pause(store, config, run_id, directory=directory, deps=deps)
    if as_json:
        _print_json(asdict(result))
    else:
        sys.stdout.write(render_handle_pause(result))
    # After the result is printed: a log failure cannot change what was reported.
    now = deps.clock()
    reason = result.skip_reason or result.waiting_reason
    entry = result_entry(run_id, directory, result.outcome, reason, result.detail, now)
    append_call(layout.calls_log_dir, entry, now)
    return EXIT_OK


def log_failed_call(layout: StateLayout, run_id: str, error: Exception) -> None:
    """The calls-log line of a ``handle_pause`` that ended in an exit-3 error."""
    now = datetime.now(UTC)
    entry = error_entry(run_id, Path.cwd(), error, now)
    append_call(layout.calls_log_dir, entry, now)
