"""A change's wire form: the one JSON object ``amoeba feed`` and the server send."""

from __future__ import annotations

from amoeba.store import Change


def change_record(change: Change) -> dict[str, object]:
    """One change as a JSON-ready dict, keys in :class:`Change`'s field order."""
    return {
        "seq": change.seq,
        "project_id": change.project_id,
        "kind": change.kind.value,
        "node_id": change.node_id,
        "subject_id": change.subject_id,
        "payload": dict(change.payload),
        "recorded_at": change.recorded_at.isoformat(),
    }
