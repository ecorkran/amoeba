"""``AddRequest`` and the ``SetUpRequest`` it builds (slice 229, D4, task 5.2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from user_configs import user_config

from amoeba.operations.add import AddRequest, single_member_request
from amoeba.operations.set_up_models import SetUpRequest
from amoeba.store.vocabulary import ConsumedMode

CONFIG = user_config()


def _built(**fields: Any) -> SetUpRequest:
    request = AddRequest.model_validate(fields)
    return single_member_request(request, CONFIG, "demo")


def _only_member(built: SetUpRequest) -> Any:
    assert len(built.members) == 1
    return built.members[0]


def test_a_bare_request_builds_a_member_with_nothing_given() -> None:
    built = _built()

    member = _only_member(built)
    assert built.program == "demo"
    assert member.project is None
    assert member.model_fields_set <= {"project", "depends_on"}
    assert member.rules_paths is None
    assert member.authorize_allow is None
    assert member.authorize_deny is None
    assert "concept" not in built.model_fields_set


def test_each_single_member_field_reaches_the_set_up_request() -> None:
    built = _built(
        project="other-repo",
        rules_paths=["CLAUDE.md", "docs/*.md"],
        authorize_allow=["push"],
        authorize_deny=["deploy"],
        depends_on=[{"provider": "lib", "consumed": "from_release"}],
        concept={"member": "me", "path": "docs/concept.md"},
    )

    member = _only_member(built)
    assert member.project == "other-repo"
    assert member.rules_paths == ("CLAUDE.md", "docs/*.md")
    assert member.authorize_allow == ("push",)
    assert member.authorize_deny == ("deploy",)
    assert [(d.provider, d.consumed) for d in member.depends_on] == [
        ("lib", ConsumedMode.FROM_RELEASE)
    ]
    assert built.concept is not None
    assert (built.concept.member, built.concept.path) == ("me", "docs/concept.md")


def test_rules_default_reaches_the_member() -> None:
    assert _only_member(_built(rules_default=True)).rules_default is True


@pytest.mark.parametrize("field", ["rules_paths", "authorize_allow", "authorize_deny"])
def test_an_empty_list_reaches_the_member_as_the_empty_list(field: str) -> None:
    member = _only_member(_built(**{field: []}))

    assert getattr(member, field) == ()
    assert field in member.model_fields_set


@pytest.mark.parametrize("field", ["rules_paths", "authorize_allow", "authorize_deny"])
def test_an_omitted_list_stays_omitted_on_the_member(field: str) -> None:
    member = _only_member(_built())

    assert getattr(member, field) is None
    assert field not in member.model_fields_set


def test_a_null_concept_is_given_and_clears_it() -> None:
    built = _built(concept=None)

    assert "concept" in built.model_fields_set
    assert built.concept is None


def test_a_dependency_without_a_mode_takes_the_configs_default() -> None:
    config = CONFIG.model_copy(update={"default_consumed": ConsumedMode.FROM_RELEASE})
    request = AddRequest.model_validate({"depends_on": [{"provider": "lib"}]})

    member = _only_member(single_member_request(request, config, "demo"))

    assert member.depends_on[0].consumed is ConsumedMode.FROM_RELEASE


def test_a_dependency_with_a_mode_keeps_it() -> None:
    config = CONFIG.model_copy(update={"default_consumed": ConsumedMode.FROM_RELEASE})
    request = AddRequest.model_validate(
        {"depends_on": [{"provider": "lib", "consumed": "from_source"}]}
    )

    member = _only_member(single_member_request(request, config, "demo"))

    assert member.depends_on[0].consumed is ConsumedMode.FROM_SOURCE


def test_bulk_passes_through_as_given() -> None:
    document: dict[str, Any] = {
        "program": "demo",
        "members": [{"project": "a", "rules_paths": []}],
    }

    request = AddRequest.model_validate({"bulk": document})

    assert request.bulk == SetUpRequest.model_validate(document)
    assert request.bulk is not None
    assert request.bulk.model_fields_set == {"program", "members"}


@pytest.mark.parametrize(
    "single",
    [
        {"program": "demo"},
        {"project": "x"},
        {"rules_paths": []},
        {"rules_default": False},
        {"authorize_allow": []},
        {"depends_on": []},
        {"concept": None},
    ],
)
def test_bulk_with_any_single_member_field_is_malformed(single: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="bulk cannot be combined with"):
        AddRequest.model_validate({"bulk": {"program": "demo"}, **single})


def test_a_dependency_mode_outside_the_vocabulary_is_malformed() -> None:
    with pytest.raises(ValidationError):
        AddRequest.model_validate({"depends_on": [{"provider": "x", "consumed": "?"}]})
