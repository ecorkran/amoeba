"""Subscriber-side access to a project's change feed.

Followers run outside the resident process. They open the project store
read-only, own their cursor, and never write. See ``docs/feed-contract.md``.
"""

from __future__ import annotations

from amoeba.feed.follower import FeedSettings, follow

__all__ = ["FeedSettings", "follow"]
