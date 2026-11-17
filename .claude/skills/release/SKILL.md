---
name: release
description: Cut an amoeba-ai release — bump the version, update the changelog, tag, push, then watch CI until it is green and PyPI shows the new version. Use when the user says "release", "cut a release", "ship it", or "bump and tag".
---

# Release amoeba-ai

Run from the repo root. Stop and report on any failed command; don't work around it.

## 1. Check cf state

Run `cf next`. If it reports something unfinished (open review gate, unchecked tasks, failing check), stop and show it. Otherwise continue.

## 2. Merge

Read the target with `cf config get git.integration_branch --value` (empty means `main`). If the current branch is a slice branch not yet merged into the target, follow the merge steps in CLAUDE.md (Git Rules). If already on the target with the work merged, skip this.

## 3. Pick the version

The working tree must be clean before continuing; if it isn't, stop and show `git status`.

Current version: `version` in `pyproject.toml`. Read the unreleased changes: use `## [Unreleased]` in `CHANGELOG.md`.

- **Patch** is the default: fixes, refinements, and new flags, options, parameters, config keys or checks. A non-empty changelog, or entries under `### Added`, does not make a release minor.
- **Minor** only for a new user-facing feature or a significant new AI capability. Propose it in one line with the reason and wait for the user to confirm before changing any files.
- **Major** only when the user explicitly asks for it.

For a patch, state the chosen version in one line and proceed.

## 4. Bump and document

1. Set `version` in `pyproject.toml`, then run `uv lock`.
2. In `CHANGELOG.md`, insert `## [X.Y.Z] - YYYY-MM-DD` directly under `## [Unreleased]`, so the unreleased entries sit under the new version and `[Unreleased]` is empty. Entries stay short and user-facing.
3. In `DEVLOG.md`, under today's `## YYYYMMDD` heading (create it at the top if missing), add `### Release X.Y.Z` with a one-line contents summary.
4. Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest`. Any failure stops the release; CI would block the publish anyway. These only check: if formatting or lint fails, stop, fix it in its own commit, and start the release again.
5. Commit: `package: bump version to X.Y.Z`.

## 5. Tag and push

Invoking this skill is the user's request to push.

```
git tag -a vX.Y.Z -m "vX.Y.Z"
git push
git push --tags
```

## 6. Watch CI

The `publish` job in `.github/workflows/ci.yml` runs only on the tag and needs `check` to pass. A red `check` means nothing publishes, silently. A tag alone is not a release: it is not done until PyPI shows the new version.

Start a loop via the `loop` skill with a 5 minute interval and this check:

1. `gh run list --workflow ci.yml --branch vX.Y.Z --json databaseId,status,conclusion,headSha` — match `headSha` to the tagged commit. (`--commit` is unreliable right after a push.)
2. Still running: report status and wait for the next tick.
3. Failed: pull the log (`gh run view <id> --log-failed`), report the actual error, stop the loop.
4. Passed: confirm with `curl -sf https://pypi.org/pypi/amoeba-ai/X.Y.Z/json`. If it returns, report "X.Y.Z live on PyPI" and stop the loop. If not yet, wait for the next tick.

Always stop the loop yourself when it resolves either way.

## 7. Update the live install

Once PyPI shows the new version, put it on this machine. From the main checkout:

```
uv run python scripts/update_live.py update
```

It backs up the live store and config, appends any config key the new code needs, reinstalls amoeba, migrates the store and checks the result. If a check fails it has already restored the backup and the previous install and exits 1: report its output and stop. Otherwise report the client sessions it lists in the release summary; they run the old `amoeba-mcp` until restarted. This is a release step, not a per-slice step: merged slices wait for the next release.
