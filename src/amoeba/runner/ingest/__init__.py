"""Ingestion: what a finished run becomes (slice 125, D6, D7).

``outcome`` maps a finished run to the block a human must see and the entry's
outcome. ``reviews`` reads, parses and attributes the run's last review. ``record``
puts the two together, in one order that is safe to repeat.
"""

from __future__ import annotations
