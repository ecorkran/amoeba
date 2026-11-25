"""One call to the hub, with retry (slice 260, D5, D6, D7, D10).

The call is a ``POST /call/<name>`` over a connection that trusts only the saved
certificate. With no reply (refused, timed out, or a body that is not a reply) it waits
and tries again with the same call id while less than the retry time has passed, then
raises ``HubUnreachableError``; the client goes by the reply's body, never its status.
"""

from __future__ import annotations

import http.client
import json
import ssl
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Final
from urllib.parse import quote

from amoeba.client.client_file import ClientFile
from amoeba.client.errors import (
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.client.trust import pinned_context
from amoeba.program_version import program_version
from amoeba.wire.address import split_address
from amoeba.wire.protocol import (
    CALL_PATH_PREFIX,
    DOCUMENT_KEY,
    HEADER_AUTHORIZATION,
    HEADER_CALL_ID,
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    UNKNOWN_ADVICE,
    UPGRADE_COMMAND,
    WRITING_CALLS,
    WRITING_STEPS,
    DoneReply,
    RefusalCode,
    RefusedReply,
    SessionIdentity,
    parse_reply,
)
from amoeba.wire.times import DOOR_VERSION, DoorTimes

JSON_TYPE: Final = "application/json"
#: Where a refused ``bad_token`` names the machine before the hub has told it its name.
MACHINE_PLACEHOLDER: Final = "<machine>"


def client_version() -> str:
    """The installed package version, sent with every call."""
    return program_version()


def _address_hint(address: str) -> str:
    return (
        f"if the hub's address has changed, `amoeba join --address <host:port>` sets "
        f"the new one (this machine uses {address})"
    )


def _refusal(client_file: ClientFile, reply: RefusedReply) -> HubRefusedError:
    text = (
        f"the hub at {client_file.address} refused the call: "
        f"{reply.code.value}: {reply.message}"
    )
    if reply.code is RefusalCode.DOOR_VERSION:
        text += f". Upgrade this client: `{UPGRADE_COMMAND}`"
    if reply.code is RefusalCode.BAD_TOKEN:
        text += (
            f". This machine's token is not known to the hub: run "
            f"`amoeba hub invite {client_file.machine}` on the hub and "
            "`amoeba join <line>` here"
        )
    return HubRefusedError(text, reply.code)


def _version_mismatch(client_file: ClientFile, header: str | None) -> HubRefusedError:
    text = (
        f"the hub at {client_file.address} speaks door version {header}, this client "
        f"speaks {DOOR_VERSION}. Upgrade this client: `{UPGRADE_COMMAND}`"
    )
    return HubRefusedError(text, RefusalCode.DOOR_VERSION)


def session_headers(identity: SessionIdentity) -> dict[str, str]:
    """The four session headers (263 D6): the directory percent-encoded, the project
    header left out for a non-project."""
    headers = {
        HEADER_SESSION_ID: identity.session_id,
        HEADER_SESSION_CLIENT: identity.client,
        HEADER_SESSION_DIRECTORY: quote(identity.directory, safe="/"),
    }
    if identity.project_id is not None:
        headers[HEADER_SESSION_PROJECT] = identity.project_id
    return headers


def _attempt(  # noqa: PLR0913 - one attempt's pieces
    client_file: ClientFile,
    context: ssl.SSLContext,
    path: str,
    body: bytes,
    headers: Mapping[str, str],
    times: DoorTimes,
) -> tuple[bytes, str | None]:
    """One attempt; the reply body and its door-version header.

    Raises:
        ssl.SSLCertVerificationError: The hub did not present the saved certificate.
        OSError, http.client.HTTPException: No reply.
    """
    host, port = split_address(client_file.address)
    connection = http.client.HTTPSConnection(
        host, port, context=context, timeout=times.connect_seconds
    )
    try:
        connection.connect()
        if connection.sock is not None:
            connection.sock.settimeout(times.read_seconds)
        connection.request(
            "POST",
            path,
            body=body,
            headers=headers,
        )
        response = connection.getresponse()
        return response.read(), response.getheader(HEADER_DOOR_VERSION)
    finally:
        connection.close()


def _certificate_error(client_file: ClientFile) -> HubCertificateError:
    return HubCertificateError(
        f"the hub at {client_file.address} did not present the saved certificate. "
        "If the address is wrong, `amoeba join --address <host:port>` sets the right "
        "one; if the hub was replaced by a new one, run "
        f"`amoeba hub invite {client_file.machine}` there and `amoeba join <line>` here"
    )


def _unreachable(
    client_file: ClientFile, name: str, tried_seconds: float
) -> HubUnreachableError:
    text = (
        f"no reply from the hub at {client_file.address} after "
        f"{tried_seconds:.0f} s; {_address_hint(client_file.address)}"
    )
    if name in WRITING_CALLS or name in WRITING_STEPS:
        text += f". The outcome of this call is unknown. {UNKNOWN_ADVICE[name]}"
    return HubUnreachableError(text)


def call(  # noqa: PLR0913 - the file, the certificate, the call and how long to try
    client_file: ClientFile,
    cert_path: Path,
    name: str,
    document: object,
    times: DoorTimes = DoorTimes(),  # noqa: B008  frozen, no state to share
    call_id: str | None = None,
    extra: Mapping[str, object] | None = None,
    identity: SessionIdentity | None = None,
) -> dict[str, object]:
    """Make the call and return its result document.

    One call id, made here when none is given, is used by every repeat, so the hub
    applies a repeated writing call once. ``extra`` holds the body keys beside
    ``document`` for values only this machine can read (the caller's project, the
    runs; 261 D5). ``identity`` adds the session headers (263 D6).

    Raises:
        HubCertificateError: The hub did not present the saved certificate; never
            retried.
        HubRefusedError: The hub refused the call, or speaks another door version.
        HubUnreachableError: No reply within the retry time.
    """
    context = pinned_context(cert_path)
    path = f"{CALL_PATH_PREFIX}{name}"
    body = json.dumps({DOCUMENT_KEY: document, **(extra or {})}).encode("utf-8")
    sent_id = call_id if call_id is not None else uuid.uuid4().hex
    headers = {
        HEADER_AUTHORIZATION: f"Bearer {client_file.token}",
        HEADER_DOOR_VERSION: str(DOOR_VERSION),
        HEADER_CLIENT_VERSION: client_version(),
        HEADER_CALL_ID: sent_id,
        "Content-Type": JSON_TYPE,
        **({} if identity is None else session_headers(identity)),
    }
    started = time.monotonic()
    while True:
        try:
            reply_body, version_header = _attempt(
                client_file, context, path, body, headers, times
            )
        except ssl.SSLCertVerificationError as error:
            # A subclass of OSError, so it is caught first: a certificate that does
            # not match is never "no reply" and is never retried (D5).
            raise _certificate_error(client_file) from error
        except (OSError, http.client.HTTPException):
            reply = None
            version_header = None
        else:
            reply = parse_reply(reply_body)
        if reply is not None:
            if version_header != str(DOOR_VERSION):
                raise _version_mismatch(client_file, version_header)
            match reply:
                case RefusedReply():
                    raise _refusal(client_file, reply)
                case DoneReply():
                    return reply.result
        elapsed = time.monotonic() - started
        if elapsed + times.retry_pause_seconds >= times.retry_seconds:
            # The next attempt would start at or after the retry time.
            raise _unreachable(client_file, name, elapsed)
        time.sleep(times.retry_pause_seconds)
