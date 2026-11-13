"""What a ``handle_pause`` call needs from its caller (slice 226, D6).

``handle_pause`` takes its checkout from the process's working directory, so a
door that cannot change its own directory (the MCP server) names the run and the
checkout together. The run id is any string: it is passed after ``--`` so a leading
``-`` is not read as a flag.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StrictStr


def _absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError(f"must be an absolute path, got {str(path)!r}")
    return path


class HandlePauseCall(BaseModel):
    """The run to handle and the checkout it runs in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: StrictStr
    directory: Annotated[Path, AfterValidator(_absolute)]
