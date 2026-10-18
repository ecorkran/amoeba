"""The bind policy: loopback, or a token plus TLS (LLD D3).

:func:`check_bind` is pure apart from loading the TLS files, and runs before
uvicorn is constructed. A refusal never falls back to a loopback bind.
"""

from __future__ import annotations

import ipaddress
import ssl
from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.serve.settings import MIN_TOKEN_LENGTH, ServeSettings

#: The one host name counted as loopback without being an address literal.
_LOCALHOST: Final = "localhost"


class RefusalRule(StrEnum):
    """Which bind rule refused the start. Named in the refusal message."""

    TOKEN_REQUIRED = "token_required"
    TLS_REQUIRED = "tls_required"
    TOKEN_TOO_SHORT = "token_too_short"
    TLS_UNUSABLE = "tls_unusable"


class ServeRefusedError(Exception):
    """The configuration is not safe to serve. Exits with ``SERVE_REFUSED``."""

    def __init__(self, rule: RefusalRule, detail: str) -> None:
        super().__init__(f"{rule.value}: {detail}")
        self.rule = rule
        self.detail = detail


def is_loopback(host: str) -> bool:
    """Whether ``host`` is ``localhost`` or a loopback address literal.

    No name is resolved. Any other name, including a bracketed form such as
    ``[::1]``, counts as non-local.
    """
    if host.lower() == _LOCALHOST:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Specific: not an address literal. A name is never resolved, so it is
        # not loopback.
        return False


def check_bind(settings: ServeSettings, token: str | None) -> None:
    """Refuse an unsafe bind. The first matching rule decides.

    Args:
        settings: The host and TLS files to check.
        token: The bearer token, or ``None`` when unset.

    Raises:
        ServeRefusedError: Naming the rule. The token itself is never in it.
    """
    loopback = is_loopback(settings.host)
    certfile, keyfile = settings.tls_certfile, settings.tls_keyfile
    if token is not None and len(token) < MIN_TOKEN_LENGTH:
        raise ServeRefusedError(
            RefusalRule.TOKEN_TOO_SHORT,
            f"the token must be at least {MIN_TOKEN_LENGTH} characters",
        )
    if not loopback and token is None:
        raise ServeRefusedError(
            RefusalRule.TOKEN_REQUIRED,
            f"binding {settings.host!r} requires a bearer token",
        )
    if (certfile is None) != (keyfile is None):
        raise ServeRefusedError(
            RefusalRule.TLS_REQUIRED,
            "a TLS certificate and key must be given together",
        )
    if certfile is not None and keyfile is not None:
        _load_tls(certfile, keyfile)
        return
    if loopback:
        return
    raise ServeRefusedError(
        RefusalRule.TLS_REQUIRED,
        f"binding {settings.host!r} requires a TLS certificate and key",
    )


def _load_tls(certfile: Path, keyfile: Path) -> None:
    """Load the pair as uvicorn will, so a bad file refuses before binding."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(str(certfile), str(keyfile))
    except (OSError, ssl.SSLError) as error:
        # Specific: a missing, unreadable, or mismatched file is a refusal with
        # its path and reason, not a crash at bind time.
        raise ServeRefusedError(
            RefusalRule.TLS_UNUSABLE,
            f"cannot load certificate {certfile} with key {keyfile}: {error}",
        ) from error
