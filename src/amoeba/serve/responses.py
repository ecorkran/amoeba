"""What every route and the request guard share: the JSON media type and body."""

from __future__ import annotations

import json
from typing import Final

from starlette.responses import Response

#: The media type of every JSON body, sent or accepted.
JSON_MEDIA_TYPE: Final = "application/json"


def json_response(body: object, status_code: int) -> Response:
    """A JSON response serialized as the CLI does (``default=str``)."""
    return Response(
        json.dumps(body, default=str),
        status_code=status_code,
        media_type=JSON_MEDIA_TYPE,
    )
