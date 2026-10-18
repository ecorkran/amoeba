"""Submissions over HTTP: ``submit()`` with a required id, and the outcome lookup."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest
from cli_harness import run_cli
from httpx2 import Response
from inspection_harness import PROJECT, SeededStore
from local_host_harness import LocalHost
from serve_harness import ClientFactory, call_asgi

from amoeba.inbox import SubmissionWriteError, layout, pending, submit
from amoeba.process.inbox_tenant import InboxTenant
from amoeba.process.settings import ProcessSettings
from amoeba.serve import submissions
from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings
from amoeba.store import Store, SubmissionOutcome
from amoeba.store.inbox_models import INTENT_BODY, SubmissionKind

_SUBMISSIONS = f"/v1/projects/{PROJECT}/submissions"
_JSON = {"content-type": "application/json"}
#: An intent whose body is a list, refused by the envelope locally and remotely.
_BAD_BODY: list[object] = [1, 2]


def _intent(submission_id: str, body: object = None) -> dict[str, object]:
    return {
        "kind": SubmissionKind.INTENT.value,
        "submission_id": submission_id,
        "submitted_by": "remote",
        "payload": {INTENT_BODY: {"ask": "status"} if body is None else body},
    }


def _post(client_response: Response) -> tuple[int, dict[str, object]]:
    return client_response.status_code, client_response.json()


def _apply(scratch_dir: Path) -> None:
    """Drain the inbox once, in-process, through the real tenant."""
    host = LocalHost(scratch_dir, ProcessSettings())
    try:
        InboxTenant(scratch_dir).tick(host)
    finally:
        host.stores.close_all()


def _records(seeded: SeededStore, submission_id: str) -> int:
    with Store.open_read_only(seeded.store_file) as store:
        return sum(1 for r in store.submissions(PROJECT) if r.id == submission_id)


def _files_in_new(scratch_dir: Path) -> list[Path]:
    directory = layout.new_dir(scratch_dir)
    return sorted(directory.iterdir()) if directory.is_dir() else []


def test_a_valid_intent_is_accepted_and_written_once(
    scratch_dir: Path, seeded: SeededStore, make_client: ClientFactory
) -> None:
    before = len(_files_in_new(scratch_dir))
    client = make_client()

    first = client.post(_SUBMISSIONS, json=_intent("remote-1"))
    assert _post(first) == (202, {"submission_id": "remote-1"})
    assert len(_files_in_new(scratch_dir)) == before + 1

    second = client.post(_SUBMISSIONS, json=_intent("remote-1"))
    assert _post(second) == (202, {"submission_id": "remote-1"})
    _apply(scratch_dir)

    assert _records(seeded, "remote-1") == 1


def test_the_outcome_goes_from_not_applied_to_applied(
    scratch_dir: Path, seeded: SeededStore, make_client: ClientFactory
) -> None:
    client = make_client()
    client.post(_SUBMISSIONS, json=_intent("remote-2"))

    before = client.get(f"{_SUBMISSIONS}/remote-2")
    assert before.status_code == 404
    assert before.json()["error"] == "not_applied"

    _apply(scratch_dir)
    after = client.get(f"{_SUBMISSIONS}/remote-2")

    assert after.status_code == 200
    record = after.json()
    assert record["outcome"] == SubmissionOutcome.APPLIED.value
    assert set(record) == {
        "id",
        "kind",
        "outcome",
        "reason",
        "submitted_by",
        "submitted_at",
        "applied_seq",
    }


def test_create_project_before_its_store_exists_is_not_applied(
    scratch_dir: Path, make_client: ClientFactory
) -> None:
    client = make_client()
    body: dict[str, object] = {
        "kind": SubmissionKind.CREATE_PROJECT.value,
        "submission_id": "create-fresh",
        "submitted_by": "remote",
        "payload": {},
    }

    assert client.post("/v1/projects/fresh/submissions", json=body).status_code == 202
    response = client.get("/v1/projects/fresh/submissions/create-fresh")

    assert response.status_code == 404
    assert response.json()["error"] == "not_applied"


def test_an_invalid_payload_gets_the_reason_amoeba_submit_reports(
    scratch_dir: Path, seeded: SeededStore, make_client: ClientFactory
) -> None:
    before = _files_in_new(scratch_dir)
    cli = run_cli(
        [
            "submit",
            "intent",
            "--project",
            PROJECT,
            "--by",
            "pm",
            "--body",
            json.dumps(_BAD_BODY),
        ],
        scratch_dir,
    )
    assert cli.returncode != 0
    cli_reason = cli.stderr.removeprefix("amoeba: ").split(":", 1)[0]

    response = make_client().post(_SUBMISSIONS, json=_intent("bad-1", _BAD_BODY))

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_submission"
    assert response.json()["reason"] == cli_reason
    assert _files_in_new(scratch_dir) == before


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {k: v for k, v in _intent("x").items() if k != "submission_id"},
            "submission_id_required",
        ),
        ({**_intent("x"), "extra": 1}, "invalid_body"),
        (
            {k: v for k, v in _intent("x").items() if k != "submitted_by"},
            "invalid_body",
        ),
        ({**_intent("x"), "payload": "not an object"}, "invalid_body"),
        ({**_intent("x"), "kind": "no-such-kind"}, "invalid_body"),
        ({**_intent("x"), "submission_id": 7}, "invalid_body"),
    ],
)
def test_a_malformed_body_is_422(
    seeded: SeededStore, make_client: ClientFactory, body: dict[str, object], code: str
) -> None:
    response = make_client().post(_SUBMISSIONS, json=body)

    assert response.status_code == 422
    assert response.json()["error"] == code


@pytest.mark.parametrize("raw", [b"[1, 2]", b"{not json", b"\xff\xfe"])
def test_a_body_that_is_not_a_json_object_is_422(
    seeded: SeededStore, make_client: ClientFactory, raw: bytes
) -> None:
    response = make_client().post(_SUBMISSIONS, content=raw, headers=_JSON)

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_body"


def test_a_declared_length_over_the_cap_is_413(make_client: ClientFactory) -> None:
    client = make_client(settings=ServeSettings(max_request_bytes=100))

    response = client.post(_SUBMISSIONS, content=b"x" * 101, headers=_JSON)

    assert response.status_code == 413
    assert response.json()["error"] == "request_too_large"


def test_an_undeclared_body_stops_being_read_at_the_crossing_chunk(
    scratch_dir: Path,
) -> None:
    """Called as an ASGI app, so no client drains the body first."""
    chunk = 64 * 1024
    cap = 200 * 1024
    app = build_app(ServeSettings(max_request_bytes=cap), None, scratch_dir)

    exchange = anyio.run(
        lambda: call_asgi(app, "POST", _SUBMISSIONS, chunks=[b"x" * chunk] * 20)
    )

    assert exchange.status == 413
    assert json.loads(exchange.body)["error"] == "request_too_large"
    crossing = next(n for n in range(1, 21) if sum(exchange.chunk_sizes[:n]) > cap)
    assert exchange.receive_calls == crossing
    assert exchange.bytes_handed_out <= cap + chunk


def test_a_write_failure_is_503_and_a_retry_applies_once(
    scratch_dir: Path,
    seeded: SeededStore,
    make_client: ClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_once(**kwargs: object) -> str:
        calls.append(str(kwargs["submission_id"]))
        if len(calls) == 1:
            raise SubmissionWriteError("disk full")
        return submit(**kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(submissions, "submit", fail_once)
    client = make_client()

    failed = client.post(_SUBMISSIONS, json=_intent("retry-1"))
    assert failed.status_code == 503
    assert failed.json()["error"] == "submission_write_failed"

    assert client.post(_SUBMISSIONS, json=_intent("retry-1")).status_code == 202
    _apply(scratch_dir)

    assert _records(seeded, "retry-1") == 1


def _tree(root: Path) -> set[Path]:
    return set(root.rglob("*"))


@pytest.mark.parametrize("segment", [".", ".."])
@pytest.mark.parametrize("method", ["POST", "GET"])
def test_a_dot_project_segment_is_400_and_touches_nothing(
    tmp_path: Path,
    scratch_dir: Path,
    seeded: SeededStore,
    monkeypatch: pytest.MonkeyPatch,
    segment: str,
    method: str,
) -> None:
    touched: list[str] = []
    monkeypatch.setattr(submissions, "submit", lambda **kw: touched.append("submit"))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(Store, "open_read_only", lambda *a: touched.append("open"))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    before_files, before_pending = _tree(tmp_path), pending(scratch_dir)
    path = f"/v1/projects/{segment}/submissions"
    if method == "GET":
        path += "/s"
    app = build_app(ServeSettings(), None, scratch_dir)
    body = json.dumps(_intent("t")).encode()

    exchange = anyio.run(lambda: call_asgi(app, method, path, chunks=[body]))

    assert exchange.status == 400
    assert json.loads(exchange.body)["error"] == "invalid_project_id"
    assert touched == []
    assert _tree(tmp_path) == before_files
    assert pending(scratch_dir) == before_pending


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_an_encoded_slash_matches_no_route(
    scratch_dir: Path, make_client: ClientFactory, method: str
) -> None:
    """``a%2Fb`` is decoded before routing, so it never reaches a handler (404)."""
    path = "/v1/projects/a%2Fb/submissions" + ("/s" if method == "GET" else "")

    response = make_client().request(method, path, json=_intent("t"))

    assert response.status_code == 404
    assert pending(scratch_dir) == []


def test_text_plain_is_415_and_json_with_charset_is_accepted(
    seeded: SeededStore, make_client: ClientFactory
) -> None:
    client = make_client()
    body = json.dumps(_intent("charset-1")).encode()

    plain = client.post(
        _SUBMISSIONS, content=body, headers={"content-type": "text/plain"}
    )
    charset = client.post(
        _SUBMISSIONS,
        content=body,
        headers={"content-type": "application/json; charset=utf-8"},
    )

    assert plain.status_code == 415
    assert plain.json()["error"] == "unsupported_media_type"
    assert charset.status_code == 202
