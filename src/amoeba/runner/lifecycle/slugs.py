"""The ``{index}-slice.`` stem rule: a slice's ``slice_name`` comes from CF's file name.

Review attribution matches a review's frontmatter ``slice`` against the slice node's
``cf.slice_name``, so the name must equal CF's own slug. Amoeba never builds a slug
from a slice's title: that would duplicate CF's ``slugify`` and drift from it.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Final

#: ``nnn-slice.{name}.md``, CF's design-file naming convention. Lenient about the
#: digits and the directory: only the file name's shape matters.
_DESIGN_FILE_STEM: Final = re.compile(r"^\d+-slice\.(?P<name>.+)\.md$")


def slice_name_from_design_file(design_file: str | None) -> str | None:
    """The slice name in a design file path, or ``None`` if there is none.

    ``None`` for no design file and for a file name not in the
    ``nnn-slice.{name}.md`` form; the caller logs the latter.
    """
    if not design_file:
        return None
    match = _DESIGN_FILE_STEM.match(PurePosixPath(design_file).name)
    return None if match is None else match.group("name")
