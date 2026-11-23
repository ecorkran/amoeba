"""The hub's certificate and D5's table of starts (slice 260)."""

from __future__ import annotations

import itertools
import ssl
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from amoeba.hub.certificate import (
    CertificateHooks,
    StartKind,
    classify_start,
    make_certificate,
)
from amoeba.wire.fingerprint import fingerprint

CERT = "hub-cert.pem"
KEY = "hub-key.pem"


def test_the_made_certificate_has_the_name_the_curve_and_no_end(
    tmp_path: Path,
) -> None:
    make_certificate(tmp_path / CERT, tmp_path / KEY)

    certificate = x509.load_pem_x509_certificate((tmp_path / CERT).read_bytes())
    common_name = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)

    assert [attribute.value for attribute in common_name] == ["amoeba-hub"]
    public_key = certificate.public_key()
    assert isinstance(public_key, ec.EllipticCurvePublicKey)
    assert public_key.curve.name == "secp256r1"
    assert certificate.not_valid_after_utc == datetime(
        9999, 12, 31, 23, 59, 59, tzinfo=UTC
    )
    assert certificate.not_valid_before_utc < datetime.now(UTC)


def test_the_key_file_is_0600_and_no_temporary_file_is_left(tmp_path: Path) -> None:
    make_certificate(tmp_path / CERT, tmp_path / KEY)

    assert stat.S_IMODE((tmp_path / KEY).stat().st_mode) == 0o600
    assert sorted(path.name for path in tmp_path.iterdir()) == [CERT, KEY]


def test_the_key_is_written_before_the_certificate(tmp_path: Path) -> None:
    class Stop(Exception):
        pass

    def stop() -> None:
        raise Stop

    with pytest.raises(Stop):
        make_certificate(
            tmp_path / CERT, tmp_path / KEY, CertificateHooks(after_key=stop)
        )

    assert (tmp_path / KEY).exists()
    assert not (tmp_path / CERT).exists()


def test_the_certificate_matches_its_key_and_loads_for_tls(tmp_path: Path) -> None:
    make_certificate(tmp_path / CERT, tmp_path / KEY)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.load_cert_chain(tmp_path / CERT, tmp_path / KEY)
    assert len(fingerprint((tmp_path / CERT).read_text(encoding="utf-8"))) == 64


EXPECTED = {
    # (store, cert, key, backup): kind
    (True, True, True, False): StartKind.NORMAL,
    (True, True, True, True): StartKind.NORMAL,
    (True, True, False, True): StartKind.DAMAGED_REFUSED,
    (True, False, True, True): StartKind.DAMAGED_REFUSED,
    (True, False, False, True): StartKind.DAMAGED_REFUSED,
    (True, True, False, False): StartKind.DAMAGED_NEW_PAIR,
    (True, False, True, False): StartKind.DAMAGED_NEW_PAIR,
    (True, False, False, False): StartKind.DAMAGED_NEW_PAIR,
    (False, True, True, True): StartKind.LOST_REFUSED,
    (False, True, False, True): StartKind.LOST_REFUSED,
    (False, False, True, True): StartKind.LOST_REFUSED,
    (False, False, False, True): StartKind.LOST_REFUSED,
    (False, True, True, False): StartKind.FIRST_PAIR_KEPT,
    (False, True, False, False): StartKind.FIRST_LONE_FILE_REPLACED,
    (False, False, True, False): StartKind.FIRST_LONE_FILE_REPLACED,
    (False, False, False, False): StartKind.FIRST_START,
}


def test_the_table_covers_all_sixteen_combinations() -> None:
    assert set(EXPECTED) == set(itertools.product([True, False], repeat=4))


@pytest.mark.parametrize(("facts", "kind"), sorted(EXPECTED.items()))
def test_each_combination_is_its_row_of_the_table(
    facts: tuple[bool, bool, bool, bool], kind: StartKind
) -> None:
    assert classify_start(*facts).kind is kind


@pytest.mark.parametrize(
    ("has_cert", "has_key", "named"),
    [(True, False, [KEY]), (False, True, [CERT]), (False, False, [CERT, KEY])],
)
def test_a_refusal_names_the_missing_files(
    has_cert: bool, has_key: bool, named: list[str]
) -> None:
    decision = classify_start(True, has_cert, has_key, True)

    assert decision.kind.is_refusal
    assert list(decision.missing) == named


def test_only_two_kinds_are_refusals() -> None:
    assert {kind for kind in StartKind if kind.is_refusal} == {
        StartKind.DAMAGED_REFUSED,
        StartKind.LOST_REFUSED,
    }
