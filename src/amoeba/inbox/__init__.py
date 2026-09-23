"""The inbox: the only way a part outside the resident process contributes state.

A submitter writes a file (``submit``) whether or not the process is running;
the process's ``InboxTenant`` drains it into the project's store, exactly once
per submission id. The full contract is in ``docs/inbox-contract.md``.

Exported here is the out-of-process API. ``submit`` is its only write path.
"""

from __future__ import annotations

from amoeba.inbox.envelope import EnvelopeError

__all__ = [
    "EnvelopeError",
]
