"""The input contract: what Amoeba writes before the pipeline runs (D4)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.runner.request_run.pipeline_file import MIN_INDEX, NEED_FILE


@dataclass(frozen=True)
class RequestInput:
    """One request: who asks, for which slice (``<index> <name>``), and the need."""

    asking_project_id: str
    asking_slice_label: str
    requests_index: int
    need: str


def _require_single_line(name: str, value: str) -> None:
    # splitlines breaks on every Unicode line separator, not only CR and LF; a value
    # that is one line is its own single splitlines item (a trailing break is not).
    if not value.strip() or value.splitlines() != [value]:
        raise ValueError(f"{name} must be a non-blank single line")


def render_need(request: RequestInput) -> str:
    """The exact ``need.md`` content of D4. The need text is verbatim.

    Raises:
        ValueError: For a blank need, a requests index below ``MIN_INDEX``, or a
            project id or slice label that is blank or spans lines.
    """
    _require_single_line("asking_project_id", request.asking_project_id)
    _require_single_line("asking_slice_label", request.asking_slice_label)
    if request.requests_index < MIN_INDEX:
        raise ValueError(
            f"requests_index must be at least {MIN_INDEX}, got {request.requests_index}"
        )
    if not request.need.strip():
        raise ValueError("need must not be blank")
    asker = f"{request.asking_project_id}, slice {request.asking_slice_label}"
    return (
        "# Request\n\n"
        f"requested by: {asker}\n"
        f"requests initiative: {request.requests_index}\n\n"
        f"{request.need}"
    )


def prepare_request_directory(directory: Path, request: RequestInput) -> None:
    """Write ``need.md`` into an existing, empty directory.

    Raises:
        ValueError: Misuse (a programming error): the directory is absent or not
            empty, or the request is invalid.
    """
    if not directory.is_dir():
        raise ValueError(f"request directory does not exist: {directory}")
    if any(directory.iterdir()):
        raise ValueError(f"request directory is not empty: {directory}")
    # Render first, so an invalid request leaves no file.
    need_text = render_need(request)
    # Bytes, so no newline translation touches the need.
    (directory / NEED_FILE).write_bytes(need_text.encode("utf-8"))
