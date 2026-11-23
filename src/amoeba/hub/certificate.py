"""The hub's certificate and what a start does about its files (slice 260, D5).

``make_certificate`` writes an EC P-256 key and a self-signed certificate that never
expires. ``classify_start`` is the one place D5's table of rows is written: a pure
function of four facts, so every combination is tested without files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from amoeba.config.home import HUB_CERT_FILE_NAME, HUB_KEY_FILE_NAME
from amoeba.wire.atomic_file import (
    PRIVATE_FILE_MODE,
    PUBLIC_FILE_MODE,
    write_through_rename,
)

#: The certificate's common name.
COMMON_NAME: Final = "amoeba-hub"
#: X.509's value for "no well-defined expiration" (RFC 5280, 4.1.2.5).
NO_EXPIRY: Final = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)
#: Clock skew allowed between the hub and a client when the certificate is checked.
BACKDATE: Final = timedelta(minutes=5)


@dataclass(frozen=True)
class CertificateHooks:
    """The fault seam of a first start: production passes none."""

    after_key: Callable[[], None] | None = None


def make_certificate(
    cert_path: Path,
    key_path: Path,
    hooks: CertificateHooks = CertificateHooks(),  # noqa: B008  frozen, no state
) -> None:
    """Write a new key (mode ``0600``), then the certificate that goes with it.

    Each file goes through a temporary name and a rename, and the key is first, so a
    stop between the two leaves a lone key (D5's "first start stopped between its two
    certificate files"), never a certificate without its key.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    write_through_rename(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        PRIVATE_FILE_MODE,
    )
    if hooks.after_key is not None:
        hooks.after_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, COMMON_NAME)])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - BACKDATE)
        .not_valid_after(NO_EXPIRY)
        .sign(key, hashes.SHA256())
    )
    write_through_rename(
        cert_path,
        certificate.public_bytes(serialization.Encoding.PEM),
        PUBLIC_FILE_MODE,
    )


class StartKind(StrEnum):
    """One value per row of D5's table."""

    NORMAL = "normal"
    DAMAGED_REFUSED = "damaged_refused"
    DAMAGED_NEW_PAIR = "damaged_new_pair"
    LOST_REFUSED = "lost_refused"
    FIRST_PAIR_KEPT = "first_pair_kept"
    FIRST_LONE_FILE_REPLACED = "first_lone_file_replaced"
    FIRST_START = "first_start"

    @property
    def is_refusal(self) -> bool:
        return self in {StartKind.DAMAGED_REFUSED, StartKind.LOST_REFUSED}


@dataclass(frozen=True)
class StartDecision:
    """What a start does, and the certificate files it found missing."""

    kind: StartKind
    #: The certificate and key file names that are not there, in that order.
    missing: tuple[str, ...]


def classify_start(
    has_store: bool, has_cert: bool, has_key: bool, has_backup: bool
) -> StartDecision:
    """D5's table. ``has_backup`` is ignored when a store has both its files."""
    missing = tuple(
        name
        for name, present in (
            (HUB_CERT_FILE_NAME, has_cert),
            (HUB_KEY_FILE_NAME, has_key),
        )
        if not present
    )
    if has_store and not missing:
        return StartDecision(StartKind.NORMAL, missing)
    if has_store:
        kind = StartKind.DAMAGED_REFUSED if has_backup else StartKind.DAMAGED_NEW_PAIR
    elif has_backup:
        kind = StartKind.LOST_REFUSED
    elif not missing:
        kind = StartKind.FIRST_PAIR_KEPT
    elif len(missing) == 1:
        kind = StartKind.FIRST_LONE_FILE_REPLACED
    else:
        kind = StartKind.FIRST_START
    return StartDecision(kind, missing)
