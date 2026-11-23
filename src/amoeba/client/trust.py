"""The client's TLS trust: pinned to one certificate (slice 260, D4, D5).

A call trusts only the certificate saved at `join`, with no system certificates and no
host name check (the hub's certificate is self-signed for ``amoeba-hub``). The one
exception is :func:`fetch_certificate`, the unverified connection of `join` step 3.
"""

from __future__ import annotations

import socket
import ssl
from pathlib import Path

from amoeba.client.errors import HubUnreachableError
from amoeba.wire.address import split_address


def pinned_context(cert_path: Path) -> ssl.SSLContext:
    """A client context that trusts only the certificate at ``cert_path``."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(cert_path))
    return context


def fetch_certificate(address: str, connect_seconds: float) -> str:
    """The certificate the hub at ``address`` presents, as PEM.

    The one unverified connection of D4 step 3: there is no certificate to check
    against yet. It sends no request bytes, reads the presented certificate and
    closes; the caller compares its fingerprint with the join line's.

    Raises:
        HubUnreachableError: Connection refused, a timeout, or a peer with no TLS;
            names the address and the cause.
    """
    host, port = split_address(address)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with (
            socket.create_connection((host, port), timeout=connect_seconds) as raw,
            context.wrap_socket(raw) as secure,
        ):
            der = secure.getpeercert(binary_form=True)
    except OSError as error:
        raise HubUnreachableError(
            f"cannot reach the hub at {address}: {error}"
        ) from error
    if der is None:
        raise HubUnreachableError(f"the hub at {address} presented no certificate")
    return ssl.DER_cert_to_PEM_cert(der)
