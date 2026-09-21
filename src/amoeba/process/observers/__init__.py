"""Observers: the modules that know about a specific upstream.

``recovery.py`` is written against the ``Observer`` protocol and imports
nothing from here. Each module in this package knows about exactly one external
system and answers one question about it: what does it show for this journaled
command?

An observer never issues, retries, or repairs anything. Expected external
failure — a missing directory, a timeout, an unparseable file — is reported as
``Unknown``, which escalates to a human, rather than raised.
"""

from __future__ import annotations
