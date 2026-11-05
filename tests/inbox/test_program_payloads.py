"""Program payload models: valid bodies, each refusal naming its field, the pin."""

from __future__ import annotations

import copy

import pytest
from program_harness import member, member_payload, program_payload
from pydantic import BaseModel, ValidationError

from amoeba.inbox.program_payloads import (
    PROGRAM_KIND_PAYLOAD_MODELS,
    MemberPayload,
    RegisterMemberPayload,
    RegisterProgramPayload,
)
from amoeba.store import program_models
from amoeba.store.program_models import ProgramSubmissionKind


def _fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


def _refusal(model: type[BaseModel], body: dict[str, object]) -> str:
    with pytest.raises(ValidationError) as caught:
        model.model_validate(body)
    return str(caught.value)


def test_a_valid_body_of_each_kind_is_accepted() -> None:
    RegisterProgramPayload.model_validate(program_payload())
    RegisterMemberPayload.model_validate(
        member_payload(member("ui", overrides={"data": "from_release"}))
    )


def test_every_kind_has_a_payload_model() -> None:
    assert set(PROGRAM_KIND_PAYLOAD_MODELS) == set(ProgramSubmissionKind)


def test_the_field_name_constants_match_the_models() -> None:
    assert _fields(RegisterProgramPayload) == {
        program_models.PROGRAM_ID,
        program_models.CONCEPT_MEMBER,
        program_models.CONCEPT_PATH,
        program_models.MEMBERS,
    }
    assert _fields(RegisterMemberPayload) == {
        program_models.PROGRAM_ID,
        program_models.MEMBER,
    }
    assert _fields(MemberPayload) == {
        program_models.MEMBER_PROJECT_ID,
        program_models.MEMBER_REQUESTS_INITIATIVE,
        program_models.MEMBER_CONSUMED,
        program_models.MEMBER_OVERRIDES,
    }


@pytest.mark.parametrize("missing", ["concept_member", "concept_path", "members"])
def test_a_missing_program_field_is_named(missing: str) -> None:
    body = program_payload()
    del body[missing]

    assert missing in _refusal(RegisterProgramPayload, body)


@pytest.mark.parametrize("missing", ["requests_initiative", "consumed", "overrides"])
def test_a_missing_member_field_is_named(missing: str) -> None:
    body = member(  # a full member, then one key removed
        "ui"
    )
    del body[missing]

    assert missing in _refusal(RegisterMemberPayload, member_payload(body))


@pytest.mark.parametrize("bad_index", [99, 800, True, "790", 790.0, None])
def test_a_bad_requests_initiative_is_refused_naming_the_field(
    bad_index: object,
) -> None:
    body = member("ui")
    body["requests_initiative"] = bad_index

    assert "requests_initiative" in _refusal(
        RegisterMemberPayload, member_payload(body)
    )


@pytest.mark.parametrize("good_index", [100, 790, 799])
def test_the_initiative_range_bounds_are_inclusive(good_index: int) -> None:
    RegisterMemberPayload.model_validate(
        member_payload(member("ui", initiative=good_index))
    )


def test_an_unknown_mode_is_refused_naming_the_field() -> None:
    assert "consumed" in _refusal(
        RegisterMemberPayload, member_payload(member("ui", consumed="from_nowhere"))
    )


def test_an_unknown_override_mode_is_refused() -> None:
    assert "overrides" in _refusal(
        RegisterMemberPayload,
        member_payload(member("ui", overrides={"data": "sideways"})),
    )


def test_a_self_override_is_refused_naming_the_field() -> None:
    message = _refusal(
        RegisterMemberPayload,
        member_payload(member("ui", overrides={"ui": "from_release"})),
    )

    assert "overrides" in message
    assert "the member itself" in message


def test_a_duplicate_member_is_refused_naming_the_field() -> None:
    message = _refusal(
        RegisterProgramPayload,
        program_payload(members=[member("data"), member("data")]),
    )

    assert "members" in message
    assert "data" in message


def test_empty_members_are_refused() -> None:
    assert "members" in _refusal(RegisterProgramPayload, program_payload(members=[]))


def test_an_unknown_key_is_refused_unlike_the_project_envelope() -> None:
    body = copy.deepcopy(program_payload())
    body["concept_pth"] = "docs/typo.md"

    assert "concept_pth" in _refusal(RegisterProgramPayload, body)


def test_an_unknown_member_key_is_refused() -> None:
    body = member("ui")
    body["requests_initative"] = 790

    assert "requests_initative" in _refusal(RegisterMemberPayload, member_payload(body))


def test_wrong_kind_fields_are_refused() -> None:
    body = program_payload()
    body["member"] = member("ui")

    assert "member" in _refusal(RegisterProgramPayload, body)
    assert "members" in _refusal(
        RegisterMemberPayload, {**member_payload(member("ui")), "members": []}
    )


@pytest.mark.parametrize(
    "bad_path",
    ["/abs/c.md", "docs/../c.md", "docs/", "docs/*.md", "   ", ""],
)
def test_a_bad_concept_path_is_refused_naming_the_field(bad_path: str) -> None:
    assert "concept_path" in _refusal(
        RegisterProgramPayload, program_payload(concept_path=bad_path)
    )


def test_a_concept_path_is_stripped() -> None:
    parsed = RegisterProgramPayload.model_validate(
        program_payload(concept_path="  docs/c.md  ")
    )

    assert parsed.concept_path == "docs/c.md"


@pytest.mark.parametrize("bad_id", ["", "a/b", ".", ".."])
def test_unusable_ids_are_refused(bad_id: str) -> None:
    assert "program_id" in _refusal(
        RegisterProgramPayload, program_payload(program_id=bad_id)
    )
    assert "project_id" in _refusal(
        RegisterMemberPayload, member_payload(member(bad_id))
    )
    assert "concept_member" in _refusal(
        RegisterProgramPayload, program_payload(concept_member=bad_id)
    )
