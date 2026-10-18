"""``read_listing``: rows and ``as_of_seq`` come from one read snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest
from inspection_harness import PROJECT, SeededStore, seed_every_listing

from amoeba.inspection import (
    LISTINGS_BY_NAME,
    PROJECTS_LISTING,
    ListingRequest,
    ListingScope,
    read_listing,
)
from amoeba.inspection.inbox import CHANNEL_OPTION
from amoeba.store import Channel, Message, Store

_MESSAGES = "messages"


@pytest.fixture
def seeded(supervisor_dir: Path) -> SeededStore:
    return seed_every_listing(supervisor_dir)


def _every_channel() -> ListingRequest:
    return ListingRequest(
        project_id=PROJECT, options={CHANNEL_OPTION.name: None}, compact=False
    )


def _head(seeded: SeededStore) -> int:
    with Store.open_read_only(seeded.store_file) as store:
        return store.change_head(PROJECT)


def test_as_of_seq_is_the_feed_head(supervisor_dir: Path, seeded: SeededStore) -> None:
    result = read_listing(_MESSAGES, _every_channel(), supervisor_dir)

    assert result.as_of_seq == _head(seeded)
    assert _head(seeded) > 0


@pytest.mark.parametrize(
    "name",
    [
        n
        for n, listing in LISTINGS_BY_NAME.items()
        if listing.scope is ListingScope.SUPERVISOR
    ],
)
def test_supervisor_listings_carry_no_as_of_seq(
    supervisor_dir: Path, seeded: SeededStore, name: str
) -> None:
    request = ListingRequest(project_id=None, options={}, compact=False)

    assert read_listing(name, request, supervisor_dir).as_of_seq is None


def test_projects_is_a_supervisor_listing() -> None:
    assert LISTINGS_BY_NAME[PROJECTS_LISTING].scope is ListingScope.SUPERVISOR


def test_a_commit_between_two_queries_does_not_split_the_read(
    supervisor_dir: Path, seeded: SeededStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``messages`` runs one query per channel, intent first, escalation second.

    After the intent query, an escalation message is committed through a
    separate read-write handle. Escalation is read second, so only the snapshot
    keeps that message out of the rows.
    """
    assert list(Channel) == [Channel.INTENT, Channel.ESCALATION]
    head_before = _head(seeded)
    original = Store.messages
    calls: list[Channel] = []

    def commit_after_first_query(
        self: Store, project_id: str, *, channel: Channel, after_seq: int = 0
    ) -> list[Message]:
        found = original(self, project_id, channel=channel, after_seq=after_seq)
        calls.append(channel)
        if len(calls) == 1:
            with Store.open(seeded.store_file) as writer:
                entry = writer.journal_entries(PROJECT, include_resolved=False)[0]
                writer.journal_escalate(entry.id, reason="committed mid-read")
        return found

    monkeypatch.setattr(Store, "messages", commit_after_first_query)
    during = read_listing(_MESSAGES, _every_channel(), supervisor_dir)
    monkeypatch.undo()

    assert calls == [Channel.INTENT, Channel.ESCALATION]
    assert [row["channel"] for row in during.rows] == [Channel.INTENT.value]
    assert during.as_of_seq == head_before

    after = read_listing(_MESSAGES, _every_channel(), supervisor_dir)
    assert [row["channel"] for row in after.rows] == [
        Channel.INTENT.value,
        Channel.ESCALATION.value,
    ]
    assert after.as_of_seq is not None and after.as_of_seq > head_before


def test_a_project_listing_without_a_project_raises(supervisor_dir: Path) -> None:
    request = ListingRequest(project_id=None, options={}, compact=False)

    with pytest.raises(ValueError, match="project id"):
        read_listing("nodes", request, supervisor_dir)
