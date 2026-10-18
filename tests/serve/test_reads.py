"""``GET /v1/listings/{name}``: parity with ``amoeba inspect --json``, and refusals."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from cli_harness import run_cli
from evidence_harness import provider_failure
from inspection_harness import PROJECT, SeededStore
from serve_harness import ClientFactory

from amoeba.inspection import (
    LISTINGS,
    LISTINGS_BY_NAME,
    ChoiceOption,
    ListingScope,
    ValueOption,
)
from amoeba.serve import reads
from amoeba.store import Channel, DetectionOutcome, Store, StoreBusyError, sql
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION

#: (case id, listing name, CLI arguments after the listing name, query string)
type ParityCase = tuple[str, str, list[str], dict[str, str]]


def _seeded_value(option: ValueOption, seeded: SeededStore) -> str:
    """The seeded id a value option names."""
    by_name = {
        "node": seeded.node_id,
        "judge_invocation_id": seeded.judge_invocation_id,
        "verdict": seeded.verdict_id,
    }
    return by_name[option.name]


def _seeded_choice(option: ChoiceOption) -> str:
    """The choice the seeded store has a row for, so the filtered read is not empty."""
    by_name = {
        "channel": Channel.INTENT.value,
        "outcome": DetectionOutcome.UNPARSEABLE.value,
    }
    return by_name[option.name]


def _parity_cases(seeded: SeededStore) -> list[ParityCase]:
    """Every listing once, then every declared option once, from the registry."""
    cases: list[ParityCase] = []
    for listing in LISTINGS:
        cli: list[str] = []
        query: dict[str, str] = {}
        if listing.scope is ListingScope.PROJECT:
            cli += ["--project", seeded.project_id]
            query[reads.PROJECT_PARAMETER] = seeded.project_id
        for option in listing.value_options:
            if option.required:
                cli += [option.flag, _seeded_value(option, seeded)]
                query[option.name] = _seeded_value(option, seeded)
        cases.append((listing.name, listing.name, cli, query))
        for flag in listing.flags:
            cases.append(
                (
                    f"{listing.name}:{flag.name}",
                    listing.name,
                    [*cli, flag.flag],
                    {**query, flag.name: "true"},
                )
            )
        for choice in listing.choice_options:
            value = _seeded_choice(choice)
            cases.append(
                (
                    f"{listing.name}:{choice.name}",
                    listing.name,
                    [*cli, choice.flag, value],
                    {**query, choice.name: value},
                )
            )
        for option in listing.value_options:
            if not option.required:
                value = _seeded_value(option, seeded)
                cases.append(
                    (
                        f"{listing.name}:{option.name}",
                        listing.name,
                        [*cli, option.flag, value],
                        {**query, option.name: value},
                    )
                )
    return cases


def test_rows_equal_inspect_json_for_every_listing_and_option(
    scratch_dir: Path, seeded: SeededStore, make_client: ClientFactory
) -> None:
    """One test, so the store is seeded once and every case reads the same rows."""
    client = make_client()
    cases = _parity_cases(seeded)
    covered = {name for _, name, _, _ in cases}
    assert covered == {listing.name for listing in LISTINGS}

    for case_id, name, cli, query in cases:
        expected = json.loads(
            run_cli(["inspect", name, *cli, "--json"], scratch_dir).stdout
        )
        response = client.get(f"/v1/listings/{name}", params=query)
        assert response.status_code == 200, (case_id, response.text)
        assert response.json()["rows"] == expected, case_id
        assert expected, f"{case_id} returned no rows; parity would be vacuous"


def test_project_listings_report_the_feed_head(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    with Store.open_read_only(seeded.store_file) as store:
        head = store.change_head(PROJECT)

    body = make_client().get("/v1/listings/nodes", params={"project": PROJECT}).json()

    assert body["listing"] == "nodes"
    assert body["project_id"] == PROJECT
    assert body["as_of_seq"] == head


@pytest.mark.parametrize(
    "name",
    [
        n
        for n, listing in LISTINGS_BY_NAME.items()
        if listing.scope is ListingScope.SUPERVISOR
    ],
)
def test_supervisor_listings_carry_no_project_or_seq(
    seeded: SeededStore, make_client: ClientFactory, name: str
) -> None:
    body = make_client().get(f"/v1/listings/{name}").json()

    assert set(body) == {"listing", "rows"}


def _error(response_json: object) -> str:
    assert isinstance(response_json, dict)
    return str(response_json["error"])  # pyright: ignore[reportUnknownArgumentType]


@pytest.mark.parametrize(
    ("path", "params", "status", "code"),
    [
        ("not-a-listing", {"project": PROJECT}, 404, "unknown_listing"),
        ("nodes", {}, 400, "missing_project"),
        ("projects", {"project": PROJECT}, 400, "unexpected_parameter"),
        ("nodes", {"project": PROJECT, "colour": "red"}, 400, "unexpected_parameter"),
        ("journal", {"project": PROJECT, "unresolved": "yes"}, 400, "invalid_option"),
        ("messages", {"project": PROJECT, "channel": "nope"}, 400, "invalid_option"),
        ("changes", {"project": PROJECT}, 400, "invalid_option"),
        ("nodes", {"project": "never-existed"}, 404, "unknown_project"),
        (
            "changes",
            {"project": PROJECT, "verdict": "no-such-verdict"},
            404,
            "not_found",
        ),
    ],
)
def test_refusals(
    seeded: SeededStore,
    make_client: ClientFactory,
    path: str,
    params: dict[str, str],
    status: int,
    code: str,
) -> None:
    response = make_client().get(f"/v1/listings/{path}", params=params)

    assert response.status_code == status, response.text
    assert _error(response.json()) == code
    assert set(response.json()) == {"error", "detail"}


def test_a_repeated_parameter_is_refused(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    response = make_client().get(
        "/v1/listings/nodes", params=[("project", PROJECT), ("project", PROJECT)]
    )

    assert response.status_code == 400
    assert _error(response.json()) == "invalid_option"


def test_a_flag_set_false_is_the_flag_unset(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    client = make_client()
    unset = client.get("/v1/listings/journal", params={"project": PROJECT})
    false = client.get(
        "/v1/listings/journal", params={"project": PROJECT, "unresolved": "false"}
    )

    assert false.json()["rows"] == unset.json()["rows"]


def test_a_non_comparable_verdict_is_422(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    with Store.open(seeded.store_file) as store:
        store.record_verdict(
            provider_failure("fixture-failed", seeded.node_id), project_id=PROJECT
        )

    response = make_client().get(
        "/v1/listings/changes", params={"project": PROJECT, "verdict": "fixture-failed"}
    )

    assert response.status_code == 422
    assert _error(response.json()) == "not_comparable"


@pytest.mark.parametrize("project", ["../x", "a/b", ".", ".."])
def test_a_traversal_project_id_is_refused_before_any_open(
    seeded: SeededStore,
    make_client: ClientFactory,
    monkeypatch: pytest.MonkeyPatch,
    project: str,
) -> None:
    opened: list[object] = []

    def record_open(*args: object, **kwargs: object) -> None:
        opened.append(args)

    monkeypatch.setattr(Store, "open_read_only", record_open)

    response = make_client().get("/v1/listings/nodes", params={"project": project})

    assert response.status_code == 400
    assert _error(response.json()) == "invalid_project_id"
    assert opened == []


def test_a_store_at_another_schema_version_is_503(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    connection = sqlite3.connect(seeded.store_file)
    try:
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_SCHEMA_VERSION + 1),
        )
        connection.commit()
    finally:
        connection.close()

    response = make_client().get("/v1/listings/nodes", params={"project": PROJECT})

    assert response.status_code == 503
    assert _error(response.json()) == "store_schema_mismatch"


def test_a_file_that_is_not_sqlite_is_503_unreadable(
    scratch_dir: Path, make_client: ClientFactory
) -> None:
    (scratch_dir / f"{PROJECT}.sqlite3").write_bytes(b"not a database" * 100)

    response = make_client().get("/v1/listings/nodes", params={"project": PROJECT})

    assert response.status_code == 503
    assert _error(response.json()) == "store_unreadable"


def test_a_busy_store_is_503_with_retry_after(
    seeded: SeededStore, make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    def busy(*args: object) -> None:
        raise StoreBusyError("database is locked")

    monkeypatch.setattr(reads, "read_listing", busy)

    response = make_client().get("/v1/listings/nodes", params={"project": PROJECT})

    assert response.status_code == 503
    assert _error(response.json()) == "store_busy"
    assert "retry-after" in response.headers
