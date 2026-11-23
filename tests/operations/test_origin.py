"""``reduce_origin`` and ``is_reduced_origin`` (slice 261, D3)."""

from __future__ import annotations

import pytest

from amoeba.operations.origin import is_reduced_origin, reduce_origin

THIS_REPO = "github.com/ecorkran/amoeba"


@pytest.mark.parametrize(
    ("address", "reduced"),
    [
        ("git@github.com:ecorkran/amoeba.git", THIS_REPO),
        ("https://github.com/ecorkran/Amoeba/", THIS_REPO),
        ("https://github.com/ecorkran/amoeba.git", THIS_REPO),
        ("https://user:secret@github.com/ecorkran/amoeba.git", THIS_REPO),
        ("https://user:p@ss@github.com/ecorkran/amoeba", THIS_REPO),
        ("https://host:8443/org/repo", "host:8443/org/repo"),
        ("ssh://git@host/org/repo.git", "host/org/repo"),
        (
            "ssh://git@Host.Example.COM:2222/Org/Repo.git/",
            "host.example.com:2222/org/repo",
        ),
        ("host.example.com:org/repo.git", "host.example.com/org/repo"),
        ("  git@github.com:org/repo.git\n", "github.com/org/repo"),
        ("https://github.com/org/repo.git/", "github.com/org/repo"),
    ],
)
def test_the_forms_git_prints_reduce_to_host_and_path(
    address: str, reduced: str
) -> None:
    assert reduce_origin(address) == reduced
    assert is_reduced_origin(reduced)


def test_the_two_forms_of_this_repo_reduce_alike() -> None:
    assert (
        reduce_origin("git@github.com:ecorkran/amoeba.git")
        == reduce_origin("https://github.com/ecorkran/Amoeba/")
        == THIS_REPO
    )


def test_a_password_is_in_no_output() -> None:
    reduced = reduce_origin("https://user:secret@host/org/repo")

    assert reduced == "host/org/repo"
    assert "secret" not in str(reduced)


@pytest.mark.parametrize(
    "address",
    [
        "",
        "   ",
        "/srv/git/repo.git",
        "./repo",
        "../repo",
        "~/repo",
        "file:///x/y",
        "FILE:///x/y",
        "https://github.com",
        "https://github.com/",
        "https:///org/repo",
        "https://user:secret@/org/repo",
        "nonsense",
        "host:",
        "C:\\work\\repo",
        "https://[::1]/org/repo",
        "git@host:secret@:::weird//address",
        "https://host/org/re po",
        "git@host:org/repo?token=x",
    ],
)
def test_text_with_no_host_and_path_gives_nothing(address: str) -> None:
    assert reduce_origin(address) is None


@pytest.mark.parametrize(
    "address",
    [
        "git@github.com:ecorkran/amoeba.git",
        "https://host:8443/org/repo",
        "https://u:p@host/a/b/c.git",
        "ssh://git@host/org/repo",
    ],
)
def test_every_output_passes_the_check(address: str) -> None:
    reduced = reduce_origin(address)

    assert reduced is not None
    assert is_reduced_origin(reduced)


@pytest.mark.parametrize(
    "value",
    [
        "GitHub.com/org/repo",
        "https://github.com/org/repo",
        "git@github.com:org/repo",
        "user@github.com/org/repo",
        "github.com/org/repo/",
        "github.com/org/repo.git",
        "github.com",
        "github.com/",
        "/org/repo",
        "",
        "host:port/org/repo",
        "host with space/org/repo",
    ],
)
def test_a_value_not_in_reduced_form_is_refused(value: str) -> None:
    assert not is_reduced_origin(value)


def test_a_reduced_form_is_not_reduced_again_to_the_same_thing() -> None:
    # Why the hub checks instead of reducing (D3): the reduced form reads as a path.
    assert reduce_origin(THIS_REPO) is None
    assert reduce_origin("example.com:8443/org/repo") == "example.com/8443/org/repo"
