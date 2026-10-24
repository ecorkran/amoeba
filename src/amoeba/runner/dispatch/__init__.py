"""Dispatch: pointing a step's checkout at its slice, then launching its pipeline.

Pure pieces here (slice 125, D1-D5): ``checkout`` resolves where a slice runs,
``state`` derives where a step is in its dispatch from its own journal, ``params``
builds the pipeline's parameters, and ``planner`` turns a view into actions. The
I/O pieces (the pointer write and its read-back) live in ``pointer``.
"""

from __future__ import annotations
