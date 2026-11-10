"""``answering.yaml`` uses exactly the names of ``pipeline_file.py`` (slice 140)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from amoeba.answering import pipeline_resource
from amoeba.answering.artifacts import AnswerKind, Verdict
from amoeba.answering.passages import PassageKind
from amoeba.answering.pipeline_file import (
    ANSWER_MODEL_PARAM,
    ANSWER_PROMPT_FILE,
    ANSWER_REPLY_FILE,
    ANSWER_STEP,
    CHECK_MODEL_PARAM,
    CHECK_PROMPT_FILE,
    CHECK_REPLY_FILE,
    CHECK_STEP,
    NOT_AUTHORIZED_FILE,
    PASSAGES_FILE,
    PIPELINE_FILE_NAME,
    QUESTION_FILE,
    answering_pipeline_path,
)


def _load() -> dict[str, Any]:
    document: Any = yaml.safe_load(
        answering_pipeline_path().read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return cast("dict[str, Any]", document)


def _steps() -> dict[str, dict[str, Any]]:
    """Step name to its config; asserts each step is a one-key ``dispatch`` entry."""
    steps: dict[str, dict[str, Any]] = {}
    for entry in _load()["steps"]:
        assert list(entry) == ["dispatch"]
        steps[entry["dispatch"]["name"]] = entry["dispatch"]
    return steps


def test_step_names_and_order() -> None:
    assert list(_steps()) == [ANSWER_STEP, CHECK_STEP]


def test_params_are_required_with_no_default() -> None:
    assert _load()["params"] == {
        ANSWER_MODEL_PARAM: "required",
        CHECK_MODEL_PARAM: "required",
    }


def test_models_come_from_the_params() -> None:
    steps = _steps()
    assert steps[ANSWER_STEP]["model"] == "{" + ANSWER_MODEL_PARAM + "}"
    assert steps[CHECK_STEP]["model"] == "{" + CHECK_MODEL_PARAM + "}"


def test_reply_and_prompt_files() -> None:
    steps = _steps()
    assert steps[ANSWER_STEP]["reply_file"] == ANSWER_REPLY_FILE
    assert steps[ANSWER_STEP]["delivered_prompt_file"] == ANSWER_PROMPT_FILE
    assert steps[CHECK_STEP]["reply_file"] == CHECK_REPLY_FILE
    assert steps[CHECK_STEP]["delivered_prompt_file"] == CHECK_PROMPT_FILE


def test_prompt_files_and_reply_chaining() -> None:
    steps = _steps()
    both = [QUESTION_FILE, PASSAGES_FILE, NOT_AUTHORIZED_FILE]
    assert steps[ANSWER_STEP]["prompt_files"] == both
    assert steps[CHECK_STEP]["prompt_files"] == both
    assert steps[CHECK_STEP]["reply_from"] == ANSWER_STEP
    assert "reply_from" not in steps[ANSWER_STEP]


def test_no_tools_and_json_reply() -> None:
    for step in _steps().values():
        assert step["allowed_tools"] == []
        assert step["reply_format"] == "json"


def test_prompts_name_the_parser_vocabulary() -> None:
    steps = _steps()
    answer_prompt = steps[ANSWER_STEP]["prompt"]
    check_prompt = steps[CHECK_STEP]["prompt"]
    assert answer_prompt.strip()
    assert check_prompt.strip()
    for kind in AnswerKind:
        assert f'"{kind.value}"' in answer_prompt
    for verdict in Verdict:
        assert f'"{verdict.value}"' in check_prompt
    assert '"verdict"' in check_prompt


def test_pipeline_name_matches_file_stem() -> None:
    assert _load()["name"] == Path(PIPELINE_FILE_NAME).stem


def test_path_resolves_to_an_existing_file() -> None:
    path = answering_pipeline_path()
    assert path.is_absolute()
    assert path.is_file()
    assert path.name == PIPELINE_FILE_NAME


def test_missing_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    def package_root(_package: str) -> Path:
        return tmp_path

    monkeypatch.setattr(pipeline_resource.resources, "files", package_root)
    with pytest.raises(FileNotFoundError, match=PIPELINE_FILE_NAME):
        answering_pipeline_path()


#: The items the prompts used to hard-code; the list is now ``not_authorized.md``.
OLD_AUTHORIZE_LIST = ("a push", "a merge to main", "a release", "a destructive")


def test_prompts_hold_no_hard_coded_authorize_list() -> None:
    for step in _steps().values():
        prompt = " ".join(step["prompt"].split())
        for old_item in OLD_AUTHORIZE_LIST:
            assert old_item not in prompt


def test_both_prompts_point_at_the_not_authorized_list_after_the_passages() -> None:
    for step in _steps().values():
        prompt = " ".join(step["prompt"].split())
        assert "not-authorized list that follows the passages" in prompt


#: The sentences both steps carry about the passage kinds (slice 182, D8).
KIND_SENTENCES = (
    "The kinds are rule, plan, pm_answer, program_concept or program_members. "
    "A program_concept passage comes from the concept document of the program "
    "this project belongs to, held in the member project its member line names; "
    "it describes how the program's projects fit together and what each one is "
    "for. A program_members passage lists the program's projects and marks the "
    "one the question comes from."
)


def test_both_steps_name_every_passage_kind_with_the_same_sentences() -> None:
    for step in _steps().values():
        prompt = " ".join(step["prompt"].split())
        assert KIND_SENTENCES in prompt
        for kind in PassageKind:
            assert kind.value in prompt


def test_the_kind_sentences_name_the_kinds_by_their_enum_values() -> None:
    listed = KIND_SENTENCES.split(".")[0].removeprefix("The kinds are ")
    names = listed.replace(" or ", ", ").split(", ")
    assert names == [kind.value for kind in PassageKind]
