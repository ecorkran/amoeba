"""Notes and release notes against real ``cf`` and ``git`` (slice 243, 8.1).

Verification Walkthrough steps 3, 5 and 6 through the CLI: a provider and two
consumers (one ``from_source``, one ``from_release``) in one program in a throwaway
``AMOEBA_HOME``. A report, a version, a correction and a withdrawal each reach the
right consumers' ``inbox -j``; a note to the program reaches the others. No model
runs. Every ``amoeba`` call goes by the harness's absolute path with that home.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from git_repo import commit_file

from amoeba.cli.exit_codes import EXIT_OK
from amoeba.config.home import store_path
from amoeba.operations.release_notes import RELEASE_NOTE_ID_PREFIX
from live.notes.consumer import NotesProgram
from live.pause.harness import PROGRAM_ID, PauseWorld, result_of, run_amoeba

TAG: Final = "v-notes-1"


def _amoeba(world: PauseWorld, *arguments: str) -> dict[str, Any]:
    completed = run_amoeba(world, *arguments)
    assert completed.returncode == EXIT_OK, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def _report(provider: PauseWorld, commit: str, *extra: str) -> dict[str, Any]:
    return _amoeba(
        provider,
        "report-release",
        "--commit",
        commit,
        "--changed",
        "adds the interface",
        "--touched",
        "interface",
        *extra,
    )


def _notes(world: PauseWorld) -> list[dict[str, Any]]:
    return list(_amoeba(world, "inbox")["notes"])


def test_the_store_amoeba_uses_is_the_throwaway_one(
    notes_program: NotesProgram, amoeba_home: Path
) -> None:
    resolved = store_path()

    assert resolved.is_relative_to(amoeba_home)
    _amoeba(notes_program.provider, "list")
    assert notes_program.provider.store == resolved
    assert resolved.exists()


def test_a_report_a_version_a_correction_and_a_withdrawal_reach_the_right_inboxes(
    notes_program: NotesProgram,
) -> None:
    provider = notes_program.provider
    source, release = notes_program.from_source, notes_program.from_release
    commit = commit_file(provider.repo, "interface.txt", "v1\n", "interface")

    # Step 5: a report with no version reaches the from_source consumer only.
    assert _report(provider, commit)["outcome"] == "recorded"
    (recorded,) = _notes(source)
    assert recorded["from_member"] != recorded["to_member"]
    assert recorded["id"].startswith(RELEASE_NOTE_ID_PREFIX)
    assert recorded["subject"] == f"Release report recorded: {commit}"
    assert _notes(release) == []

    # Versioning reaches the from_release consumer, with the commit, version and text.
    assert _report(provider, commit, "--version", TAG)["outcome"] == "versioned"
    (versioned,) = _notes(release)
    assert versioned["subject"] == f"Release report versioned: {TAG}"
    for text in (commit, TAG, "adds the interface", "interface"):
        assert text in versioned["body"]
    assert len(_notes(source)) == 1

    # Step 6: a correction reaches both; a withdrawal reaches both and says to
    # disregard the report.
    assert _report(provider, commit, "--correct")["outcome"] == "corrected"
    assert len(_notes(source)) == 2 and len(_notes(release)) == 2
    withdrawn = _amoeba(provider, "report-release", "--commit", commit, "--withdraw")
    assert withdrawn["outcome"] == "withdrawn"
    for consumer in (source, release):
        notes = _notes(consumer)
        assert len(notes) == 3
        assert notes[-1]["subject"].startswith("Release report withdrawn")
        assert "disregard" in notes[-1]["body"]


def test_a_note_to_the_program_reaches_every_member_but_its_sender(
    notes_program: NotesProgram,
) -> None:
    source = notes_program.from_source
    sent = _amoeba(
        source,
        "send",
        "--note",
        "--id",
        "live-note-1",
        "--to-program",
        PROGRAM_ID,
        "--subject",
        "a freeze",
        "--body",
        "do not merge after noon",
    )

    assert sent["outcome"] == "sent"
    assert _notes(source) == []
    for reader in (notes_program.provider, notes_program.from_release):
        (note,) = _notes(reader)
        assert (note["id"], note["to_program"]) == ("live-note-1", PROGRAM_ID)
    again = _amoeba(
        source,
        "send",
        "--note",
        "--id",
        "live-note-1",
        "--to-program",
        PROGRAM_ID,
        "--subject",
        "a freeze",
        "--body",
        "do not merge after noon",
    )
    assert again["outcome"] == "unchanged"
