"""Dispatch: launching or resuming a step's pipeline in its checkout.

Pure pieces here (slice 125, D1-D5): ``checkout`` resolves where a slice runs,
``state`` derives where a step is in its dispatch from its own journal, ``params``
builds the pipeline's parameters, and ``planner`` turns a view into actions.
"""

from __future__ import annotations
