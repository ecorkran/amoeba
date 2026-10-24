"""The ``{index}-slice.{name}`` stem rule, defined once.

CF names a slice ``NNN-slice.{name}`` (``fileSlice``, ``activeSlice``) and its design
file ``NNN-slice.{name}.md``. Everything that needs the index or the name of a slice
reads it through ``parse_slice_stem``: the read-back observer (``amoeba.process``) and
the lifecycle's slice-name rule (``amoeba.runner``). Neither may import the other, so
the rule lives here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

#: Lenient about the digit count, the directory and the ``.md`` suffix: only the shape
#: of the file name matters. The slug cannot start with a dot, so ``125-slice..md`` is
#: not a stem with the slug ``.md``.
_SLICE_STEM: Final = re.compile(r"^(?P<index>\d+)-slice\.(?P<slug>[^.].*?)(?:\.md)?$")


@dataclass(frozen=True)
class SliceStem:
    """A slice's index and CF slug."""

    index: int
    name: str


def parse_slice_stem(text: str | None) -> SliceStem | None:
    """The index and name in a slice stem or design file path, or ``None``.

    ``None`` for empty input and for any other shape; the caller decides what
    that means.
    """
    if not text:
        return None
    match = _SLICE_STEM.match(PurePosixPath(text.strip()).name)
    if match is None:
        return None
    return SliceStem(index=int(match.group("index")), name=match.group("slug"))
