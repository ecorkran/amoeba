"""Find the ``@path`` imports in a rules file's text (slice 229, D10).

An import is a token that starts with ``@`` at the start of a line or after
whitespace, outside fenced blocks and inline code, whose path has no whitespace, ends
in ``.md`` once trailing ``.,;:)`` is removed, and does not start with ``/`` or ``~``.
Requiring ``.md`` keeps ``@types/node`` and ``@modelcontextprotocol/server`` from
being read as imports. A ``..`` segment is returned as written: whether the path
stays inside the repository is decided where it is resolved.

Pure: no file is read here.
"""

from __future__ import annotations

import re
from typing import Final

from amoeba.answering.passages import fence_after

_TRAILING_PUNCTUATION: Final = ".,;:)"
#: Rules files whose ``@path`` imports are read, and what an import must end in.
MARKDOWN_SUFFIX: Final = ".md"
_NOT_REPO_RELATIVE: Final = ("/", "~")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_TOKEN = re.compile(r"(?:^|(?<=\s))@(\S+)")


def rule_imports(text: str) -> tuple[str, ...]:
    """The import paths in ``text``, in order of first appearance, each once."""
    found: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        fence = fence_after(line, fence)
        if fence is not None:
            continue
        # Blank the spans, so the characters around them keep their positions.
        prose = _INLINE_CODE.sub(lambda span: " " * len(span.group(0)), line)
        for token in _TOKEN.findall(prose):
            path = token.rstrip(_TRAILING_PUNCTUATION)
            if _is_import_path(path):
                found.append(path)
    return tuple(dict.fromkeys(found))


def _is_import_path(path: str) -> bool:
    return (
        len(path) > len(MARKDOWN_SUFFIX)
        and path.endswith(MARKDOWN_SUFFIX)
        and not path.startswith(_NOT_REPO_RELATIVE)
    )
