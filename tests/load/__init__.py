"""The load tier: crash-loop and recovery-scale tests.

Required by the Python rules now that concurrency and process boundaries enter
the codebase. These drive **real** resident processes through crash loops and
reconcile hundreds of entries against a thousand run files, so they take far
longer than the default suite and are excluded from it by ``--ignore`` in
``pyproject.toml``.

Run them explicitly::

    uv run pytest tests/load

CI runs them as a separate step, able to fail the build independently of the
default suite.
"""

from __future__ import annotations
