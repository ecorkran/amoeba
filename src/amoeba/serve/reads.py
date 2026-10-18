"""``GET /v1/listings/{name}``: every listing in the one registry (LLD D4).

The query string is checked against the listing's declared options, so an
undeclared parameter is refused rather than ignored. Rows come from the same
``read_listing`` the CLI calls, with ``compact=False`` as ``--json`` sets it.
No store or filesystem call runs on the event loop.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Final

import anyio.to_thread
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from amoeba.inspection import (
    LISTINGS_BY_NAME,
    ChoiceOption,
    FlagOption,
    Listing,
    ListingRequest,
    ListingResult,
    ListingScope,
    OptionValue,
    ValueOption,
    read_listing,
)
from amoeba.serve.errors import ApiError, ApiErrorCode
from amoeba.store import paths

#: The query parameter naming the project, for a project-scoped listing.
PROJECT_PARAMETER: Final = "project"

#: The values a flag option accepts in a query string.
FLAG_VALUES: Final = {"true": True, "false": False}

#: The response media type for every JSON body this module writes.
JSON_MEDIA_TYPE: Final = "application/json"


def validated_project_id(value: str) -> str:
    """``value`` if it passes 103's id rule, else ``invalid_project_id``."""
    try:
        paths.validate_project_id(value)
    except ValueError as error:
        # Specific: the id rule's refusal is the client's error, not ours.
        raise ApiError(ApiErrorCode.INVALID_PROJECT_ID, str(error)) from error
    return value


def existing_store_path(store_dir: Path, project_id: str) -> Path:
    """The project's store file, or ``unknown_project`` if there is none.

    Blocking: call it on a worker thread.
    """
    path = paths.project_store_path(store_dir, project_id)
    if not path.is_file():
        raise ApiError(ApiErrorCode.UNKNOWN_PROJECT, f"no project {project_id!r}")
    return path


def listing_request(
    listing: Listing, query: Sequence[tuple[str, str]]
) -> ListingRequest:
    """The request a query string describes, checked against ``listing``.

    Raises:
        ApiError: ``missing_project``, ``unexpected_parameter``,
            ``invalid_option``, or ``invalid_project_id``.
    """
    repeated = sorted(
        key for key, count in Counter(k for k, _ in query).items() if count > 1
    )
    if repeated:
        raise ApiError(ApiErrorCode.INVALID_OPTION, f"repeated parameters: {repeated}")
    values = dict(query)
    project_id = _project_id(listing, values.pop(PROJECT_PARAMETER, None))
    declared = {
        option.name: option
        for option in (*listing.flags, *listing.choice_options, *listing.value_options)
    }
    undeclared = sorted(set(values) - set(declared))
    if undeclared:
        raise ApiError(
            ApiErrorCode.UNEXPECTED_PARAMETER,
            f"listing {listing.name!r} takes no {undeclared}",
        )
    options = {
        name: _option_value(option, values.get(name))
        for name, option in declared.items()
    }
    return ListingRequest(project_id=project_id, options=options, compact=False)


def _project_id(listing: Listing, value: str | None) -> str | None:
    if listing.scope is ListingScope.SUPERVISOR:
        if value is not None:
            raise ApiError(
                ApiErrorCode.UNEXPECTED_PARAMETER,
                f"listing {listing.name!r} is not project-scoped",
            )
        return None
    if value is None:
        raise ApiError(
            ApiErrorCode.MISSING_PROJECT, f"listing {listing.name!r} needs a project"
        )
    return validated_project_id(value)


def _option_value(
    option: FlagOption | ChoiceOption | ValueOption, value: str | None
) -> OptionValue:
    match option:
        case FlagOption():
            if value is None:
                return False
            if value not in FLAG_VALUES:
                raise ApiError(
                    ApiErrorCode.INVALID_OPTION,
                    f"{option.name} takes {sorted(FLAG_VALUES)}, got {value!r}",
                )
            return FLAG_VALUES[value]
        case ChoiceOption():
            if value is not None and value not in option.choices:
                raise ApiError(
                    ApiErrorCode.INVALID_OPTION,
                    f"{option.name} takes {list(option.choices)}, got {value!r}",
                )
            return value
        case ValueOption():
            if value is None and option.required:
                raise ApiError(
                    ApiErrorCode.INVALID_OPTION, f"{option.name} is required"
                )
            return value


def _read(store_dir: Path, name: str, request: ListingRequest) -> ListingResult:
    """Blocking: the existence check and the read, on a worker thread."""
    if request.project_id is not None:
        existing_store_path(store_dir, request.project_id)
    return read_listing(name, request, store_dir)


def json_response(body: object, status_code: int) -> Response:
    """A JSON response serialized as the CLI does (``default=str``)."""
    return Response(
        json.dumps(body, default=str),
        status_code=status_code,
        media_type=JSON_MEDIA_TYPE,
    )


def routes(store_dir: Path) -> list[Route]:
    """The reads route, closed over the supervisor directory."""

    async def read(request: Request) -> Response:
        name = str(request.path_params["name"])
        listing = LISTINGS_BY_NAME.get(name)
        if listing is None:
            raise ApiError(ApiErrorCode.UNKNOWN_LISTING, f"no listing named {name!r}")
        listing_req = listing_request(listing, request.query_params.multi_items())
        result = await anyio.to_thread.run_sync(
            partial(_read, store_dir, name, listing_req)
        )
        body: dict[str, object] = {"listing": name}
        if listing.scope is ListingScope.PROJECT:
            body["project_id"] = listing_req.project_id
            body["as_of_seq"] = result.as_of_seq
        body["rows"] = result.rows
        return json_response(body, HTTPStatus.OK)

    return [Route("/v1/listings/{name}", read, methods=["GET"])]
