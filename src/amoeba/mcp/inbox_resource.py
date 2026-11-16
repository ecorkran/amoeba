"""The ``amoeba://inbox`` resource and the capabilities push declares (slice 241, D3,
D5).

Every handler first waits for presence to resolve, so none answers from the pending
state; only that request waits. ``read`` returns the member and the number ``inbox``
reports as ``as_of_seq``, never message text. ``subscribe`` and ``unsubscribe`` set
and clear a flag on the event loop, which the watcher reads before sending a
resource update. Capabilities are fixed at ``initialize``, before the member is
known, so every server declares both the channel and the subscribable resources.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Final

import anyio.to_thread
import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import MCPError

from amoeba.mcp.channel_event import CHANNEL_CAPABILITY
from amoeba.mcp.presence import PresenceState
from amoeba.wiring_presence import StoreError, StoreOpener, read_as_of_seq

#: The one resource this server offers.
INBOX_URI: Final = "amoeba://inbox"
INBOX_NAME: Final = "inbox"
INBOX_MIME_TYPE: Final = "application/json"
#: Sent after a channel event to a client that subscribed to ``INBOX_URI``.
RESOURCE_UPDATED_METHOD: Final = "notifications/resources/updated"
#: The resource document's keys.
MEMBER_FIELD: Final = "member"
AS_OF_SEQ_FIELD: Final = "as_of_seq"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InboxResource:
    """The four handlers, over the server's presence and its store opener."""

    state: PresenceState
    open_store: StoreOpener

    async def _member(self, uri: str) -> str:
        """The member, for a request about ``INBOX_URI``; invalid-params otherwise."""
        await self.state.resolved.wait()
        member = self.state.member_id
        if member is None:
            raise MCPError(types.INVALID_PARAMS, "this server serves no member")
        if uri != INBOX_URI:
            raise MCPError(types.INVALID_PARAMS, f"unknown resource {uri!r}")
        return member

    async def list_resources(
        self,
        ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None,
    ) -> types.ListResourcesResult:
        await self.state.resolved.wait()
        if self.state.member_id is None:
            return types.ListResourcesResult(resources=[])
        resource = types.Resource(
            name=INBOX_NAME, uri=INBOX_URI, mime_type=INBOX_MIME_TYPE
        )
        return types.ListResourcesResult(resources=[resource])

    async def read_resource(
        self, ctx: ServerRequestContext[Any], params: types.ReadResourceRequestParams
    ) -> types.ReadResourceResult:
        member = await self._member(str(params.uri))
        try:
            as_of_seq = await anyio.to_thread.run_sync(read_as_of_seq, self.open_store)
        except StoreError as error:
            # This request fails, naming the error; the server keeps serving.
            logger.exception("inbox resource read failed")
            raise MCPError(
                types.INTERNAL_ERROR, f"{type(error).__name__}: {error}"
            ) from error
        document = {MEMBER_FIELD: member, AS_OF_SEQ_FIELD: as_of_seq}
        contents = types.TextResourceContents(
            uri=INBOX_URI, mime_type=INBOX_MIME_TYPE, text=json.dumps(document)
        )
        return types.ReadResourceResult(contents=[contents])

    async def subscribe(
        self, ctx: ServerRequestContext[Any], params: types.SubscribeRequestParams
    ) -> types.EmptyResult:
        await self._member(str(params.uri))
        self.state.subscribed = True
        return types.EmptyResult()

    async def unsubscribe(
        self, ctx: ServerRequestContext[Any], params: types.UnsubscribeRequestParams
    ) -> types.EmptyResult:
        await self._member(str(params.uri))
        self.state.subscribed = False
        return types.EmptyResult()


def register_inbox_resource(
    server: Server[Any], state: PresenceState, open_store: StoreOpener
) -> None:
    """Serve the resource's four methods on ``server``.

    Registering ``resources/subscribe`` is what makes the SDK declare
    ``resources: {subscribe: true}``.
    """
    resource = InboxResource(state, open_store)
    server.add_request_handler(
        "resources/list", types.PaginatedRequestParams, resource.list_resources
    )
    server.add_request_handler(
        "resources/read", types.ReadResourceRequestParams, resource.read_resource
    )
    server.add_request_handler(
        "resources/subscribe", types.SubscribeRequestParams, resource.subscribe
    )
    server.add_request_handler(
        "resources/unsubscribe", types.UnsubscribeRequestParams, resource.unsubscribe
    )


def initialization_options(server: Server[Any]) -> InitializationOptions:
    """The server's options with the channel capability, ``{}`` as Claude Code needs."""
    return server.create_initialization_options(
        experimental_capabilities={CHANNEL_CAPABILITY: {}}
    )
