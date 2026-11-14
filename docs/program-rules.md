---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The two rule blocks a program member pastes into its rules file so a provider reports what it changed and a consumer reads those reports before designing a slice.
dateCreated: 20261114
dateUpdated: 20261114
status: complete
---

# Program rules

Two blocks, each pasted whole into a repo's rules file by an agent session in that repo,
as a commit to that repo's target. A repo outside a program carries neither. The
blocks use `amoeba changes` and `amoeba report-release` (`docs/cli-contract.md`); over
MCP the same operations are the `changes` and `report_release` tools
(`docs/mcp-server.md`).

## Consumer block

Where it goes: the rules file of a member that has providers, that is, one that
depends on other members (`amoeba add --depends-on`).

```markdown
Before designing a slice, check Amoeba for changes in what this repo depends on. Run `amoeba changes -j --since <time>` in this checkout, or call the `changes` MCP tool with this checkout's absolute path as `directory`. Take `<time>` from `git log -1 --diff-filter=A --format=%aI -- project-documents/user/slices/`; if that prints nothing, take it from `git log --max-parents=0 --reverse --format=%aI | head -1`. Judge each report against the slice. In the design's Dependencies section, list the reports that affect the slice and how, or state that none do. If a report means the slice cannot be designed as planned, stop with a question or a `BLOCKED:` line. If the call fails, record its error in the Dependencies section; never treat a failed call as no changes.
```

Run the first git command before committing the slice design, so a report made while
the repo implements an earlier slice is not missed (the starting point is the author
time of the commit that added the latest design on this branch, which a rebase or an
amend does not move). The path is the Context Forge slice-design path: a member whose
slice designs live somewhere else edits that path in its pasted copy.

## Provider block

Where it goes: the rules file of a member that other members depend on, and that repo's
release skill, after its tag step.

```markdown
When a slice merge into the target, or a release, changes something other repos use (an interface, a command, a file format, a schema, or behavior they rely on), run `amoeba report-release` in this checkout. Pass `--commit` as the full hash of the merged commit (`git rev-parse HEAD`), or for a release the tagged commit (`git rev-list -n 1 <tag name>`). Pass `--version` as the tag name for a release, and omit it otherwise. Pass `--changed` as what changed, for someone using this repo; for a release, cover everything since the previous release. Pass one `--touched` per thing changed. On a non-zero exit, record the error in the task notes or the release result, and do not retry with different values. If a report you made is wrong, run the same command with `--correct` and the true text. To take a report back entirely, run `amoeba report-release --commit <full hash> --withdraw`.
```

A release merges into a merge report only when the tag is on the reported commit: the
same call with `--version` adds the version and replaces the text, and a `from_source`
consumer does not see the commit twice. A release flow that adds its own
commit before tagging makes a second report, for the release commit, and a consumer
then sees both reports. That is by design: one report per commit.

## Choosing what a consumer sees

Which of a provider's reports a consumer sees is the pair's `consumed`
(`from_source` or `from_release`). Set it with the `--depends-on PROVIDER[:MODE]` row of
`amoeba add` in `docs/cli-contract.md`; without `:MODE` the config's `default_consumed`
applies (`docs/config-contract.md`).
