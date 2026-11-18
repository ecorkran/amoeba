"""``amoeba --version`` prints the installed package's version (issue #39)."""

from __future__ import annotations

from importlib.metadata import version

import pytest

from amoeba.cli.main import main
from amoeba.cli.parser import PACKAGE_NAME


@pytest.mark.parametrize("flag", ["--version", "-v"])
def test_version_flag_prints_the_installed_version_and_exits_zero(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([flag])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"{version(PACKAGE_NAME)}\n"


def test_help_lists_the_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "--version" in capsys.readouterr().out
