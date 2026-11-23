"""A hub's address, ``host:port``: the one parser (slice 260, D3).

The join line, the client file, ``join --address`` and ``hub.yaml`` all hold one, and
each checks it here when it takes the text in, so a connection never starts from text
that is not an address.
"""

from __future__ import annotations

from typing import Final

PORT_MIN: Final = 1
PORT_MAX: Final = 65535


def _in_range(port: int) -> bool:
    return PORT_MIN <= port <= PORT_MAX


def split_address(address: str) -> tuple[str, int]:
    """``host:port`` as its two parts; the host of ``[::1]:8443`` is ``::1``.

    Raises:
        ValueError: The text has no host, no port, a port that is not a number from
            1 to 65535, or a space or control character anywhere in it.
    """
    host, separator, port = address.rpartition(":")
    plain = all(c.isprintable() and not c.isspace() for c in address)
    numeric = port.isascii() and port.isdigit()
    if not (separator and host and plain and numeric and _in_range(int(port))):
        raise ValueError(f"{address!r} is not host:port")
    # A bracketed IPv6 host ("[::1]") is the address form; sockets want it bare.
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host, int(port)
