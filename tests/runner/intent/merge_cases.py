"""The merge table: current row crossed with each body form (D1, D5; 132, D7)."""

from __future__ import annotations

from typing import Any

from amoeba.store import AcknowledgmentOutcome, ClearDesiredState, SetDesiredState

APPLIED = AcknowledgmentOutcome.APPLIED
NO_OP = AcknowledgmentOutcome.NO_OP
NODE = None  # the project target; the merge rules do not depend on the target

NONE_ROW = None
DRIVE_ONLY = {"drive": True}
HOLD_ONLY = {"hold": True}
DRIVE_HOLD = {"drive": True, "hold": True}
EXCLUDED = {"drive": False}


def set_row(**fields: Any) -> SetDesiredState:
    return SetDesiredState(node_id=NODE, **fields)


CLEAR = ClearDesiredState(node_id=NODE)

#: (id, current row, body, outcome, expected change)
CASES = [
    # drive
    ("drive/none", NONE_ROW, {"intent": "drive"}, APPLIED, set_row(drive=True)),
    ("drive/drive", DRIVE_ONLY, {"intent": "drive"}, NO_OP, None),
    (
        "drive/hold-kept",
        HOLD_ONLY,
        {"intent": "drive"},
        APPLIED,
        set_row(drive=True, hold=True),
    ),
    (
        "drive/excluded",
        EXCLUDED,
        {"intent": "drive"},
        APPLIED,
        set_row(drive=True),
    ),
    # exclude
    ("exclude/none", NONE_ROW, {"intent": "exclude"}, APPLIED, set_row(drive=False)),
    ("exclude/excluded", EXCLUDED, {"intent": "exclude"}, NO_OP, None),
    (
        "exclude/hold-kept",
        DRIVE_HOLD,
        {"intent": "exclude"},
        APPLIED,
        set_row(drive=False, hold=True),
    ),
    # pause
    ("pause/none", NONE_ROW, {"intent": "pause"}, APPLIED, set_row(hold=True)),
    ("pause/hold", HOLD_ONLY, {"intent": "pause"}, NO_OP, None),
    (
        "pause/drive-kept",
        DRIVE_ONLY,
        {"intent": "pause"},
        APPLIED,
        set_row(drive=True, hold=True),
    ),
    # resume
    ("resume/none", NONE_ROW, {"intent": "resume"}, NO_OP, None),
    ("resume/no-hold", DRIVE_ONLY, {"intent": "resume"}, NO_OP, None),
    ("resume/only-setting", HOLD_ONLY, {"intent": "resume"}, APPLIED, CLEAR),
    (
        "resume/drive-kept",
        DRIVE_HOLD,
        {"intent": "resume"},
        APPLIED,
        set_row(drive=True),
    ),
    # clear
    ("clear/none", NONE_ROW, {"intent": "clear"}, NO_OP, None),
    ("clear/drive", DRIVE_ONLY, {"intent": "clear"}, APPLIED, CLEAR),
    ("clear/hold", HOLD_ONLY, {"intent": "clear"}, APPLIED, CLEAR),
    ("clear/everything", DRIVE_HOLD, {"intent": "clear"}, APPLIED, CLEAR),
]
