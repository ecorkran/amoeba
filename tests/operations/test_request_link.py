"""``find_request_link`` on the shapes Squadron reports (slice 242, D1, 2.2)."""

from __future__ import annotations

import pytest

from amoeba.operations.request_link import (
    BadLink,
    Link,
    LinkResult,
    NoLink,
    find_request_link,
)

#: Requests the question's member sent; anything else does not resolve.
OWN_REQUESTS = frozenset({"guide-change", "v1.2.", "other-one"})
#: A request another member sent, and a note: the resolver says no to both.
FOREIGN_REQUEST = "theirs-1"
NOTE_ID = "note-1"


def _link(question: str) -> LinkResult:
    return find_request_link(question, OWN_REQUESTS.__contains__)


def test_a_question_ending_with_the_marker_line_links() -> None:
    question = "Can I go on with the hook?\namoeba-request: guide-change"

    assert _link(question) == Link("guide-change")


def test_a_question_cut_by_squadron_still_links() -> None:
    """Squadron's question is the reply's tail with lines joined by spaces."""
    question = "…filler. What is the limit now? amoeba-request: guide-change"

    assert _link(question) == Link("guide-change")


def test_a_sentence_ending_dot_is_dropped_and_an_id_ending_in_dot_kept() -> None:
    assert _link("See amoeba-request: guide-change.") == Link("guide-change")
    assert _link("See amoeba-request: v1.2.") == Link("v1.2.")


@pytest.mark.parametrize(
    "marker",
    [
        "amoeba-request: 'guide-change'",
        'amoeba-request: "guide-change"',
        "amoeba-request: [guide-change]",
        "amoeba-request: `guide-change`",
        "amoeba-request: <guide-change>",
        "AMOEBA-REQUEST: guide-change",
        "Amoeba-Request:guide-change",
        "amoeba_request=guide-change",
        "amoeba request: guide-change",
        "amoeba-request : guide-change",
    ],
)
def test_marker_variations_link(marker: str) -> None:
    assert _link(f"Is it in?\n{marker}") == Link("guide-change")


def test_the_same_id_twice_is_one_link() -> None:
    question = "amoeba-request: guide-change\nagain amoeba-request: guide-change"

    assert _link(question) == Link("guide-change")


def test_two_different_resolved_ids_are_a_bad_link() -> None:
    result = _link("amoeba-request: guide-change and amoeba-request: other-one")

    assert isinstance(result, BadLink)
    assert "guide-change" in result.detail
    assert "other-one" in result.detail


@pytest.mark.parametrize("named", ["no-such-request", FOREIGN_REQUEST, NOTE_ID])
def test_a_marker_that_does_not_resolve_is_a_bad_link(named: str) -> None:
    result = _link(f"Done yet?\namoeba-request: {named}")

    assert isinstance(result, BadLink)
    assert named in result.detail


def test_a_marker_with_no_id_is_a_bad_link() -> None:
    assert isinstance(_link("Done yet?\namoeba-request:"), BadLink)


@pytest.mark.parametrize(
    "question",
    [
        "What is the maximum file length?",
        "Is the guide-change request done yet?",
        "I am waiting for the request about the guide change.",
    ],
)
def test_no_marker_is_no_link(question: str) -> None:
    assert _link(question) == NoLink()


def test_one_marker_whose_two_spellings_both_resolve_is_one_link() -> None:
    both = OWN_REQUESTS | {"v1.2"}

    assert find_request_link("amoeba-request: v1.2.", both.__contains__) == Link(
        "v1.2."
    )
