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
turns: 16
promptTokens: 1145403
cachedTokens: 1041810
cacheWriteTokens: 103561
completionTokens: 26445
durationSeconds: 284.1
costUsd: 1.566208
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.5662085
    completionTokens: 26445
---

# Slice Design: Program Dependencies

## Overview

Scenario B. A member repo tells the program what it released, and a member that depends on it reads those reports before designing a slice. Nobody relays anything.

- **`report_release`** records a release from the member's own checkout: commit, optional version, what changed, and what that touched. A report is keyed on member and commit. Repeating a report changes nothing. A version reported later for an already reported commit is added to that report.
- **`changes`** returns what this member's providers reported since a time the caller gives. Each dependency pair's `consumed` filters what it sees. Nothing is marked read.
- **Both doors.** Both operations are added to the CLI and to the MCP tool table, under the same names.
- **Rule lines.** `docs/program-rules.md` holds the text a member pastes into its own rules file: a consumer line, a provider line, and a release-skill line.

The slice adds no table and no migration. 222's baseline already has `dependency_pairs.consumed` and the `releases` table this slice writes.

**Gate.** The slice plan builds this only after 225's trial gives a go verdict. If the verdict is rethink, this design goes back to the PM before Phase 5.

## Value

User value. A repo designing a slice sees what changed in the repos it depends on without the PM carrying the news between repos, and a provider says what it changed once, in its own words. For a `from_release` consumer, unreleased work in a provider stays out of view until the provider publishes it.

## Technical Scope

**Included:**

- `store/releases.py` and a `Release` model: reads and writes of the `releases` table (D1, D2, D3).
- `operations/report_release.py`: `ReportReleaseRequest`, `ReportReleaseResult`, `report_release()` (D1, D2).
- `operations/changes.py`: `ChangesRequest`, `ChangesResult`, `changes()` (D3, D4).
- Two `OperationName` members, two CLI subcommands and two MCP tool rows (D5).
- `docs/program-rules.md` with the three rule lines (D6), and updates to `docs/store-contract.md`, the CLI contract and `docs/mcp-server.md` (D8).
- Tests (D7).

**Excluded:**

- Any change to `set_up`. Pairs and `consumed` are registered there already (222 D7).
- Marking reports read, notifying consumers, or walking the graph past direct providers (architecture: pull, never push; never walks the graph).
- Running `git` from Amoeba. The caller passes a full commit hash and a time, so Amoeba needs no git reader.
- A pipeline step that calls `changes`. That is `ecorkran/squadron#304`, on hold (Future Work 1 in the slice plan).
- Removing or correcting a report. A wrong report is rare and is fixed by hand in SQLite, like a wrong registration (222 Future Work).

## Dependencies

### Prerequisites

- **225 complete with a go verdict.** See the gate in Overview.
- **226 complete.** The tool table, `OperationName`, `wiring.py` and the parity tests exist.
- **222 and 224 complete** (transitively): the store, `resolve_member`, the `releases` and `dependency_pairs` tables, and `project_names` and `decisions` from 224.
- No new packages and no Squadron or Context Forge change.

### Interfaces Required

- **222:** `Store.open`, `Store.write()` and `Store.read()`; `resolve_member(store, directory, run) -> Member | NotInProgram | NotAProject`; `store.programs.pairs_of`; `ConsumedMode`; the `releases` table (`seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`, with `UNIQUE (member_id, commit_sha)`); the CLI exit-code constants.
- **224:** `project_names(run)`, and the `since` rule of 224 D5 (ISO-8601 with an offset, converted to the store's UTC text form, no offset is `malformed`). 224 names no function for that rule, so this slice writes it once as `operations/since.py` `parse_since()` and changes `decisions` to call it. 224's tests must pass unchanged.
- **226:** `OperationName`, `ToolSpec` with `takes_directory` and `RunMode.IN_PROCESS`, `wiring.default_deps()`, and `build_parser()`.

## Architecture

### Component Structure

```
src/amoeba/
├── store/
│   ├── models.py            # + Release
│   └── releases.py          # release_for_commit, release_for_version, insert_release,
│                            #   add_version, visible_releases (D2, D3)
├── operations/
│   ├── names.py             # + REPORT_RELEASE, CHANGES
│   ├── since.py             # parse_since(): 224 D5's rule, written once; decisions calls it
│   ├── report_release.py    # ReportReleaseRequest, ReportReleaseResult, report_release() (D1, D2)
│   └── changes.py           # ChangesRequest, ChangesResult, changes() (D3, D4)
├── cli/main.py              # + report_release and changes subcommands (D5)
└── mcp/tools.py             # + two in-process rows (D5)
docs/program-rules.md        # the three rule lines (D6)
```

Import direction is unchanged from 222 and 226: `cli` and `mcp` → `operations` → `store`, `upstream`. `store/releases.py` imports nothing from `operations`.

### Data Flow

**`amoeba report_release --commit <sha> [--version <v>] --changed <text> --touched <item> …`**, run in the provider's checkout:

1. The CLI builds a document from the flags and passes it, still unvalidated, to `report_release`. MCP passes its arguments the same way, with `directory` taken out (226 D5).
2. `report_release` validates the document into `ReportReleaseRequest` (D1). On failure it returns `rejected / malformed`.
3. It resolves the directory with `resolve_member`. All `cf` calls happen here, before the store is written. A directory that is not a member returns `rejected / not_a_member` with the resolution as detail.
4. In one `BEGIN IMMEDIATE` transaction it reads the member's report for that commit, and the report holding that version if one is given, applies D2's table, and writes or rolls back.
5. It returns `ReportReleaseResult` with the stored report after the call.

**`amoeba changes --since <iso-8601>`**, run in the consumer's checkout:

1. The document is validated into `ChangesRequest` (D3). A missing or offset-less `since` is `rejected / malformed`.
2. `resolve_member` gives the consumer. A non-member is `rejected / not_a_member`.
3. One read transaction reads the consumer's pairs (consumer = this member) and, for each pair, the provider's reports visible under its `consumed` since `since` (D3).
4. One `project_names` call gives provider names (224 D6).
5. It returns `ChangesResult`, one entry per pair, including pairs with nothing new. It writes nothing.

### State Management

- **Written:** `releases` rows, by `report_release` only.
- **Read:** `releases`, `dependency_pairs` and `members`.
- **Not stored:** what any consumer has seen. The caller's starting point is its own state, which it gets from its own git history (D4). So worktrees and parallel designs never hide changes from each other.

## Technical Decisions

### D1 — The release report request
Status: decided

`ReportReleaseRequest` is a frozen pydantic model with `extra="forbid"`:

| Field | Rule |
|---|---|
| `commit` | Required. Stripped and lowercased. It must be a full hash: 40 hex characters (SHA-1) or 64 (SHA-256). |
| `version` | Optional. Stripped and non-empty when given. It is stored as given, because a version string's format (`v1.2.3`, `1.2.3`, a date) belongs to the provider. |
| `changed` | Required. Stripped, non-empty text: what changed, for someone using this repo. |
| `touched` | Required. A list of at least one stripped, non-empty string: the things other repos use that the change touched (an interface, a command, a file format, a schema). Duplicates are removed and order is kept. Stored as a JSON array in `releases.touched`. |

- **Full hashes only.** An abbreviated hash would make two reports of one commit look like two commits, so the identity would drift. The rejection detail says that a full hash is required and that `git rev-parse` gives one. Amoeba doesn't resolve refs itself (Technical Scope).
- **`touched` is a list,** so a consumer agent can match it against what it uses without parsing prose. 222 left the column's form to this slice, and a JSON array fits 222 D3's rule because no constraint changes.

Rejected: making `touched` optional. A report that touches nothing other repos use should not be made, and the provider rule line says when to report.

### D2 — Report identity and repeats
Status: decided

A report is identified by member and commit (222's `UNIQUE (member_id, commit_sha)`), and holds the commit's current version. This is narrower than the architecture's and the plan's "member, commit and version": one commit has one report, and a later version on it replaces the earlier one rather than adding a second report. The schema 222 built allows only this, and it covers the flows the architecture names (repeats, and a tag on a reported commit) as well as a release candidate promoted to final on the same commit. A version belongs to at most one commit per member. Inside the transaction, with `stored` being the member's report for `commit`:

| Case | Outcome | Write |
|---|---|---|
| The request's version is already on another commit of this member | `rejected / version_conflict` | None |
| No `stored` | `recorded` | Insert. `reported_at` is now. `versioned_at` is now if a version is given, else null. |
| The request gives a version different from `stored`'s (or `stored` has none) | `versioned` | Set `version` and `versioned_at` to now, and replace `changed` and `touched` with the request's. |
| Anything else (no new version) | `unchanged` | None |

- **A repeat is `unchanged` whatever its wording.** Agents rephrase, so a second merge report of one commit with different text must not fail or rewrite the record. The result always carries the stored report, so the caller sees what stands.
- **Adding a version replaces the text.** A release covers every merge since the previous release, and the release-skill line asks for a description of all of it (D6). A `from_release` consumer then sees that summary, not the text of the last merge alone. `reported_at` is unchanged, so a `from_source` consumer who already saw the commit does not see it again (D3). The merge-time text is lost from the record. That costs little, because the `from_source` consumers it was for have already read it, and keeping both texts would need two more columns and a rule for which one each consumer sees.
- **A later version on a versioned commit** (a release candidate promoted to final) moves `versioned_at`, so `from_release` consumers see the report again with the new version. `from_source` consumers don't, because `reported_at` doesn't move. The earlier version label is not kept.
- **A version moved to another commit is refused, not repaired.** It is rare and means something went wrong in the provider. The detail names the stored report, and the fix is by hand.
- **Only a tag on the reported commit merges.** If the release flow adds its own commit (a version bump, for example), the tag's commit is new, so the release is a second report. A `from_source` consumer then sees both the merge report and the release report, and a `from_release` consumer sees only the release. `docs/program-rules.md` says so (D8).
- **Concurrent reports** of one commit are serialized by `BEGIN IMMEDIATE`. The second sees the first's row and follows the table. `UNIQUE (member_id, commit_sha)` is the backstop, and an `IntegrityError` there is a bug and is not caught.

`ReportReleaseResult`: `outcome` (`recorded`, `versioned`, `unchanged`, `rejected`), `member` (the CF project id, or null when not a member), `report` (the stored row after the call: `seq`, `commit`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`, or null if none exists), and `problems` (`code`: `malformed`, `not_a_member` or `version_conflict`, and `detail`; empty unless rejected). The outcome and problem codes are `StrEnum`s in `report_release.py`.

### D3 — What `changes` returns
Status: decided

`ChangesRequest`: `since`, required, validated by `parse_since` (224 D5's rule). The request takes no member or program. The member is the caller's directory, as the architecture says for callers inside a repo.

For each pair where the caller is the consumer, the provider's reports are visible when:

| `consumed` | Visible when | Ordered by |
|---|---|---|
| `from_source` | `reported_at >= since` | `reported_at`, then `seq` |
| `from_release` | `version IS NOT NULL AND versioned_at >= since` | `versioned_at`, then `seq` |

- This gives the plan's criteria directly. A `from_release` consumer sees a merge report only once it has a version. A `from_source` consumer whose `since` falls between the merge report and the tag doesn't see the tag, because `reported_at` didn't move. One whose `since` is earlier sees one entry, carrying the version.
- `>=` matches 224's `decisions`, so a report made in the same second as the starting point is shown, not lost.
- **Nothing is marked read,** and `changes` writes nothing. Two worktrees with different `since` values each get everything after their own point.
- **Every pair is listed,** including pairs with no visible reports, so the caller can tell "checked, nothing new" from "not a dependency". A member with no providers gets an empty `pairs` list, which is a result, not a rejection.
- **A member's reports never reach a non-consumer.** Only direct pairs are read. A provider's own providers are not followed.

`ChangesResult`: `member` (`{id, name}`), `since` (the normalized UTC value used), `pairs` (each `{provider: {id, name}, consumed, releases: [...]}`, where a release has the fields of D2's `report`), and `problems` with `outcome` `listed` or `rejected` (`malformed`, `not_a_member`). Provider names come from one `project_names` call. A provider id missing from Context Forge's list is a `ContextForgeError`, as in 224 D6.

### D4 — The starting point belongs to the caller
Status: decided

Amoeba stores no read position. The consumer rule line (D6) tells the design agent how to get its `since`: the committer time of the commit that added the most recent slice design on its branch, `git log -1 --diff-filter=A --format=%cI -- project-documents/user/slices/`. When that prints nothing, the fallback is the time of the earliest root commit, `git log --max-parents=0 --reverse --format=%cI | head -1`, which also handles a repo with several roots. The agent runs it before committing its own design.

- **Why the previous design, not the last merge.** The architecture says "usually its branch's last merge". That point misses scenario B's ordinary timing: a provider reports while the consumer is implementing a slice, after that slice's design and before its merge, and the next design's `since` would fall after the report. Starting from the previous design's creation covers that window, at the cost of re-showing reports the previous design already saw. It errs toward showing more, as the architecture intends.
- **Still soft.** A rebase or cherry-pick moves `%cI` later. The path is the project guide's layout, which members share.
- **Same clock.** The store is per-user and local, so report times and the consumer's commit times come from the same machine's clock. `%cI` carries an offset, which `parse_since` requires.

Rejected: a per-member or per-worktree read marker in the store. It would hide a change from a parallel worktree once another had read it, which is the problem the architecture names. Rejected: accepting a commit ref and resolving it with `git`. That adds a git reader to save the agent one command that the rule line spells out.

### D5 — The two doors
Status: decided

- `OperationName` gains `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"`. The CLI subcommands and MCP tool names come from these, so 226's name-parity test covers them unchanged.
- **CLI.**
  ```
  amoeba report_release --commit <sha> [--version <v>] --changed <text> --touched <item> [--touched <item> …]
  amoeba changes --since <iso-8601>
  ```
  Flags map one-to-one onto request fields, as 223's `answer` does. The CLI builds the document and the operation validates it, so a missing `--touched` reaches the operation as a missing field and comes back `rejected / malformed` with the same detail the MCP door gives. The flags are not marked required in argparse for that reason.
  Exit codes use 222's constants: `0` for `recorded`, `versioned`, `unchanged` or `listed`; `1` for `rejected`; `2` for a usage error; `3` for an operational error (`ContextForgeError`, `ConfigError`, `AmoebaHomeError`, any `StoreError`).
- **MCP.** Two `ToolSpec` rows: `report_release` and `changes`, both `RunMode.IN_PROCESS` with `takes_directory = True`. Each is a short store call plus `cf` calls, so neither is long work. `directory` is required and absolute (226 D5). The tool descriptions say what each does and that `changes` marks nothing read, and contain no example values.
- `report_release` and `changes` need the user config only because `wiring` loads it for every call. They read no config key.

### D6 — The rule lines
Status: decided

`docs/program-rules.md` holds three blocks of text, each meant to be pasted whole. The doc says where each goes, and that a repo outside a program carries none of them. The wording is the doc's. Each block must carry these instructions:

- **Consumer** (rules file of a member with providers): before designing a slice, call `changes` (CLI in this checkout, or the MCP tool with this checkout's absolute path as `directory`), with `since` from D4's command, or D4's fallback command when the first prints nothing. Judge each report against the slice. In the design's Dependencies section, list the reports that affect it and how, or state that none do. Stop with a question or a `BLOCKED:` line if a report means the slice can't be designed as planned. Record a failed call's error there, and never treat it as "no changes".
- **Provider** (rules file of a member others depend on): right after a slice merge into the target that changes something other repos use (an interface, a command, a file format, a schema, or behavior they rely on), call `report_release` with `--commit` from `git rev-parse HEAD`, `--changed` for someone using this repo, one `--touched` per thing changed, and no `--version`. On a non-zero exit, record the error in the task notes and don't retry with different values.
- **Release skill** (after the tag step): skip if the release changed nothing other repos use. Otherwise call `report_release` with `--commit` from `git rev-list -n 1` for the new tag, `--version` as the tag's name, `--changed` summarizing everything since the previous release, and one `--touched` per thing changed. Report a non-zero exit with the release result.

- **Why the design's Dependencies section.** `changes` writes nothing, so the design document is the only place that shows the line was followed. It is also where the finding belongs. The plan's last criterion and 225-style evidence both read from it.
- **No example values.** Each value the agent passes comes from a named command, and no sample hash, time or version is printed near it (project rules, hallucination traps).

### D7 — Tests
Status: decided

All are in the default suite and use the autouse `AMOEBA_HOME` fixture and 222's fake `cf`.

- **Request validation:** an abbreviated hash, a non-hex hash, empty `changed`, empty or missing `touched`, a blank `version`, and a `since` with no offset are each `malformed`. An upper-case full hash is stored lower-cased. Duplicate `touched` items are removed with their order kept.
- **D2 table:** one test per row, each asserting the outcome and the stored row, including a second version on a versioned commit, which moves `versioned_at`. A rephrased repeat is `unchanged` and keeps the stored text.
- **D3 visibility,** on a fixture program with one provider and two consumers, `from_source` and `from_release`, with rows seeded at chosen times through `store/releases.py`, whose writes take the time as an argument:
  - a merge report is seen by the `from_source` consumer and not by the `from_release` one;
  - after the version is added, the `from_release` consumer sees it with the release text;
  - a `from_source` consumer with `since` between the report and the tag sees nothing, and one with an earlier `since` sees one entry with the version;
  - two calls with different `since` values each see everything after their own point, and a call between them changes neither;
  - a provider's provider is never listed; a member with no providers gets empty `pairs`.
- **Non-members:** both operations return `not_a_member` for a CF project in no program and for a directory in no project, and write nothing. A `cf` failure is `ContextForgeError`, exit 3.
- **Doors:** 226's name and function tests cover the new rows. 226's stdio test asserts a literal six tools, so this slice changes that assertion to one tool per `OperationName` member. This is the one edit to a 226 test. One CLI test per subcommand checks exit codes 0 and 1 and that a repeated `--touched` reaches the request as a list.
- **Rule lines:** a test checks that `docs/program-rules.md` contains the three blocks, that each names the operation and its CLI flags as `build_parser()` defines them, that the consumer block contains both of D4's commands, and that it contains no 40-hex string. So a renamed flag breaks the test, not the agents.

### D8 — Contract docs
Status: decided

- `docs/store-contract.md`: `releases` is written by `report_release`. It documents `touched` as a JSON array of strings, D2's identity and repeat rules, and that nothing records reads.
- The CLI contract: the two subcommands, their flags, results and exit codes.
- `docs/mcp-server.md`: the tool list gains the two tools.
- `docs/program-rules.md`: D6, plus a pointer to 222's `set_up` contract for choosing `consumed`, and one sentence saying that a release report merges with a merge report only when the tag is on the reported commit (D2).

### Technology Choices

No new packages. pydantic request and result models, `sqlite3` through 222's store, `argparse` through the existing parser.

### Patterns and Conventions

- Outcome and problem codes are `StrEnum`s defined once. The visibility rules in D3 are one function, `visible_releases(tx, provider_id, consumed, since)`, with one branch per `ConsumedMode`.
- `report_release` takes the current UTC time once per call and passes it to the store writes, in the store's UTC text form.
- Files stay under ~300 lines and functions under ~50.

## Implementation Details

### API Contracts

**CLI:** D5.

**`report_release` result (JSON):**

```json
{"outcome": "versioned",
 "member": "<cf project id>",
 "report": {"seq": 0, "commit": "<full hash>", "version": "<tag>",
            "changed": "<text>", "touched": ["<item>"],
            "reported_at": "<UTC ISO-8601>", "versioned_at": "<UTC ISO-8601>"},
 "problems": []}
```

**`changes` result (JSON):**

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

**MCP:** inputs are the request models plus `directory`, and results are the same JSON (226 D5, D7).

**Python:** `report_release(store, document, *, directory, deps) -> ReportReleaseResult` and `changes(store, document, *, directory, deps) -> ChangesResult`, where `deps` supplies the `cf` runner.

### Database / Storage Schema

No change. The slice writes 222's `releases` columns as D2 describes and stores `touched` as a JSON array.

## Integration Points

### Provides to Other Slices

- `report_release`, `changes` and the rule-line text. No later slice in this plan consumes them. Future Work 1 in the slice plan (a pipeline step through `#304`) would call `changes` the same way the rule line does.

### Consumes from Other Slices

- **222:** the tables, `resolve_member`, the store transactions and `pairs_of`. Pairs registered through `set_up` are the only input to `changes`. A member registered with no `depends_on` sees empty `pairs`.
- **224:** `project_names`, and the `since` rule, which this slice writes as `operations/since.py` and `decisions` then calls, with 224's tests unchanged.
- **226:** the tool table and parity tests.
- **225:** the go verdict, and the registered trading program, which the walkthrough extends with pairs.

## Success Criteria

### Functional Requirements

- `report_release` records a report from a member's checkout. A repeat with any wording returns `unchanged`. A version on an unversioned commit returns `versioned` and replaces the text. A different version on a versioned commit returns `versioned`. A version already on another commit is rejected as `version_conflict` with the stored report.
- A `from_source` consumer sees a provider's merge report. A `from_release` consumer sees it only once it has a version.
- Tagging a release on an already reported commit adds the version, and a `from_source` consumer whose `since` is after the merge report does not see it again.
- Two worktrees calling `changes` with different `since` values each see everything since their own point.
- Both operations are available on the CLI and over MCP, with the same inputs and results.
- A caller outside every program gets `not_a_member` and nothing is written.

### Technical Requirements

- Format, lint, pyright (strict) and the full default suite pass, including D7's tests and 226's parity tests.
- No migration is added, and `EXPECTED_SCHEMA_VERSION` is unchanged.
- The contract docs and `docs/program-rules.md` match the code (D8).

### Integration Requirements

- The rule lines, pasted into two of the PM's member repos, lead a design agent to call `changes` in a real design run, and the resulting design's Dependencies section records what it returned. This waits on a real provider merge and a real design (walkthrough step 6). The merge does not wait for it, but the slice is not complete until it is recorded.

### Verification Walkthrough

Draft. Steps 2 to 5 use a scratch home and the trading repos from 225 D1 (`trading-data` as provider, `trading-engine` and `trading-ui` as consumers), so the real store is untouched. `amoeba` is the tool installed in 225 D2 (`uv tool install --force <amoeba repo>` from this slice's branch). Step 6 uses the real store. D7's tests cover differing starting points, non-members and the MCP door, so they are not repeated here.

1. **Checks.**
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   ```
   All pass.

2. **Scratch program with pairs.** In `trading-data`:
   ```bash
   export AMOEBA_HOME="$(mktemp -d)"
   cp ~/.config/amoeba/config.yaml "$AMOEBA_HOME/"
   amoeba set_up --file - <<'EOF'
   program: trading
   members:
     - rules_paths: [CLAUDE.md]
     - project: trading-engine
       rules_paths: [CLAUDE.md]
       depends_on: [{provider: trading-data, consumed: from_source}]
     - project: trading-ui
       rules_paths: [CLAUDE.md]
       depends_on: [{provider: trading-data, consumed: from_release}]
   EOF
   ```
   Expect `applied`. Keep `AMOEBA_HOME` exported in every terminal used below.

3. **A merge report.** In `trading-data`:
   ```bash
   T0="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
   amoeba report_release --commit "$(git rev-parse HEAD)" --changed "walkthrough report" --touched "walkthrough item"
   ```
   Expect `recorded`, with `version` and `versioned_at` null. Run it again with `--changed "reworded"`: `unchanged`, and the `report` still shows `walkthrough report`. Run it with `--commit "$(git rev-parse --short HEAD)"`: exit 1, `malformed`, with the detail asking for a full hash.

4. **Who sees it.** In `trading-engine`, `amoeba changes --since "$T0"`: one `trading-data` pair, `from_source`, with the report. In `trading-ui`, the same command lists the `from_release` pair with no releases.

5. **The tag.** In `trading-data`:
   ```bash
   T1="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
   amoeba report_release --commit "$(git rev-parse HEAD)" --version walkthrough-1 --changed "walkthrough release" --touched "walkthrough item"
   ```
   Expect `versioned`, with the release text. Then:
   - In `trading-ui`, `amoeba changes --since "$T0"` shows the report with `version: walkthrough-1`.
   - In `trading-engine`, `amoeba changes --since "$T1"` shows no releases, and `--since "$T0"` shows exactly one entry, now carrying the version.
   - In `trading-data`, the same command with `--version walkthrough-2` gives `versioned`, and `trading-ui` sees the report again with that version.

6. **Rule lines in real use.** `unset AMOEBA_HOME`. Add the pairs from step 2 to the real `trading` program with `amoeba set_up`. Paste the provider line into `trading-data`'s rules file and its release skill, and the consumer line into the rules files of `trading-engine` and `trading-ui`. After `trading-data`'s next slice merges with a change the others use, check `amoeba changes --since <time before the merge>` from `trading-engine` lists its report. Then run a real slice design in `trading-engine`. Confirm that the design's Dependencies section records what `changes` returned. Note in the task notes, as evidence for `#304`, any design that didn't call `changes` and any provider report it should have seen and didn't.

## Risk Assessment

### Technical Risks

- **Agents skip the rule lines.** Nothing forces a design agent to call `changes`, or a provider to report. The architecture accepts this.

### Mitigation Strategies

- The consumer line asks the agent to record the result in the design, so a skipped call is visible in the document. If designs keep missing it, Future Work 1 (a pipeline step through `#304`) is the fallback.

## Implementation Notes

### Development Approach

Relative effort: 3.

1. `store/releases.py` and the `Release` model, with the D2 table tests at store level.
2. `operations/since.py`, with `decisions` switched to it, and `operations/report_release.py`, with validation and non-member tests. Commit.
3. `operations/changes.py` with the D3 visibility tests.
4. `OperationName` members, CLI subcommands and MCP rows, with the CLI tests and the updated stdio count. Commit.
5. `docs/program-rules.md` and its test, and the contract doc updates. Commit.
6. Walkthrough steps 2 to 5. They gate the code review and the merge.
7. Walkthrough step 6 needs a real provider merge and a real design, so it runs when those happen. The slice is not complete until its result is in the task notes, because the plan's last criterion rests on it. The merge does not wait for it.

### Pending Planning Edits

Two decisions depart from the parent documents. Each needs a one-line planning edit to `220-arch.program-tool.md` (decisions 3 and 4) and slice plan entry 8, made outside this slice like the plan's concept-wording edit:

- **Report identity** (D2): member and commit, holding the commit's current version, instead of "member, commit and version".
- **Starting point** (D4): the creation of the previous slice design, instead of "usually its branch's last merge".

### Special Considerations

- **What a report can reach.** Report text is read by consumer design agents, which have tools. It comes only from the PM's own member repos, through their own agents, the same trust level as their rules files. Amoeba doesn't screen it, and the consumer line asks the agent to judge, not obey, what it reads.
- **Store growth.** One row per reported commit. Not a concern at this scale.
