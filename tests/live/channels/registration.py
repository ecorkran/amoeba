"""Where the channels tier's session finds its server (slice 241, D9, D10).

Each ``RegistrationForm`` writes the registration somewhere the operator's own Claude
config never sees: the fixture directory, a file beside it, or a throwaway config
directory.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from live_environment import process_environment

#: How long ``claude mcp add`` may take.
MCP_ADD_TIMEOUT_SECONDS: Final = 60


class RegistrationForm(StrEnum):
    """How the server reaches the session (D9's order)."""

    PROJECT_MCP_JSON = "project .mcp.json"
    MCP_CONFIG_FLAG = "--mcp-config file"
    USER_SCOPE = "user-scope install"


@dataclass(frozen=True)
class ServerRegistration:
    """The stdio server the session loads, by name."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=lambda: {})

    def entry(self) -> dict[str, object]:
        return {"command": self.command, "args": list(self.args), "env": dict(self.env)}


@dataclass(frozen=True)
class SessionSpec:
    """What a session needs: where, which model, which server and form."""

    cwd: Path
    model: str
    registration: ServerRegistration
    form: RegistrationForm
    allowed_tools: Sequence[str]
    #: Where the ``--mcp-config`` file or throwaway user config goes.
    scratch: Path
    environ: Mapping[str, str]
    extra_environment: Mapping[str, str] = field(default_factory=lambda: {})


def register(spec: SessionSpec) -> tuple[list[str], dict[str, str]]:
    """Write the registration for ``spec.form``; the extra arguments and variables."""
    servers = {"mcpServers": {spec.registration.name: spec.registration.entry()}}
    if spec.form is RegistrationForm.PROJECT_MCP_JSON:
        (spec.cwd / ".mcp.json").write_text(json.dumps(servers), encoding="utf-8")
        return [], {}
    if spec.form is RegistrationForm.MCP_CONFIG_FLAG:
        config = spec.scratch / "mcp-config.json"
        config.write_text(json.dumps(servers), encoding="utf-8")
        return ["--mcp-config", str(config)], {}
    # A user-scope install goes in a throwaway config directory, which has no login
    # of its own: this form runs only where that directory has been logged in.
    config_directory = spec.scratch / "claude-config"
    config_directory.mkdir(exist_ok=True)
    variables = {"CLAUDE_CONFIG_DIR": str(config_directory)}
    registration = spec.registration
    command = ["claude", "mcp", "add", "--scope", "user"]
    command += [
        arg
        for key, value in registration.env.items()
        for arg in ("-e", f"{key}={value}")
    ]
    command += [registration.name, "--", registration.command, *registration.args]
    subprocess.run(
        command,
        env=process_environment(spec.environ, **variables),
        capture_output=True,
        text=True,
        check=True,
        timeout=MCP_ADD_TIMEOUT_SECONDS,
    )
    return [], variables
