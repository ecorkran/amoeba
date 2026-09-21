"""The ``amoeba`` command-line interface.

``argparse`` only — the CLI adds no dependency of its own (D3). This package
owns the exit-code vocabulary and the single documented process-boundary
handler; nothing under ``amoeba.process`` references an exit code.
"""

from __future__ import annotations
