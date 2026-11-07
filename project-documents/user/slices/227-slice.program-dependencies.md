---
docType: slice-design
slice: program-dependencies
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 224-slice.status-and-decisions
- 225-slice.scenario-a-trial
- 226-slice.mcp-server
interfaces: []
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
---

# Slice Design: Program Dependencies

## Overview

Scenario B. A provider repo reports what it released, and a consumer reads those reports before designing a slice. Nobody relays anything.

- **`report_release`** records a release from the member's own checkout (D1, D2).
- **`changes`** returns what this member's providers reported since a time the caller gives, filtered by each pair's `consumed`. Nothing is marked read (D3, D4).
- Both are added to the CLI and the MCP tool table under the same names (D5).
- `docs/program-rules.md` holds the two rule lines a member pastes into its rules file (D6).

No table or migration: 222's baseline already has `dependency_pairs.consumed` and `releases`.

**Gate.** Built only after 225's trial gives a go verdict. On a rethink verdict this design goes back to the PM.

## Value

User value. A repo designing a slice sees what changed in the repos it depends on without the PM relaying it. A `from_release` consumer doesn't see a provider's unreleased work.

## Technical Scope

**Included:** `store/releases.py` and a `Release` model; `operations/report_release.py`; `operations/changes.py`; `operations/since.py`; two `OperationName` members, CLI subcommands and MCP rows; `docs/program-rules.md`; contract doc updates (D8); tests (D7).

**Excluded:**

- Any change to `set_up`. Pairs and `consumed` are registered there already (222 D7).
- Marking reports read, notifying consumers, or reading past direct providers (architecture: pull, never walks the graph).
- Running `git` from Amoeba. The caller passes a full hash and a time.
- A pipeline step that calls `changes` (`ecorkran/squadron#304`, slice plan Future Work 1).
- Removing or correcting a report. Rare; fixed by hand in SQLite, like a wrong registration.

## Dependencies

- **225** with a go verdict. **226**: `OperationName`, `ToolSpec` (`takes_directory`, `RunMode.IN_PROCESS`), `wiring.default_deps()`, `build_parser()`, parity tests.
- **222**: `Store.open`/`write()`/`read()`, `resolve_member`, `store.programs.pairs_of`, `ConsumedMode`, the `releases` table (`seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`, `UNIQUE (member_id, commit_sha)`), CLI exit-code constants.
- **224**: `project_names(run)`, and 224 D5's `since` rule (ISO-8601 with an offset, converted to the store's UTC text; no offset is `malformed`). 224 has no function for it, so this slice writes `operations/since.py` `parse_since()` and switches `decisions` to it. 224's tests pass unchanged.
- No new packages, no Squadron or Context Forge change.

## Architecture

```
src/amoeba/
├── store/models.py          # + Release
├── store/releases.py        # release_for_commit, insert_release, add_version, visible_releases
├── operations/names.py      # + REPORT_RELEASE, CHANGES
├── operations/since.py      # parse_since(); decisions calls it too
├── operations/report_release.py
├── operations/changes.py
├── cli/main.py              # + two subcommands
└── mcp/tools.py             # + two rows
docs/program-rules.md
```

Import direction is unchanged: `cli`, `mcp` → `operations` → `store`, `upstream`.

**Flow.** Each operation validates the unvalidated document from either door into its request model (`rejected / malformed` on failure), then resolves the directory with `resolve_member` (`rejected / not_a_member` with the resolution as detail). All `cf` calls happen before the store is touched. `report_release` then applies D2 in one `BEGIN IMMEDIATE` transaction. `changes` reads pairs and visible reports in one read transaction, gets names from one `project_names` call, and writes nothing.

**State.** `releases` is written only by `report_release`. No read position is stored; the caller's starting point comes from its own git history (D4).

## Technical Decisions

### D1 — The release report request

`ReportReleaseRequest`, frozen pydantic, `extra="forbid"`:

| Field | Rule |
|---|---|
| `commit` | Required, stripped, lowercased. Full hash only: 40 or 64 hex characters. An abbreviated hash would split one commit into two reports. The rejection detail says `git rev-parse` gives a full hash. |
| `version` | Optional; stripped, non-empty when given. Stored as given. |
| `changed` | Required, non-empty: what changed, for someone using this repo. |
| `touched` | Required list of at least one non-empty string: the things other repos use that the change touched. Deduplicated, order kept. Stored as a JSON array, so a consumer agent can match items without parsing prose. |

### D2 — Report identity and repeats

A report is identified by member and commit, and holds the commit's current version. With `stored` being the member's report for `commit`:

| Case | Outcome | Write |
|---|---|---|
| No `stored` | `recorded` | Insert. `reported_at` now; `versioned_at` now if a version is given, else null. |
| A version different from `stored`'s, or `stored` has none | `versioned` | Set `version`, `versioned_at` to now, and replace `changed` and `touched`. |
| Anything else | `unchanged` | None |

- A repeat is `unchanged` whatever its wording, since agents rephrase. The result always carries the stored report.
- Versioning replaces the text because a release describes everything since the previous release. `reported_at` doesn't move, so `from_source` consumers don't see the commit again (D3).
- Only a tag on the reported commit merges into a report. A release flow that adds its own commit makes a second report.
- `BEGIN IMMEDIATE` serializes concurrent reports of one commit. An `IntegrityError` on the unique key is a bug and is not caught.

`ReportReleaseResult`: `outcome` (`recorded`, `versioned`, `unchanged`, `rejected`), `member` (CF project id or null), `report` (`seq`, `commit`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`, or null), `problems` (`code`: `malformed` or `not_a_member`, and `detail`). Codes are `StrEnum`s.

### D3 — What `changes` returns

`ChangesRequest`: `since`, required, validated by `parse_since`. The member is the caller's directory.

For each pair where the caller is the consumer, one function `visible_releases(tx, provider_id, consumed, since)` selects:

| `consumed` | Visible when | Ordered by |
|---|---|---|
| `from_source` | `reported_at >= since` | `reported_at`, `seq` |
| `from_release` | `version IS NOT NULL AND versioned_at >= since` | `versioned_at`, `seq` |

Every pair is listed, including those with nothing visible, so "checked, nothing new" differs from "not a dependency". A member with no providers gets empty `pairs`, not a rejection.

`ChangesResult`: `outcome` (`listed`, `rejected`), `member` (`{id, name}`), `since` (normalized UTC), `pairs` (each `{provider: {id, name}, consumed, releases: [report as in D2]}`), `problems` (`malformed`, `not_a_member`). A provider id missing from Context Forge's list is a `ContextForgeError`, as in 224 D6.

### D4 — The starting point belongs to the caller

Amoeba stores no read marker, so parallel worktrees never hide changes from each other. The consumer's `since` is the committer time of the commit that added the most recent slice design on its branch:

    git log -1 --diff-filter=A --format=%cI -- project-documents/user/slices/

If that prints nothing (no previous design), use the earliest root commit's time, which also handles several roots:

    git log --max-parents=0 --reverse --format=%cI | head -1

The agent runs it before committing its own design. This departs from the architecture's "usually its branch's last merge": a provider often reports while the consumer implements, after its design and before its merge, and the last merge would miss that report.

### D5 — The two doors

- `OperationName` gains `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"`; 226's name-parity test covers them.
- **CLI:**
  ```
  amoeba report_release --commit <sha> [--version <v>] --changed <text> --touched <item> [--touched <item> …]
  amoeba changes --since <iso-8601>
  ```
  Flags map one-to-one onto request fields and are not marked required in argparse, so a missing field is rejected by the operation with the same detail on both doors. Exit codes: `0` for any non-rejected outcome, `1` rejected, `2` usage, `3` operational error (`ContextForgeError`, `ConfigError`, `AmoebaHomeError`, `StoreError`).
- **MCP:** two `RunMode.IN_PROCESS` rows with `takes_directory = True`; `directory` is required and absolute (226 D5). Descriptions contain no example values.

### D6 — The rule lines

`docs/program-rules.md` holds two blocks, each pasted whole, and says where each goes. A repo outside a program carries neither. The text is:

**Consumer** (rules file of a member with providers):

> Before designing a slice, check Amoeba for changes in what this repo depends on. Run `amoeba changes --since <time>` in this checkout, or call the `changes` MCP tool with this checkout's absolute path as `directory`. Take `<time>` from `git log -1 --diff-filter=A --format=%cI -- project-documents/user/slices/`; if that prints nothing, take it from `git log --max-parents=0 --reverse --format=%cI | head -1`. Judge each report against the slice. In the design's Dependencies section, list the reports that affect the slice and how, or state that none do. If a report means the slice cannot be designed as planned, stop with a question or a `BLOCKED:` line. If the call fails, record its error in the Dependencies section; never treat a failed call as no changes.

**Provider** (rules file of a member others depend on, and the repo's release skill after its tag step):

> When a slice merge into the target, or a release, changes something other repos use (an interface, a command, a file format, a schema, or behavior they rely on), run `amoeba report_release` in this checkout. Pass `--commit` as the full hash of the merged commit (`git rev-parse HEAD`), or for a release the tagged commit (`git rev-list -n 1 <tag name>`). Pass `--version` as the tag name for a release, and omit it otherwise. Pass `--changed` as what changed, for someone using this repo; for a release, cover everything since the previous release. Pass one `--touched` per thing changed. On a non-zero exit, record the error in the task notes or the release result, and do not retry with different values.

The design's Dependencies section is where the consumer records the result, because `changes` writes nothing and the plan's last criterion reads from it. No sample hash, time or version appears near any value the agent must fetch (project rules, hallucination traps).

### D7 — Tests

Default suite, autouse `AMOEBA_HOME` fixture, 222's fake `cf`.

- **Validation:** abbreviated or non-hex hash, empty `changed`, empty or missing `touched`, blank `version`, offset-less `since` are each `malformed`. Upper-case hash stored lowercased; duplicate `touched` removed in order.
- **D2:** one test per row, asserting outcome and stored row, including a second version on a versioned commit. A rephrased repeat keeps the stored text.
- **D3,** one provider with a `from_source` and a `from_release` consumer, rows seeded at chosen times (store writes take the time as an argument): the merge report reaches only `from_source`; after versioning `from_release` sees it with the release text; a `from_source` `since` between report and tag sees nothing, an earlier one sees one entry with the version; two `since` values each see everything after their own point; a provider's provider is never listed; no providers gives empty `pairs`.
- **Non-members:** both operations return `not_a_member` and write nothing. A `cf` failure exits 3.
- **Doors:** 226's parity tests cover the rows. 226's stdio test's literal tool count becomes one per `OperationName` member (the one edit to a 226 test). One CLI test per subcommand for exits 0 and 1 and a repeated `--touched` arriving as a list.
- **Rule lines:** `docs/program-rules.md` has both blocks, each names its operation and flags as `build_parser()` defines them, the consumer block has both D4 commands, and neither contains a 40-hex string.

### D8 — Contract docs

- `docs/store-contract.md`: `releases` written by `report_release`, `touched` as a JSON array, D2's rules, no read record.
- The CLI contract and `docs/mcp-server.md`: the two operations.
- `docs/program-rules.md`: D6, a pointer to 222's `set_up` contract for choosing `consumed`, and the D2 note that a release merges with a merge report only when the tag is on the reported commit.

## Implementation Details

**`changes` result (JSON).** A `report_release` result has the same `report` object.

```json
{"outcome": "listed",
 "member": {"id": "<cf project id>", "name": "<cf name>"},
 "since": "<UTC ISO-8601>",
 "pairs": [{"provider": {"id": "<cf project id>", "name": "<cf name>"},
            "consumed": "from_release",
            "releases": [{"seq": 0, "commit": "<full hash>", "version": "<tag>",
                          "changed": "<text>", "touched": ["<item>"],
                          "reported_at": "<UTC ISO-8601>", "versioned_at": "<UTC ISO-8601>"}]}],
 "problems": []}
```

**Python:** `report_release(store, document, *, directory, deps)` and `changes(store, document, *, directory, deps)`. `report_release` takes the UTC time once per call and passes it to the store writes.

## Success Criteria

- A `from_source` consumer sees a provider's merge report; a `from_release` consumer sees it only once it has a version.
- Tagging a release on an already reported commit adds the version; a `from_source` consumer does not see it twice.
- Two worktrees calling `changes` from different starting points each see everything since their own point.
- Both operations work on the CLI and over MCP with the same inputs and results. A caller outside every program gets `not_a_member` and nothing is written.
- Format, lint, pyright (strict) and the full default suite pass. No migration; `EXPECTED_SCHEMA_VERSION` unchanged. Docs match the code (D8).
- **Integration:** the rule lines, pasted into two of the PM's member repos, lead a design agent to call `changes` in a real design run, and the design's Dependencies section records the result (walkthrough step 5). The merge does not wait for this, but the slice is not complete until it is recorded.

### Verification Walkthrough

Steps 2 to 4 use a scratch `AMOEBA_HOME` and 225's trading repos (`trading-data` provider; `trading-engine` `from_source`, `trading-ui` `from_release`), with `amoeba` installed from this slice's branch as in 225 D2.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest` passes.
2. `export AMOEBA_HOME="$(mktemp -d)"`, copy the user config into it, and `amoeba set_up` the trading program with the two pairs. Expect `applied`.
3. In `trading-data`, record `T0` with `date -u +%Y-%m-%dT%H:%M:%S+00:00`, then `amoeba report_release --commit "$(git rev-parse HEAD)" --changed "walkthrough report" --touched "walkthrough item"`: `recorded`, version null. Repeat with other text: `unchanged`, text kept. With `--commit "$(git rev-parse --short HEAD)"`: exit 1, `malformed`. `amoeba changes --since "$T0"` shows the report in `trading-engine` and an empty pair in `trading-ui`.
4. Record `T1`, then report the same commit with `--version walkthrough-1` and new text: `versioned`. `trading-ui` now sees it with the version; `trading-engine` sees nothing since `T1` and one entry since `T0`.
5. Real use: unset `AMOEBA_HOME`, add the pairs to the real program, paste the provider line into `trading-data`'s rules file and release skill and the consumer line into the other two. After a real provider merge that others use, run a real design in `trading-engine` and confirm its Dependencies section records what `changes` returned. Note any design that skipped the call, as evidence for `#304`.

## Risk Assessment

Agents may skip the rule lines; the architecture accepts this. The consumer line makes a skipped call visible in the design, and Future Work 1 (`#304`) is the fallback. Report text reaches consumer agents with tools, but comes only from the PM's own member repos, and the consumer line asks the agent to judge it, not obey it.

## Implementation Notes

Relative effort: 3.

1. `store/releases.py` and `Release`, with D2 tests at store level.
2. `operations/since.py` (switch `decisions`), `operations/report_release.py`, validation and non-member tests. Commit.
3. `operations/changes.py` with D3 tests.
4. Doors, CLI tests, stdio count. Commit.
5. `docs/program-rules.md` and its test, contract docs. Commit.
6. Walkthrough steps 2 to 4 gate review and merge. Step 5 runs when a real provider merge and design happen; its result goes in the task notes.

### Pending Planning Edits

- **Starting point** (D4): the creation of the previous slice design, instead of "usually its branch's last merge". A one-line edit to `220-arch.program-tool.md` (decision 4, consumer rule) and slice plan entry 8, made outside this slice.
