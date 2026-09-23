"""The inbox: the only way a part outside the resident process contributes state.

A submitter writes a file (``submit``) whether or not the process is running;
the process's ``InboxTenant`` drains it into the project's store, exactly once
per submission id. The full contract is in ``docs/inbox-contract.md``.

Exported here is the out-of-process API. ``submit`` is its only write path.
"""

from __future__ import annotations

from amoeba.inbox.envelope import EnvelopeError
from amoeba.inbox.pending import (
    FailedSubmission,
    PendingSubmission,
    QuarantinedSubmission,
    failed,
    pending,
    quarantined,
)
from amoeba.inbox.submit import (
    InboxSubmitError,
    InvalidSubmissionError,
    SubmissionWriteError,
    submit,
)

__all__ = [
    # The one write path
    "submit",
    # Read-only listings
    "failed",
    "pending",
    "quarantined",
    # Transfer objects
    "FailedSubmission",
    "PendingSubmission",
    "QuarantinedSubmission",
    # Exceptions
    "EnvelopeError",
    "InboxSubmitError",
    "InvalidSubmissionError",
    "SubmissionWriteError",
]
