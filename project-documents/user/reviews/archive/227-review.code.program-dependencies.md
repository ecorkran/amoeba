---
docType: review
layer: project
reviewType: code
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/227-slice.program-dependencies.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 4f2588005a75884eb5de1a7e95396b9e374de4ff
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 42
diffTruncated: false
effort: xhigh
turns: 43
promptTokens: 2695888
cachedTokens: 2327876
cacheWriteTokens: 367988
completionTokens: 81052
durationSeconds: 354.4
costUsd: 0.695432
costBasis: provider
runId: run-20261114-p6-6b20c1ce
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: consistency-rot
    summary: "Helper imports placed after the `amoeba` import block in ten new test files"
    location: "tests/cli/test_release_cli.py:16"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "`_Model` base class copied into each models module"
    location: "src/amoeba/operations/changes_models.py:48"
  - id: F003
    severity: concern
    category: documentation-drift
    summary: "Concurrency test comment contradicts the timeout it cites"
    location: "tests/operations/test_report_release_concurrent.py:29-31"
  - id: F004
    severity: concern
    category: test-debt
    summary: "No load-tier test for the concurrent write path"
    location: "tests/operations/test_report_release_concurrent.py:1"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "Commit hash is validated for shape only"
    location: "src/amoeba/operations/report_release_models.py:71-79"
  - id: F006
    severity: note
    category: security-hygiene
    summary: "Version string printed without escaping"
    location: "src/amoeba/cli/render/releases.py:74"
  - id: F007
    severity: note
    category: security-hygiene
    summary: "f-string SQL in a test helper"
    location: "tests/operations/release_support.py:125"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Release SQL lives in a second module"
    location: "src/amoeba/store/release_sql.py"
  - id: F009
    severity: note
    category: performance-resource
    summary: "No index on the release range columns"
    location: "src/amoeba/store/release_sql.py"
  - id: F010
    severity: pass
    category: correctness
    summary: "`releases` table is in the baseline, so no migration is needed"
    location: "src/amoeba/store/schema/001_baseline.sql:43"
  - id: F011
    severity: pass
    category: correctness
    summary: "In-process operations run off the event loop"
    location: "src/amoeba/mcp/in_process.py:79"
---

# Review: code — slice 227

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 42 successful tool call(s) of 42 made; 172994 of 172994 diff characters reached the model

## Findings

### [CONCERN] Helper imports placed after the `amoeba` import block in ten new test files

`pyproject.toml:49` selects `I`, and there is no `src` override, so `store`, `operations`, `cli`, `program` and `live` resolve as third-party. Isort would move them above the `amoeba` block. The new files place them after it, while the pre-existing `tests/test_wiring.py` and the new `tests/mcp_server/test_release_tools.py` place them before. The other affected lines are `tests/operations/test_report_release.py:32`, `tests/operations/test_changes.py:38`, `tests/operations/test_report_release_concurrent.py:21`, `tests/operations/release_support.py:21`, `tests/program/test_program_flow.py:19`, `tests/store/test_pairs_consumed_by.py:15-16`, `tests/store/test_visible_releases.py:14`, `tests/store/test_releases.py:14` and `tests/live/program/test_program_dependencies_live.py:19`. Running `ruff check` on the branch should confirm this.

### [CONCERN] `_Model` base class copied into each models module

`changes_models.py:48` and `report_release_models.py:114` define the same `_Model(BaseModel)` with `ConfigDict(frozen=True, extra="forbid")`. The same base already exists in `decisions_models.py:19` and `status_models.py:23`. This slice adds a fourth copy. One shared base in a common operations module would replace all four.

### [CONCERN] Concurrency test comment contradicts the timeout it cites

The comment says the 20-second bound is "far below the store's busy timeout". `BUSY_TIMEOUT_SECONDS` is `5.0` (`src/amoeba/store/store.py:28`), so the bound is four times the timeout. The bound therefore cannot detect the lock contention the comment describes. Either the bound should be stated relative to the busy timeout or the comment should be corrected.

### [CONCERN] No load-tier test for the concurrent write path

The Python rules require a load test under `tests/load/` for code on concurrency paths, asserting latency, throughput or resource bounds, and gated in CI. `tests/load/` does not exist in this repo (the glob returns nothing). This slice adds cross-process `BEGIN IMMEDIATE` writes. The only coverage is eight threads asserting `elapsed < 20 s` in the unit tier, which is the weak assertion described above.

### [NOTE] Commit hash is validated for shape only

`_full_hash` checks length and hex characters and nothing else. Design line 89 specifies this, so it is consistent with the design. A well-formed but wrong hash is accepted, stored, and shown to every consumer. The only remedy is `--withdraw` with the same hash. Whether to add a `git cat-file -e` check in the provider's checkout is a design decision for you, not a defect against the design.

### [NOTE] Version string printed without escaping

`_tag_name` rejects whitespace only, so control characters pass validation. `_entry` then appends `report.version` to the printed line without cutting or escaping it. The risk is low, since the writer is another agent in the same organization, but stripping control characters at validation would close it.

### [NOTE] f-string SQL in a test helper

`table_dump` builds `SELECT * FROM "{table}"` with an f-string. The table name is checked against `user_tables` first and the statement is read-only, so there is no injection path. The SQL rules still say "never f-string SQL", so a fixed mapping of allowed table names would satisfy them without the check-then-interpolate pattern.

### [NOTE] Release SQL lives in a second module

The split is justified: `sql.py` is 396 lines. But `SELECT_PAIRS_CONSUMED_BY` was added to `sql.py` while the release statements went to `release_sql.py`. Choosing one home for new statements would remove the inconsistency.

### [NOTE] No index on the release range columns

The read queries filter on `member_id`, range over `reported_at` or `versioned_at`, and sort. The only index is the baseline `UNIQUE (member_id, commit_sha)`. The baseline is immutable, so an index would need a new migration. At the volume the design expects (one row per reported commit) this does not matter yet.

### [PASS] `releases` table is in the baseline, so no migration is needed

The table, its unique key, and the `members` foreign key were defined before this branch. The branch changes no schema file, so no migration is missing.

### [PASS] In-process operations run off the event loop

The MCP in-process runner calls `anyio.to_thread.run_sync`, so the `cf` subprocess calls in `changes` and `report_release` do not block the event loop.

### Run Digest

- Response length: 8926 chars
- Response is newline-free: no
- Tool calls made: 42
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 43
- Tokens — prompt / cached / cache write / completion / reasoning: 2695888 / 2327876 / 367988 / 81052 / not computed
- Duration: 354.4 s
- Cost: $0.70 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
