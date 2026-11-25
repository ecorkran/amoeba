"""The **Runs on other machines** and **Behind the hub** sections of ``status`` and
``list`` (slice 263, D12).

Another machine's runs are shown as that machine last reported them, under its own
heading with the age. A machine or session whose door version differs from the hub's
is listed with the command that brings it level. Neither section is something the PM
must answer, so neither sets a notice or changes ``Nothing needs you.``
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from amoeba.cli.render.sessions import FIELD_GAP
from amoeba.cli.render.text import command_line, how_long, indented
from amoeba.operations.status_machine_models import MachineEntry, MachineRunLine
from amoeba.operations.status_models import MemberStatus, StatusResult

RUNS_ON_OTHER_MACHINES: Final = "Runs on other machines"
BEHIND_THE_HUB: Final = "Behind the hub"
UPGRADE_COMMAND: Final = "uv tool install --force amoeba-ai"
AHEAD_OF_THE_HUB: Final = "ahead of the hub"
NOT_REPORTED: Final = "nothing reported"
RESTART_NOTE: Final = "Restart the sessions listed after the upgrade."
UPGRADE_HUB_NOTE: Final = (
    "A version above the hub's means the hub is the one to upgrade."
)
UPGRADE_NOTE: Final = "Upgrade the machines listed:"


def runs_on_other_machines_section(result: StatusResult, now: datetime) -> list[str]:
    """One heading per other machine, with a line per run it reported."""
    lines: list[str] = []
    for machine in result.machines:
        if machine.calling:
            continue
        lines.append(indented(_heading(machine, now)))
        lines.extend(indented(_run_line(run), 2) for run in machine.runs)
    return [RUNS_ON_OTHER_MACHINES, *lines] if lines else []


def _heading(machine: MachineEntry, now: datetime) -> str:
    if machine.runs_reported_at is None:
        return f"{machine.name}, {NOT_REPORTED}"
    reported = f"{machine.name}, reported {how_long(machine.runs_reported_at, now)} ago"
    if machine.runs_problem is None:
        return reported
    return f"{reported}, runs unreadable: {machine.runs_problem}"


def _run_line(run: MachineRunLine) -> str:
    return FIELD_GAP.join(
        (run.run_id, run.pipeline, run.status, run.directory or "no directory")
    )


def behind_the_hub_section(
    result: StatusResult, members: list[MemberStatus]
) -> list[str]:
    """Each machine and session on another door version than the hub's, or nothing."""
    hub = result.hub_door_version
    found = [
        (f"{machine.name}", machine.client_version, machine.door_version)
        for machine in result.machines
        if machine.behind
    ]
    found.extend(
        (
            f"{session.client}  {session.machine}  {session.directory}",
            session.client_version,
            session.door_version,
        )
        for member in members
        for session in member.sessions
        if session.behind
    )
    if not found:
        return []
    lines = [
        indented(f"{who}  {_versions(client, door, hub)}")
        for who, client, door in found
    ]
    notes = [indented(f"The hub serves door version {hub}.")]
    if any(not _is_ahead(door, hub) for _, _, door in found):
        notes += [indented(UPGRADE_NOTE), command_line(UPGRADE_COMMAND)]
        notes.append(indented(RESTART_NOTE))
    if any(_is_ahead(door, hub) for _, _, door in found):
        notes.append(indented(UPGRADE_HUB_NOTE))
    return [BEHIND_THE_HUB, *lines, *notes]


def _is_ahead(version: int | None, hub: int | None) -> bool:
    return version is not None and hub is not None and version > hub


def _versions(
    client_version: str | None, door_version: int | None, hub: int | None
) -> str:
    text = f"client {client_version}, door {door_version}"
    return f"{text}, {AHEAD_OF_THE_HUB}" if _is_ahead(door_version, hub) else text
