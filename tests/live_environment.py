"""The environment a live pipeline run gets: named variables only (slice 180, D10).

The write step is a model with the provider's full tools, a shell included, so it can
read every variable it is launched with. Passing the whole test-run environment would
hand it anything in the developer's shell, such as a production database URL. This
list names what ``git``, ``cf`` and ``sq`` need to run, and the provider credentials
Squadron reads; everything else is dropped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

#: What the tools need to run: lookup path, user home (CF and Squadron config, the
#: SDK's login), temporary files, locale and terminal.
PROCESS_VARIABLES: Final = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
)

#: The provider credentials Squadron reads (its OpenRouter, OpenAI and Gemini
#: providers and the Anthropic settings).
PROVIDER_VARIABLES: Final = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
)

PIPELINE_VARIABLES: Final = (*PROCESS_VARIABLES, *PROVIDER_VARIABLES)


def pipeline_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """The named variables of ``environ`` that are set; nothing else."""
    return {name: environ[name] for name in PIPELINE_VARIABLES if name in environ}
