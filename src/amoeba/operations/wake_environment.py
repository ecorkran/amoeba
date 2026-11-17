"""What a wake command inherits, and what a recorded `detail` may say (244, D1, D6).

The wrapper is started by ``send``, so its own environment is the sender's. The woken
command must not receive it: a sender's keys and budget settings would let an agent
spend under the sender's credentials, outside the recipient's limits. The command
gets only the names in ``WAKE_ENV_NAMES``, copied from the wrapper's when set.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from amoeba.config.home import HOME_VARIABLE

#: The only environment variables a wake command sees. The Amoeba home variable
#: (``config.home.HOME_VARIABLE``) stays so the woken agent's ``amoeba`` calls reach
#: the same store.
WAKE_ENV_NAMES: Final = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    HOME_VARIABLE,
)


def build_wake_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """The names of ``WAKE_ENV_NAMES`` that ``environ`` sets, and nothing else."""
    return {name: environ[name] for name in WAKE_ENV_NAMES if name in environ}


def wake_detail(error: BaseException) -> str:
    """The one place the wrapper makes a recorded ``detail``; it never holds argv text.

    (``wake_after_send`` records a start failure with the text of the launch error or
    the missing-script error, which names a path to the checkout or the script and
    never the wake command.)

    An ``OSError`` gives its class and its ``strerror``, never its filename (a command
    may have been written with a secret in it). Anything else gives the class name.
    """
    if isinstance(error, OSError) and error.strerror:
        return f"{type(error).__name__}: {error.strerror}"
    return type(error).__name__
