"""``docs/program-rules.md``: both blocks exist and say what the code does
(slice 227, D6, 5.2). The real file is the fixture; the flags come from the parser."""

from __future__ import annotations

import argparse
import re
from typing import cast

import pytest
from rule_blocks import PROGRAM_RULES, real_rule_blocks, rule_blocks

from amoeba.cli.parser import build_parser

#: D4's two commands, which the consumer block gives for finding ``since``.
SLICE_DESIGN_COMMAND = (
    "git log -1 --diff-filter=A --format=%aI -- project-documents/user/slices/"
)
ROOT_COMMIT_COMMAND = "git log --max-parents=0 --reverse --format=%aI | head -1"
#: The flags the contract test also leaves out: ``-j`` is a parent-parser flag.
IGNORED_FLAGS = {"--help", "--json"}
_LONG_FLAG = re.compile(r"(?<![\w-])--[a-z][a-z-]*")


def _parser_flags(command: str) -> set[str]:
    """Every ``--flag`` the parser gives ``command``."""
    for action in build_parser()._actions:  # pyright: ignore[reportPrivateUsage]
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and command in choices:
            subparser = cast("argparse.ArgumentParser", choices[command])  # pyright: ignore[reportUnknownVariableType]
            return {
                option
                for sub_action in subparser._actions  # pyright: ignore[reportPrivateUsage]
                for option in sub_action.option_strings
                if option.startswith("--")
            }
    raise AssertionError(f"no command {command}")


def _flags_in(block: str) -> set[str]:
    """The long flags the block writes for its own command: every ``--flag`` outside
    the ``git`` commands it quotes."""
    return set(_LONG_FLAG.findall(re.sub(r"`git [^`]*`", "", block)))


def test_both_blocks_exist_in_the_real_file() -> None:
    blocks = real_rule_blocks()

    assert blocks.consumer
    assert blocks.provider
    assert blocks.consumer != blocks.provider


def test_the_consumer_block_names_changes_and_uses_only_its_flags() -> None:
    block = real_rule_blocks().consumer
    valid = _parser_flags("changes") - IGNORED_FLAGS
    used = _flags_in(block)

    assert "amoeba changes" in block
    assert used == valid, "the block uses every flag the command has and no other"
    assert re.search(r"amoeba changes -j\b", block), "the agent reads the -j document"


def test_the_provider_block_names_report_release_and_every_one_of_its_flags() -> None:
    block = real_rule_blocks().provider
    valid = _parser_flags("report-release") - IGNORED_FLAGS
    used = _flags_in(block)

    assert "amoeba report-release" in block
    assert used == valid, "the block uses every flag the command has and no other"


def test_the_consumer_block_gives_both_starting_point_commands() -> None:
    block = real_rule_blocks().consumer

    assert f"`{SLICE_DESIGN_COMMAND}`" in block
    assert f"`{ROOT_COMMIT_COMMAND}`" in block


@pytest.mark.parametrize("which", ["consumer", "provider"])
def test_no_block_contains_a_full_hash(which: str) -> None:
    block = getattr(real_rule_blocks(), which)

    assert not re.search(r"[0-9a-fA-F]{40}", block)


def test_the_rule_blocks_parser_is_lenient_about_heading_depth_and_fences() -> None:
    text = (
        "# Title\n\n#### The Consumer  block ##\nWhere.\n\n~~~~text\n# not a heading\n"
        "consumer text\n~~~~\n\n## the PROVIDER block\n\n````\nprovider text\n````\n"
    )

    blocks = rule_blocks(text)

    assert blocks.consumer == "# not a heading\nconsumer text"
    assert blocks.provider == "provider text"


def test_the_rule_blocks_parser_fails_loudly_when_a_block_is_missing() -> None:
    with pytest.raises(ValueError, match="provider"):
        rule_blocks("## Consumer block\n\n```\ntext\n```\n")


def test_the_file_carries_the_pointers_the_design_requires() -> None:
    text = PROGRAM_RULES.read_text(encoding="utf-8")

    for pointer in (
        "--depends-on PROVIDER[:MODE]",
        "docs/cli-contract.md",
        "default_consumed",
        "docs/config-contract.md",
        "second report",
        "edits that path",
    ):
        assert pointer in text, pointer
