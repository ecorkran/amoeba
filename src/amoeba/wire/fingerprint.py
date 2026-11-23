"""The certificate fingerprint a join line carries (slice 260, D3)."""

from __future__ import annotations

import hashlib
import ssl


def fingerprint(pem_or_der: str | bytes) -> str:
    """SHA-256 of the certificate's DER bytes, as lower-case hex.

    Text is read as a PEM certificate, bytes as DER, so the same certificate has
    the same fingerprint whichever form it is held in.
    """
    der = (
        ssl.PEM_cert_to_DER_cert(pem_or_der)
        if isinstance(pem_or_der, str)
        else pem_or_der
    )
    return hashlib.sha256(der).hexdigest()


def normalize_fingerprint(text: str) -> str:
    """A fingerprint typed with colons or upper case, as the lower-case hex form."""
    return text.strip().replace(":", "").lower()
