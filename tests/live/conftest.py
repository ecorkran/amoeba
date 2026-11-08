"""The live tier: real ``sq``, real models, real spend (slice 140, D10).

``--ignore=tests/live`` keeps a bare ``uv run pytest`` out of this directory, so
this file loads only when the tier is named: ``uv run pytest tests/live``. The
``answering`` sub-tier reads its own settings in its own ``conftest.py``; only what
every sub-tier needs lives here.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The tier's shared modules live beside the other harnesses in ``tests/``.
_TESTS_DIRECTORY = str(Path(__file__).parent.parent)
if _TESTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _TESTS_DIRECTORY)
