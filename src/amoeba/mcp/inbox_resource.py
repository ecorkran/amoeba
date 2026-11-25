"""The ``amoeba://inbox`` resource and the capabilities push declares (slice 241, D3,
D5).

Every handler first waits for presence to resolve (the first tick ends), so none
answers from the pending state; only that request waits. Then it answers from memory,
from the newest tick reply (263 D10): ``read`` returns the member and the number
``inbox`` reports as ``as_of_seq``, never message text, and makes no store read and no
hub call. ``subscribe`` and ``unsubscribe`` set and clear a flag on the event loop,
which the tick reads before sending a resource update. Capabilities are fixed at
``initialize``, before the member is known, so every server declares both the channel
and the subscribable resources, and lists the resource whether or not it has a
member.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import MCPError

from amoeba.mcp.channel_event import CHANNEL_CAPABILITY
from amoeba.mcp.presence import PresenceState

#: The one resource this server offers.
INBOX_URI: Final = "amoeba://inbox"
INBOX_NAME: Final = "inbox"
INBOX_MIME_TYPE: Final = "application/json"
#: Sent after a channel event to a client that subscribed to ``INBOX_URI``.
RESOURCE_UPDATED_METHOD: Final = "notifications/resources/updated"
#: The resource document's keys.
MEMBER_FIELD: Final = "member"
AS_OF_SEQ_FIELD: Final = "as_of_seq"


@dataclass(frozen=True)
class InboxResource:
    """The four handlers, over the server's presence."""

    state: PresenceState

    async def _member(self, uri: str) -> tuple[str, int]:
        """The member and ``as_of_seq`` of the newest tick reply, for a request about
        ``INBOX_URI`` (D10's table).

        Raises:
            MCPError: Internal error naming the tick's last error before any reply;
                invalid-params for no member or another resource.
        """
        await self.state.resolved.wait()
        member, as_of_seq = self.state.member_id, self.state.as_of_seq
        if as_of_seq is None:
            raise MCPError(
                types.INTERNAL_ERROR,
                self.state.last_error or "no tick has had a reply yet",
            )
        if member is None:
            raise MCPError(types.INVALID_PARAMS, "this server serves no member")
        if uri != INBOX_URI:
            raise MCPError(types.INVALID_PARAMS, f"unknown resource {uri!r}")
        return member, as_of_seq

    async def list_resources(
        self,
        ctx: ServerRequestContext[Any],
        params: types.PaginatedRequestParams | None,
    ) -> types.ListResourcesResult:
        resource = types.Resource(
            name=INBOX_NAME, uri=INBOX_URI, mime_type=INBOX_MIME_TYPE
        )
        return types.ListResourcesResult(resources=[resource])

    async def read_resource(
        self, ctx: ServerRequestContext[Any], params: types.ReadResourceRequestParams
    ) -> types.ReadResourceResult:
        member, as_of_seq = await self._member(str(params.uri))
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


def register_inbox_resource(server: Server[Any], state: PresenceState) -> None:
    """Serve the resource's four methods on ``server``.

    Registering ``resources/subscribe`` is what makes the SDK declare
    ``resources: {subscribe: true}``.
    """
    resource = InboxResource(state)
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
