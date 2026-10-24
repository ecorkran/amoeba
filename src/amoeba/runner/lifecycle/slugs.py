"""The ``{index}-slice.`` stem rule: a slice's ``slice_name`` comes from CF's file name.

Review attribution matches a review's frontmatter ``slice`` against the slice node's
``cf.slice_name``, so the name must equal CF's own slug. Amoeba never builds a slug
from a slice's title: that would duplicate CF's ``slugify`` and drift from it. The
parsing rule itself lives in ``amoeba.upstream.context_forge.slice_stem``.
"""

from __future__ import annotations

from amoeba.upstream.context_forge import parse_slice_stem


def slice_name_from_design_file(design_file: str | None) -> str | None:
    """The slice name in a design file path, or ``None`` if there is none.

    ``None`` for no design file and for a file name not in the
    ``nnn-slice.{name}.md`` form; the caller logs the latter.
    """
    stem = parse_slice_stem(design_file)
    return None if stem is None else stem.name
