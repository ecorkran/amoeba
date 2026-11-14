---
docType: slice-design
slice: program-dependencies
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 224-slice.status-and-decisions
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
- 229-slice.human-cli
interfaces: []
dateCreated: 20261107
dateUpdated: 20261113
status: not_started
---

# Slice Design: Program Dependencies

## Overview

Scenario B. A provider repo reports what it released, and a consumer reads those reports before designing a slice. Nobody relays anything.

- **`report_release`** records a release from the member's own checkout. The same operation corrects a report's text or withdraws it (D1, D2).
- **`changes`** returns what this member's providers reported since a time the caller gives, filtered by each pair's `consumed`. Nothing is marked read (D3, D4).
- Both are added to the CLI and the MCP tool table under the same names (D5).
- `docs/program-rules.md` holds the two rule blocks a member pastes into its rules file (D6).
- Integration is proven by automated tests: a flow test runs the rule block's commands in fixture repos, and a live test runs both operations against real `cf` (D7). No step waits on real use.

No table or migration: `releases` and `dependency_pairs.consumed` are in the baseline. This slice does not change `EXPECTED_SCHEMA_VERSION`; it stays at the value 226 sets.

## Value

User value. A repo designing a slice sees what changed in the repos it depends on without the PM relaying it. A `from_release` consumer doesn't see a provider's unreleased work. A wrong report is fixed or withdrawn by the agent that made it.

## Technical Scope

**Included:** `store/releases.py` and a `Release` model; `operations/report_release.py` (modes `report`, `correct`, `withdraw`); `operations/changes.py`; `operations/since.py`; two `RejectCode` members; two `OperationName` members, `wiring.invoke` cases, CLI subcommands and MCP rows; `docs/program-rules.md`; contract doc updates (D8); tests (D7).

**Excluded:**

- Any change to `add` or `rm`. Pairs and `consumed` are set by `add --depends-on` (222 D7, 229 D4); removal is `rm --pair` (228, 229 D6).
- Marking reports read, notifying consumers, or reading past direct providers (architecture: pull, never walks the graph).
- Running `git` from Amoeba. The caller passes a full hash and a time.
- A pipeline step that calls `changes` (`ecorkran/squadron#304`, slice plan Future Work 1). Not part of this slice.

## Dependencies

- **224:** `project_names` (`upstream/context_forge/projects.py`); `resolve_member` and `ContextForgeError` (`operations/members.py`); `RejectCode` and `validation_problems` (`operations/reject_codes.py`); `decisions`' `since` rule, which this slice moves into `parse_since()` (D5).
- **226:** `OperationName`, `ToolSpec`, `RunMode`, `wiring.invoke` (`src/amoeba/wiring.py`), `build_parser()`, and 226's parity tests. 226 is merged.
- **229:** `OperationName.cli_name`, the `-j` parent parser, `cli/render/`, and the `add` and `rm` commands this slice's text refers to. 229 merges first.
- **228:** `state_layout()`, which the doors use to open the store. Its active-member rule means `pairs_of` returns only pairs whose two members are active.
- **222:** `Store.read()` and `Store.write()` (`write()` is `BEGIN IMMEDIATE`), `encode_string_list` and `decode_string_list`, `encode_timestamp` and `decode_timestamp`, `ConsumedMode`, and the `releases` table (`seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`, `UNIQUE (member_id, commit_sha)`).
- **225:** complete, with no verdict. Plan entry 6 dropped the counted trial, so this slice has no gate.
- No new packages, no Squadron or Context Forge change.

## Architecture

```
src/amoeba/
├── store/models.py            # + Release
├── store/releases.py          # release_for_commit, insert_release, add_version,
│                              #   correct_release, delete_release, visible_releases
├── operations/names.py        # + REPORT_RELEASE, CHANGES
├── operations/reject_codes.py # + NOT_A_MEMBER, NOT_REPORTED
├── operations/since.py        # parse_since(); decisions calls it too
├── operations/report_release.py
├── operations/changes.py
├── wiring.py                  # + two invoke cases (226 D4)
├── cli/main.py                # + two subcommands
└── mcp/tools.py               # + two rows
docs/program-rules.md
```

Import direction is unchanged: `cli`, `mcp` → `operations` → `store`, `upstream`.

**Flow.** Each operation validates the unvalidated document from either door into its request model (`rejected / malformed` on failure). `changes` then reads the names with one `cf` call, and both operations resolve the directory with `resolve_member` (`rejected / not_a_member`). The detail tells the two outcomes apart: for `NotInProgram`, "this Context Forge project is in no program"; for `NotAProject`, "this directory is in no Context Forge project" followed by Context Forge's message. No `cf` call runs while a write transaction is open. `report_release` applies D2 in one `store.write()` transaction. `changes` reads pairs and visible reports in one `store.read()` transaction and writes nothing.

**State.** `releases` is written only by `report_release`. A row is created by a report, changed by versioning or correction, and deleted by withdrawal. No read position is stored (D4).

## Technical Decisions

### D1 — The release request

`ReportReleaseRequest`: frozen pydantic, `extra="forbid"`, with a model validator that enforces the mode rules.

| Field | Rule |
|---|---|
| `mode` | `report` (default), `correct` or `withdraw`. A `ReportMode` StrEnum. |
| `commit` | Required in every mode. Stripped, lowercased; 40 or 64 hex characters. An abbreviated hash would split one commit into two reports. The rejection detail says `git rev-parse` gives a full hash. |
| `version` | Optional in `report` and `correct`; stripped, non-empty when given; stored as given. Not allowed in `withdraw`. |
| `changed` | Required in `report` and `correct`; non-empty. Not allowed in `withdraw`. |
| `touched` | Required in `report` and `correct`: at least one non-empty string; duplicates removed, order kept; stored as a JSON array so a consumer agent can match items without parsing prose. Not allowed in `withdraw`. |

A field the mode does not allow is `malformed`, and the detail names the field and the mode.

### D2 — Report identity, repeats, corrections and withdrawal

A report is identified by member and commit. With `stored` being the member's report for `commit`:

| Mode | Case | Outcome | Write |
|---|---|---|---|
| `report` | No `stored` | `recorded` | Insert. `reported_at` now; `versioned_at` now if a version is given, else null. |
| `report` | A version is given and differs from `stored`'s, or `stored` has none | `versioned` | Set `version`; `versioned_at` now; replace `changed` and `touched`. `reported_at` and `seq` unchanged. |
| `report` | Anything else | `unchanged` | None. |
| `correct` | No `stored` | `rejected` / `not_reported` | None. |
| `correct` | `stored` exists | `corrected` | Replace `changed` and `touched`. Set `version` if given, else keep it. `reported_at` now. `versioned_at` now if the row has a version after the write, else null. |
| `withdraw` | No `stored` | `rejected` / `not_reported` | None. |
| `withdraw` | `stored` exists | `withdrawn` | Delete the row. |

- A repeat in `report` mode is `unchanged` whatever its wording, since agents rephrase. The result carries the stored report.
- Versioning replaces the text because a release describes everything since the previous release. `reported_at` doesn't move, so `from_source` consumers don't see the commit again (D3).
- Only a tag on the reported commit merges into a report. A release flow that adds its own commit makes a second report.
- A correction moves the times to now so consumers see it again. A `from_source` consumer sees the corrected report if its `since` predates the correction. A `from_release` consumer sees it if the row is versioned and its `since` predates the correction. A consumer whose `since` is later doesn't see it.
- Withdrawal deletes the row. A consumer that already read the report keeps its own record in its Dependencies section; that section is the record the operator sees.
- A withdrawn commit can be reported again; it gets a new `seq`.
- `BEGIN IMMEDIATE` serializes concurrent writers, and the stored-row check and the write share one transaction. An `IntegrityError` on the unique key is a bug and is not caught.

`ReportReleaseResult`: `outcome` (`recorded`, `versioned`, `corrected`, `unchanged`, `withdrawn`, `rejected`); `member` (the CF project id, or null when the directory is not a member); `report` (the stored report after the call; null after `withdrawn` and on rejection); `problems` (`code` from `RejectCode`: `malformed`, `not_a_member` or `not_reported`, and `detail`).

Rows are bounded: one per commit a member reported, so they grow with the member's merges and releases. `withdraw` is the explicit cancel for a row, and no cleanup job runs.

### D3 — What `changes` returns

`ChangesRequest`: `since`, required, validated by `parse_since` (D5). The member is the caller's directory.

Flow: validate; `project_names()` (one `cf` call; a `CfCallFailed` raises `ContextForgeError`); `resolve_member`; then one read transaction that takes the caller's pairs from `pairs_of` (the rows whose consumer is the caller) and calls `visible_releases` for each pair. `visible_releases(tx, provider_id, consumed, since)` selects:

| `consumed` | Visible when | Ordered by |
|---|---|---|
| `from_source` | `reported_at >= since` | `reported_at`, `seq` |
| `from_release` | `version IS NOT NULL AND versioned_at >= since` | `versioned_at`, `seq` |

- Every pair is listed, including pairs with nothing visible, so "checked, nothing new" differs from "not a dependency". A member with no providers gets `listed` with empty `pairs`. Pairs come in `pairs_of`'s order (provider id, consumer id).
- A member or provider id that `project_names` does not list keeps its id, gets `name: null`, and adds a `warnings` entry (`not_in_context_forge`, with the id). The outcome stays `listed`. A `cf` failure is not a warning; it is `ContextForgeError`.

`ChangesResult`: `outcome` (`listed`, `rejected`); `member` (`{id, name}`); `since` (normalized UTC text); `pairs` (each `{provider: {id, name}, consumed, releases}`, where each release has the `report` shape of D2); `problems` (`malformed`, `not_a_member`); `warnings` (`not_in_context_forge`, with detail).

### D4 — The starting point belongs to the caller

Amoeba stores no read marker. A marker kept by Amoeba would be shared by every worktree of a member, so a change could be hidden from one worktree by another. The caller gives `since`, and the rule block tells the consumer agent how to get it from git. The consumer's `since` is the author time of the commit that added the most recent slice design on its branch. Author time, not committer time: a rebase, cherry-pick or amend rewrites the committer date to the time of the rewrite, which would move `since` later and silently skip reports, while the author date survives them. (The project merges slice branches with a plain `git merge`, never a squash, so the author date also survives the merge.)

    git log -1 --diff-filter=A --format=%aI -- project-documents/user/slices/

If that prints nothing (no previous design), use the earliest root commit's time, which also handles several roots:

    git log --max-parents=0 --reverse --format=%aI | head -1

The agent runs it before committing its own design. A provider often reports while the consumer implements, after the consumer's design and before its merge, so the last merge would miss that report. The path is the Context Forge slice-design path; a member whose slice designs live elsewhere edits the path in its pasted block.

### D5 — Doors and shared pieces

- `OperationName` gains `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"`; the MCP tools use those names and the CLI uses `cli_name` (`report-release`, `changes`, 229 D1). 229's name-parity test covers them.
- Both commands print text by default and the result document with `-j` (229 D2). Each gets a renderer in `cli/render/`: the first line says `reported`, `unchanged`, `corrected`, `withdrawn` or `rejected: <code>`, and `changes` prints one entry per report (provider name, commit, version, changed text cut to the line width, touched items) with `No changes since <time>.` when empty. The rule blocks (D6) run `changes` with `-j`, so an agent reads the document.
- `wiring.invoke` gains two cases. Each calls its operation with the caller's directory and the door (226 D4).
- `operations/since.py`: `parse_since(value: str) -> str`. An ISO-8601 string with an offset becomes the store's UTC text (`encode_timestamp`). A string with no offset, or one that does not parse, raises `ValueError` with the same messages 224 uses. `DecisionsRequest._utc_text` in `operations/decisions.py` calls `parse_since`, so its behavior, messages and tests do not change.
- `RejectCode` gains `NOT_A_MEMBER` and `NOT_REPORTED`. `test_contract_docs` checks the codes against the contract docs (D8).
- **CLI:**
  ```
  amoeba report-release --commit <sha> [--version <v>] --changed <text> --touched <item> [--touched <item> …] [--correct]
  amoeba report-release --commit <sha> --withdraw
  amoeba changes --since <iso-8601>
  ```
  `--correct` and `--withdraw` form a mutually exclusive group. No flag is `required=True` in argparse. Absent flags are left out of the document, so the operation rejects a missing field with the same detail on both doors. `--touched` is repeatable and collected as a list. Exit codes: `0` for any non-rejected outcome, `1` rejected, `2` usage, `3` operational error (`OPERATIONAL_ERRORS`).
- **MCP:** two `ToolSpec` rows: `RunMode.IN_PROCESS`, `takes_directory = True`, `request_model` `ReportReleaseRequest` and `ChangesRequest`. No per-tool adapter (226 D2). Descriptions say what the call does, say that `report_release` also corrects or withdraws, and contain no example values.

### D6 — The rule blocks

`docs/program-rules.md` holds two blocks, each pasted whole, and says where each goes. A repo outside a program carries neither.

**Consumer** (rules file of a member with providers):

> Before designing a slice, check Amoeba for changes in what this repo depends on. Run `amoeba changes -j --since <time>` in this checkout, or call the `changes` MCP tool with this checkout's absolute path as `directory`. Take `<time>` from `git log -1 --diff-filter=A --format=%aI -- project-documents/user/slices/`; if that prints nothing, take it from `git log --max-parents=0 --reverse --format=%aI | head -1`. Judge each report against the slice. In the design's Dependencies section, list the reports that affect the slice and how, or state that none do. If a report means the slice cannot be designed as planned, stop with a question or a `BLOCKED:` line. If the call fails, record its error in the Dependencies section; never treat a failed call as no changes.

**Provider** (rules file of a member others depend on, and the repo's release skill after its tag step):

> When a slice merge into the target, or a release, changes something other repos use (an interface, a command, a file format, a schema, or behavior they rely on), run `amoeba report-release` in this checkout. Pass `--commit` as the full hash of the merged commit (`git rev-parse HEAD`), or for a release the tagged commit (`git rev-list -n 1 <tag name>`). Pass `--version` as the tag name for a release, and omit it otherwise. Pass `--changed` as what changed, for someone using this repo; for a release, cover everything since the previous release. Pass one `--touched` per thing changed. On a non-zero exit, record the error in the task notes or the release result, and do not retry with different values. If a report you made is wrong, run the same command with `--correct` and the true text. To take a report back entirely, run `amoeba report-release --commit <full hash> --withdraw`.

The Dependencies section is where the consumer records the result, because `changes` writes nothing. No sample hash, time or version appears near any value the agent must fetch (project rules, hallucination traps).

### D7 — Tests

Default suite, autouse `AMOEBA_HOME` fixture, the replayed `cf` in `tests/cf_fixtures.py`, and the git helpers in `tests/git_repo.py`.

- **Validation:** per mode, each cross-field violation and each bad field is `malformed`: abbreviated or non-hex hash; empty `changed`; empty or missing `touched`; blank `version`; `version` or `touched` on `withdraw`; offset-less `since`; unknown field. An upper-case hash is stored lowercased; duplicate `touched` items are removed in order.
- **D2:** one test per row of the table, asserting outcome and stored row, including a second version on a versioned commit. A rephrased repeat keeps the stored text.
- **Corrections:** a `from_source` `since` between the original report and the correction sees the corrected report; a `since` after the correction sees nothing. A `from_release` consumer sees a corrected row once it is versioned. `correct` and `withdraw` on a commit with no report are `rejected / not_reported` and write nothing.
- **Withdrawal:** after `withdraw`, `changes` no longer lists the report, and reporting the commit again is `recorded`.
- **D3 (store level, rows seeded at chosen times):** the merge report reaches only `from_source`; after versioning, `from_release` sees it with the release text; a `from_source` `since` between report and tag sees nothing, and an earlier one sees one entry with the version; two `since` values each see everything after their own point; a provider's provider is never listed; no providers gives empty `pairs`.
- **Warnings:** a provider missing from the `cf` names is listed with `name: null` and one `not_in_context_forge` warning. A `cf` failure raises `ContextForgeError`.
- **Non-members:** `not_a_member` on both operations, and nothing written.
- **`changes` writes nothing:** a table dump before and after is equal.
- **Doors:** 226's parity tests cover the rows. 226's stdio literal count becomes one per `OperationName` member (the one edit to a 226 test). One CLI test per subcommand for exits 0, 1 and 2 (the mutually exclusive flags); a repeated `--touched` arrives as a list; absent flags are absent from the document.
- **Rule blocks:** `docs/program-rules.md` has both blocks, each in the form D6 gives. Each names its operation and flags as `build_parser()` defines them (flag names come from the parser, not a literal list). The consumer block contains both D4 commands. Neither block contains a 40-hex string. The parser is lenient about heading and whitespace, and the real file is the fixture.
- **Flow test (automated integration)**, `tests/program/test_program_flow.py`: a provider repo and a consumer repo from `tests/git_repo.py`, both members of one program in a replayed `cf`. The test reads the consumer block from `docs/program-rules.md`, runs its two git commands in the consumer repo, and passes the output to `changes`. Then it checks the window case: the provider reports after the consumer's design commit and before its merge, and the consumer's `since` still sees the report (author dates set with `GIT_AUTHOR_DATE`, and a clock fixed after the design commit). A rebase case follows: the consumer's branch is rebased onto a newer commit with `GIT_COMMITTER_DATE` after the report, and the consumer's `since`, taken again from the rule block's command, still sees the report. The provider then tags and reports with a version, and the `from_release` consumer sees it.
- **Live test**, `tests/live/program/test_program_dependencies_live.py`: real `cf` and `git`, two throwaway members built with the helpers in `tests/live/pause/harness.py`, and a throwaway `AMOEBA_HOME`. It runs both operations through the CLI and asserts `recorded`, `unchanged`, `malformed` with exit 1, and the consumer's `changes` result. It exercises the real `cf list projects` output through `project_names`.

### D8 — Contract docs

- `docs/store-contract.md`: `releases` is written only by `report_release`; `touched` is a JSON array; D2's identity, repeat, correction and withdrawal rules; no read record is kept.
- `docs/cli-contract.md` and `docs/mcp-server.md`: the two operations, their flags, modes, outcomes and exit codes; both MCP tools take an absolute `directory`.
- `docs/program-rules.md`: the D6 blocks; a pointer to the `add --depends-on` contract (229) for choosing `consumed`; and the D2 note that a release merges into a merge report only when the tag is on the reported commit, and that a release flow adding its own commit makes a second report.

## Implementation Details

**`changes` result (JSON).** A `report_release` result carries the same `report` object.

```json
{"outcome": "listed",
 "member": {"id": "<cf project id>", "name": "<cf name>"},
 "since": "<UTC ISO-8601>",
 "pairs": [{"provider": {"id": "<cf project id>", "name": "<cf name>"},
            "consumed": "from_release",
            "releases": [{"seq": 0, "commit": "<full hash>", "version": "<tag>",
                          "changed": "<text>", "touched": ["<item>"],
                          "reported_at": "<UTC ISO-8601>", "versioned_at": "<UTC ISO-8601>"}]}],
 "problems": [],
 "warnings": []}
```

**Python:** `report_release(store, document, *, directory, deps)` and `changes(store, document, *, directory, deps)`. Each takes the time once per call from `deps.clock()` and passes it to the store writes.

## Success Criteria

- A `from_source` consumer sees a provider's merge report; a `from_release` consumer sees it only once it has a version.
- Tagging a release on an already reported commit adds the version; a `from_source` consumer does not see it twice.
- A correction is seen again by consumers whose `since` predates it, and a withdrawn report is no longer listed.
- Two worktrees calling `changes` from different starting points each see everything since their own point.
- Both operations work on the CLI and over MCP with the same inputs and results. A caller outside every program gets `not_a_member` and nothing is written.
- A provider missing from `cf`'s names is listed with a warning. A `cf` failure exits 3.
- Format, lint, pyright (strict), the full default suite and the live test pass. This slice does not change `EXPECTED_SCHEMA_VERSION`. Docs match the code (D8).
- Integration without a real design run: the flow test runs the rule block's commands in fixture repos and gets the reports, and the live test runs both operations against real `cf`.

### Verification Walkthrough

All steps run by the implementing agent, with no person involved.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest` passes. This includes the flow test.
2. The live test `tests/live/program/test_program_dependencies_live.py` passes with real `cf` and `git`.

## Operator Walkthrough

The operator is an agent session in each repo.

- **Start.** Install the tool (`uv tool install --force <repo>`, as 226 D8). An agent session in each member that others depend on adds the provider block to that repo's rules file and release skill. An agent session in each member with providers adds the consumer block to its rules file. Each change is a commit to that repo's target. Nothing waits on the PM.
- **Normal, provider.** After a merge that others use, the agent runs `report_release` with the full hash: `recorded`. After a release tag, it runs the same command with `--version`: `versioned`.
- **Normal, consumer.** Before designing, the agent runs the D4 git command, then `changes`, and records the reports, or that there are none, in its Dependencies section.
- **Failure: bad input.** An abbreviated hash, empty text or a blank version gives exit 1 and `malformed` with the detail. The agent corrects the value and runs again. A rejected call writes nothing.
- **Failure: not a member.** `not_a_member`, and nothing is written. The detail says which case it is (a Context Forge project in no program, or a directory in no Context Forge project), and the agent records that in its Dependencies section.
- **Failure: `cf` down.** Exit 3 with the error. The agent records the error in its Dependencies section and does not retry with other values. It never treats the failure as "no changes".
- **Failure: no previous design.** The fallback command runs. If the repo has no commits, both git commands print nothing, `since` is empty, and `changes` rejects it as `malformed`. The agent records that error.
- **Wrong report.** `--correct` with the true text: `corrected`. Consumers whose `since` predates the correction see it again.
- **Report that should not exist.** `--withdraw` with the full hash: `withdrawn`. The report is gone from `changes`. A consumer that read it earlier keeps its own record in its Dependencies section.
- **End state.** Each report is one row per commit a member reported, and the rows are the record. No cleanup job runs. A removed member's reports stay in the table, bounded by its history, and are not listed because its pairs are gone.
- **Clear or undo.** A single report: `--withdraw`. A pair: `amoeba rm --pair PROVIDER:CONSUMER` (228, 229). No step edits SQLite by hand.

**Dead ends found and closed:**

- A wrong `touched` list had no fix except a hand edit. Closed by `correct` (D2).
- A correction would be invisible to consumers that had already read the commit. Closed by moving the times on correction (D2).
- A report that should not exist had no exit. Closed by `withdraw` (D2).
- A provider missing from `cf` failed the whole call. Now a warning (D3).
- The integration check waited on a real design run in the PM's repos. Now automated (D7).
- The slice waited on 225's verdict, which the plan had already dropped. Removed (Dependencies).

## Risk Assessment

Agents may skip the rule blocks. The consumer block requires the Dependencies section to record the `changes` result or the error, so a skipped call shows in the design. No fallback mechanism is added. Report text reaches consumer agents with tools, but comes only from the PM's own member repos, and the consumer block asks the agent to judge it, not to obey it.

## Implementation Notes

Relative effort: 3.

1. `store/releases.py`, `Release`, and the D2 store-level tests, including `correct` and `withdraw`. Commit.
2. `parse_since` and the `decisions` switch, `report_release` with its modes and validation, and the `RejectCode` additions. Commit.
3. `changes` and its D3 tests. Commit.
4. Doors: names, `invoke` cases, CLI, MCP rows, stdio count. Commit.
5. `docs/program-rules.md` and its test; contract docs. Commit.
6. Flow test and live test. Commit.

### Pending Planning Edits

Applied to the parents at design time, so they match what this slice builds (nothing is left to a later step):

- `220-arch.program-tool.md`: the operations table (the modes of `report_release`), decision 3 (versioning replaces the text; correction and withdrawal), decision 4 (the explicit starting point and why the last merge is not used), and Anticipated Slices (no gate).
- `220-slices.program-tool.md` entry 9: the starting-point wording, and the integration criterion replaced by the automated flow and live tests (D7) plus a correction criterion.
