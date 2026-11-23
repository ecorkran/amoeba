"""The ``origin`` rule: when two checkouts are the same repo (slice 261, D3).

``reduce_origin`` turns the address ``git remote get-url origin`` prints into
``host[:port]/path``, or nothing. ``is_reduced_origin`` says whether a value is
already in that form, which is what the hub checks, because reducing a reduced form
would change or empty it. Both are pure and import only the standard library.

The address as git printed it can hold a password. ``reduce_origin`` never raises
and never puts the address in an error, and only its output may leave the client.
"""

from __future__ import annotations

import re
from typing import Final

#: ``scheme://`` at the start of the text.
_URL_PREFIX: Final = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
#: The SSH short form: ``[user@]host:path``. The host holds no ``/`` or ``@``.
_SCP_FORM: Final = re.compile(r"^(?:[^@/:\s]+@)?([^@/:\s]+):(.+)$")
#: A reduced host: no ``@``, no ``/``, an optional numeric port after one colon.
_REDUCED_HOST: Final = re.compile(r"^[^\s@:/]+(?::\d+)?$")
_GIT_SUFFIX: Final = ".git"
_SLASH: Final = "/"
_USERINFO_END: Final = "@"
_FILE_SCHEME: Final = "file://"


def _join(host: str, path: str) -> str | None:
    """``host/path`` in reduced form, or ``None`` when either part is unusable."""
    host = host.lower()
    path = path.lower().strip()
    # A trailing slash, then ``.git``, then a slash (D3).
    path = path.removesuffix(_SLASH).removesuffix(_GIT_SUFFIX).removesuffix(_SLASH)
    path = path.lstrip(_SLASH)
    if not path or "\\" in path or any(part.isspace() for part in path):
        return None
    if _REDUCED_HOST.fullmatch(host) is None:
        return None
    return f"{host}{_SLASH}{path}"


def _from_url(address: str) -> str | None:
    if address.lower().startswith(_FILE_SCHEME):
        return None
    remainder = _URL_PREFIX.sub("", address, count=1)
    authority, _, path = remainder.partition(_SLASH)
    # The password may hold ``@``, so the host follows the last one.
    host = authority.rpartition(_USERINFO_END)[2]
    return _join(host, path)


def _from_scp_form(address: str) -> str | None:
    match = _SCP_FORM.match(address)
    if match is None:
        return None
    return _join(match.group(1), match.group(2))


def reduce_origin(address: str) -> str | None:
    """The reduced remote, or ``None`` when ``address`` names no host and path.

    Accepts ``scheme://[user[:password]@]host[:port]/path`` and ``[user@]host:path``.
    Drops the scheme, user and password, keeps a port, lower-cases, and removes a
    trailing slash, then ``.git``, then a slash. A filesystem path, ``file://`` and
    text it cannot read as a host and a path give ``None``, as does no remote.
    """
    text = address.strip()
    if not text or text.startswith((_SLASH, ".", "~")):
        return None
    if _URL_PREFIX.match(text):
        return _from_url(text)
    return _from_scp_form(text)


def is_reduced_origin(value: str) -> bool:
    """Whether ``value`` is already ``host[:port]/path`` in the form D3 gives.

    A host and a path, lower case, no ``://``, no ``@`` in the host, no whitespace,
    no trailing slash and no trailing ``.git``.
    """
    if value != value.lower() or "://" in value:
        return False
    host, separator, path = value.partition(_SLASH)
    if not separator or not path or any(char.isspace() for char in value):
        return False
    if _REDUCED_HOST.fullmatch(host) is None:
        return False
    return not path.endswith((_SLASH, _GIT_SUFFIX))
