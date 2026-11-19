"""Color is off unless a person is reading a terminal that wants it."""

from __future__ import annotations

import io
import re

import pytest

from amoeba.cli.render.style import PLAIN, Painter, Tone, painter_for

ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_plain_paints_nothing() -> None:
    assert PLAIN("Requests", Tone.HEADING) == "Requests"


def test_an_enabled_painter_wraps_the_text_and_resets() -> None:
    painted = Painter(enabled=True)("Requests", Tone.HEADING)

    assert painted != "Requests"
    assert ESCAPE.sub("", painted) == "Requests"
    assert painted.endswith("\x1b[0m")


def test_a_terminal_gets_color() -> None:
    assert painter_for(_Terminal(), {}).enabled


@pytest.mark.parametrize(
    "environ", [{"NO_COLOR": "1"}, {"TERM": "dumb"}], ids=["no_color", "dumb"]
)
def test_the_environment_can_turn_color_off(environ: dict[str, str]) -> None:
    assert not painter_for(_Terminal(), environ).enabled


def test_a_pipe_gets_no_color() -> None:
    assert not painter_for(io.StringIO(), {}).enabled
