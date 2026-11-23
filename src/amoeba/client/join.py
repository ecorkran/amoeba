"""The network and file steps of `join` and `leave` (slice 260, D4).

``join`` fetches the hub's certificate, compares its fingerprint with the join line's,
saves it, makes one ``hello`` call with the token over the pinned connection, and
writes the client file. ``wiring_door`` runs these steps in order, around the local
store's set-aside.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from amoeba.client.call import MACHINE_PLACEHOLDER, call
from amoeba.client.client_file import ClientFile, load_client_file, write_client_file
from amoeba.client.errors import HubRefusedError
from amoeba.client.trust import fetch_certificate
from amoeba.wire.address import split_address
from amoeba.wire.atomic_file import PUBLIC_FILE_MODE, write_through_rename
from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.join_line import JoinError, JoinLine
from amoeba.wire.protocol import HELLO_CALL, HELLO_MACHINE_KEY, RefusalCode
from amoeba.wire.times import DoorTimes


def _machine_name(result: dict[str, object]) -> str:
    machine = result.get(HELLO_MACHINE_KEY)
    if not isinstance(machine, str) or not machine:
        raise HubRefusedError(
            "the hub's hello reply named no machine", RefusalCode.HUB_FAULT
        )
    return machine


def _restore_certificate(cert_path: Path, previous: bytes | None) -> None:
    if previous is None:
        cert_path.unlink(missing_ok=True)
    else:
        write_through_rename(cert_path, previous, PUBLIC_FILE_MODE)


def join(  # noqa: PLR0913 - the line, the two files, the times and the middle step
    line: JoinLine,
    *,
    client_path: Path,
    cert_path: Path,
    between: Callable[[], None],
    times: DoorTimes = DoorTimes(),  # noqa: B008  frozen, no state to share
) -> str:
    """Join the hub the line names; returns this machine's name.

    ``between`` runs after ``hello`` succeeded and before the client file is written
    (the set-aside of the local store). A failure at any point before the client file
    is written removes the saved certificate, or puts the previous one back, then
    raises; nothing is retried here apart from the retry inside the ``hello`` call.

    Raises:
        HubUnreachableError: Nothing at the address speaks TLS.
        JoinError: The certificate is not the one the line names (both fingerprints
            are in the message; the token was never sent).
        HubRefusedError, HubCertificateError: The ``hello`` call's own errors.
    """
    pem = fetch_certificate(line.address, times.connect_seconds)
    presented = fingerprint(pem)
    if presented != line.fingerprint:
        raise JoinError(
            f"the hub at {line.address} presented a certificate with fingerprint "
            f"{presented}, not the {line.fingerprint} in the join line; nothing was "
            "saved and the token was not sent"
        )
    previous = cert_path.read_bytes() if cert_path.exists() else None
    write_through_rename(cert_path, pem.encode("utf-8"), PUBLIC_FILE_MODE)
    joined = False
    try:
        probe = ClientFile(
            address=line.address, machine=MACHINE_PLACEHOLDER, token=line.token
        )
        machine = _machine_name(call(probe, cert_path, HELLO_CALL, {}, times))
        between()
        write_client_file(
            client_path,
            ClientFile(address=line.address, machine=machine, token=line.token),
        )
        joined = True
    finally:
        # Whatever went wrong before the client file was written, the saved
        # certificate goes back to what it was; the failure itself still propagates.
        if not joined:
            _restore_certificate(cert_path, previous)
    return machine


def change_address(client_path: Path, cert_path: Path, address: str) -> ClientFile:
    """Change only the address in the client file; makes no hub call.

    Raises:
        JoinError: There is no client file: the machine is not joined.
        ClientFileError: The file or the saved certificate cannot be used.
    """
    if not client_path.exists():
        raise JoinError(
            f"this machine is not joined (no {client_path}); run `amoeba join <line>` "
            "with a line from `amoeba hub invite`"
        )
    try:
        split_address(address)
    except ValueError as error:
        raise JoinError(str(error)) from error
    current = load_client_file(client_path, cert_path)
    changed = ClientFile(address=address, machine=current.machine, token=current.token)
    write_client_file(client_path, changed)
    return changed


def remove_client_files(client_path: Path, cert_path: Path) -> list[Path]:
    """Delete the client file, then the saved certificate; each is skipped when there
    is nothing there. Returns what was deleted. Makes no hub call."""
    removed: list[Path] = []
    for path in (client_path, cert_path):
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed
