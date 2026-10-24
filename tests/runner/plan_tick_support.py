"""Canned ``cf`` plan answers for the project-tick plan tests."""

from __future__ import annotations

import json

from amoeba.runner.lifecycle.plan_read import slice_list_command
from runner.observe_support import CfReply, FakeCf

INITIATIVES_KEY = "list initiatives"
ERROR_DOCUMENT = (
    '{"error":true,"code":"UNKNOWN","message":"No slice plan found for index"}'
)


def slices_key(index: int) -> str:
    return " ".join(slice_list_command(index)[:3])


def initiatives_json(*indexes: int, arch_file: str | None = "x-arch.md") -> str:
    return json.dumps(
        [
            {
                "index": index,
                "name": f"Initiative {index}",
                "isChecked": False,
                "archFile": arch_file,
                "status": "in_progress",
            }
            for index in indexes
        ]
    )


def slices_json(*indexes: int, status: str = "in_progress") -> str:
    return json.dumps(
        {
            "entries": [
                {
                    "index": index,
                    "name": f"Slice {index}",
                    "isChecked": False,
                    "designFile": None,
                    "status": status,
                }
                for index in indexes
            ]
        }
    )


def serve_plan(
    cf: FakeCf, initiatives: tuple[int, ...], slices: dict[int, tuple[int, ...]]
) -> None:
    """Answer the plan commands: these initiatives, these slices under each."""
    cf.replies[INITIATIVES_KEY] = CfReply(initiatives_json(*initiatives))
    for initiative in initiatives:
        if initiative in slices:
            cf.replies[slices_key(initiative)] = CfReply(
                slices_json(*slices[initiative])
            )
        else:
            cf.replies[slices_key(initiative)] = CfReply("", 1, ERROR_DOCUMENT)
