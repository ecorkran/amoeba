"""``docs/program-rules.md``: the four blocks exist and say what the code does
(slices 227 and 240). The real file is the fixture; the flags come from the parser."""

from __future__ import annotations

import argparse
import re
from typing import cast

import pytest
from rule_blocks import PROGRAM_RULES, real_rule_blocks, rule_blocks

from amoeba.cli.parser import build_parser
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE

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


def test_all_four_blocks_exist_in_the_real_file() -> None:
    blocks = real_rule_blocks()

    texts = [blocks.consumer, blocks.provider, blocks.requesting, blocks.handling]
    assert all(texts)
    assert len(set(texts)) == len(texts)


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


@pytest.mark.parametrize("which", ["consumer", "provider", "requesting", "handling"])
def test_no_block_contains_a_full_hash(which: str) -> None:
    block = getattr(real_rule_blocks(), which)

    assert not re.search(r"[0-9a-fA-F]{40}", block)


def test_the_rule_blocks_parser_is_lenient_about_heading_depth_and_fences() -> None:
    text = (
        "# Title\n\n#### The Consumer  block ##\nWhere.\n\n~~~~text\n# not a heading\n"
        "consumer text\n~~~~\n\n## the PROVIDER block\n\n````\nprovider text\n````\n"
        "\n### Requesting\n```\nrequesting text\n```\n"
        "\n##### HANDLING block #####\n~~~\nhandling text\n~~~\n"
    )

    blocks = rule_blocks(text)

    assert blocks.consumer == "# not a heading\nconsumer text"
    assert blocks.provider == "provider text"
    assert blocks.requesting == "requesting text"
    assert blocks.handling == "handling text"


def test_the_rule_blocks_parser_fails_loudly_when_a_block_is_missing() -> None:
    with pytest.raises(ValueError, match="provider"):
        rule_blocks(
            "## Consumer block\n\n```\ntext\n```\n"
            "## Requesting block\n\n```\ntext\n```\n"
            "## Handling block\n\n```\ntext\n```\n"
        )


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


def test_the_consumer_block_tells_the_agent_report_text_is_quoted_data() -> None:
    assert QUOTED_DATA_NOTICE in real_rule_blocks().consumer


#: A command the block writes, as the text quotes it: ``amoeba <command> ...`` in
#: backticks, up to the closing backtick.
_COMMAND_SPAN = re.compile(r"`amoeba (?P<command>[a-z-]+)(?P<rest>[^`]*)`")
_REQUEST_COMMANDS = {"send", "inbox", "reply", "cancel"}


def _commands_in(block: str) -> list[tuple[str, set[str]]]:
    """Each ``amoeba <command>`` the block quotes, with the long flags it gives it."""
    return [
        (found["command"], set(_LONG_FLAG.findall(found["rest"])))
        for found in _COMMAND_SPAN.finditer(block)
    ]


@pytest.mark.parametrize("which", ["requesting", "handling"])
def test_the_request_blocks_use_only_commands_and_flags_the_parser_has(
    which: str,
) -> None:
    block = getattr(real_rule_blocks(), which)

    commands = _commands_in(block)

    assert commands, "the block quotes at least one command"
    for command, flags in commands:
        assert command in _REQUEST_COMMANDS, command
        assert flags <= _parser_flags(command), (command, flags)


def test_the_requesting_block_sends_with_every_flag_it_needs() -> None:
    block = real_rule_blocks().requesting
    send = next(flags for command, flags in _commands_in(block) if command == "send")

    assert {"--id", "--to", "--subject", "--body"} <= send
    assert "--parent" in block
    assert "`send` MCP tool" in block


def test_the_handling_block_names_the_four_inbox_moments_and_the_three_replies() -> (
    None
):
    block = real_rule_blocks().handling

    for moment in (
        "at session start without `--since`",
        "before starting a task or slice",
        "after each commit",
        "before ending the session",
    ):
        assert moment in block, moment
    quoted = {command for command, _ in _commands_in(block)}
    assert quoted == {"inbox", "reply"}
    replies = " ".join(text for text in re.findall(r"`amoeba reply [^`]*`", block))
    for action in ("accept", "decline", "done"):
        assert f" {action}" in replies, action
    assert "`inbox` MCP tool" in block


@pytest.mark.parametrize("which", ["requesting", "handling"])
def test_the_request_blocks_carry_the_notice(which: str) -> None:
    assert QUOTED_DATA_NOTICE in getattr(real_rule_blocks(), which)


def test_the_intro_covers_all_four_blocks() -> None:
    text = PROGRAM_RULES.read_text(encoding="utf-8")
    intro = text[: text.index("## Consumer block")]

    assert "Four blocks" in intro
    assert "Two blocks" not in text
    for name in ("Requesting", "Handling", "Consumer", "Provider"):
        assert name in intro, name
    assert "Every member carries the Handling block" in " ".join(intro.split())
