"""The client's typed errors (slice 260). Each joins ``wiring.OPERATIONAL_ERRORS``.

They live here so ``trust`` and ``call`` do not import each other.
"""

from __future__ import annotations

from amoeba.wire.protocol import RefusalCode


class ClientFileError(Exception):
    """The client file or the saved certificate cannot be used; names the file."""


class HubUnreachableError(Exception):
    """No reply from the hub (refused, timed out, not TLS, or not a reply)."""


class HubCertificateError(Exception):
    """The hub did not present the saved certificate; never retried."""


class HubRefusedError(Exception):
    """The hub refused the call. ``code`` is the refusal code it gave."""

    def __init__(self, message: str, code: RefusalCode) -> None:
        super().__init__(message)
        self.code = code
