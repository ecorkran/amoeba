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
reviewedSha: f799ed7f93f6c1d1b32eb5542c5dbf5cec027afb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
diffTruncated: false
effort: xhigh
turns: 37
promptTokens: 3549455
cachedTokens: 3212859
cacheWriteTokens: 336562
completionTokens: 66659
durationSeconds: 306.2
costUsd: 0.593589
costBasis: provider
runId: run-20261114-p6-6b20c1ce
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: security-hygiene
    summary: "`version` accepts whitespace and newlines, and the text renderer prints it unescaped"
    location: "src/amoeba/operations/report_release_models.py:58"
  - id: F002
    severity: concern
    category: test-debt
    summary: "No load test covers the new concurrent write path"
    location: "src/amoeba/operations/report_release.py:96"
  - id: F003
    severity: note
    category: type-contract-debt
    summary: "The renderer's `_rejected` fallback hides a missing invariant"
    location: "src/amoeba/cli/render/releases.py:31"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Duplicated rejection and validation code across two operations"
    location: "src/amoeba/operations/report_release.py#report_release"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "Size guidance is exceeded in shared files"
    location: "src/amoeba/wiring.py#invoke"
  - id: F006
    severity: note
    category: other
    summary: "A consumer silently loses reports from a removed provider"
    location: "src/amoeba/operations/changes.py#changes"
  - id: F007
    severity: note
    category: performance-resource
    summary: "`changes` fetches every pair in the program, then filters in Python"
    location: "src/amoeba/operations/changes.py:63"
  - id: F008
    severity: note
    category: error-handling-observability
    summary: "A swallowed failure in the live consumer setup"
    location: "tests/live/program/consumer.py:48"
  - id: F009
    severity: note
    category: security-hygiene
    summary: "Test helper builds SQL with an f-string and suppresses the wrong rule"
    location: "tests/operations/release_support.py:111"
  - id: F010
    severity: note
    category: other
    summary: "Known duplicate report for a release commit"
    location: "docs/program-rules.md:44-47"
  - id: F011
    severity: note
    category: consistency-rot
    summary: "`changes` now means two things in the CLI contract"
    location: "docs/cli-contract.md:102"
  - id: F012
    severity: pass
    category: correctness
    summary: "Release writes match the D2 table and the SQL parameter order"
    location: "src/amoeba/store/releases.py#correct_release"
---

# Review: code — slice 227

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 35 successful tool call(s) of 36 made; 161254 of 161254 diff characters reached the model

## Findings

### [CONCERN] `version` accepts whitespace and newlines, and the text renderer prints it unescaped

`ReportReleaseRequest.version` is `NonBlank`, which strips only the edges and requires at least one character. An interior newline or space is accepted. The value is then written into the single-line header of text output with no sanitizing: `render_changes` `_entry` (src/amoeba/cli/render/releases.py:70-73) and `render_report_release` (lines 58-59). A version such as `"v1\nchanged: …"` prints as a fake second line of an entry, in the context of an agent that reads this output. Git tag names cannot contain whitespace or control characters, and the design calls `--version` "the release tag", so validating the shape at the Pydantic boundary matches the rule "validate everything entering the system". The `changed` and `touched` fields are safe because the renderer collapses whitespace through `prose_line`. The fix is a tag-name pattern on `version`, with a test that a value with a newline is `malformed`.

### [CONCERN] No load test covers the new concurrent write path

`report_release` takes `BEGIN IMMEDIATE` and is called by several agent processes at once. `changes` reads the same tables. The project's testing rule requires a load test for code on concurrency paths, and CI gates it. The repository has no `tests/load/` directory at all. The slice's tests are functional: they check outcomes, not lock contention or latency. This is my reading of the rule as covering store writes; if the PM reads it narrowly, this drops to a note. The gap is real either way: nothing measures what happens when two providers report at once.

### [NOTE] The renderer's `_rejected` fallback hides a missing invariant

`code = problems[0].code.value if problems else "rejected"` shows a placeholder when a `REJECTED` result has no problems. Every current caller passes at least one problem, so the branch is dead. The real gap is that `ReportReleaseResult` and `ChangesResult` do not enforce "rejected implies problems non-empty". A validator on those models would remove the need for the fallback.

### [NOTE] Duplicated rejection and validation code across two operations

The block `tuple(ReleaseProblem(code=RejectCode.MALFORMED, detail=detail) for detail in validation_problems(error))` appears in both `report_release` and `changes`. The two `_rejected` helpers (report_release.py:178, changes.py:112) are near-copies, and `render/releases.py` adds a third. In `report_release.py#_apply`, `_required(request.changed, "changed")` and `_required(request.touched, "touched")` repeat in four arms and could be computed once.

### [NOTE] Size guidance is exceeded in shared files

`invoke` runs about 63 lines (wiring.py:179-257), against the ~50-line guideline. This slice added two arms to it. `wiring.py` is 349 lines, and `store/sql.py` is 480 lines; the slice added the 42-line releases block to the SQL file. The release SQL could go in its own module, and the release arms could share one dispatch helper.

### [NOTE] A consumer silently loses reports from a removed provider

The active-member rule (`_PAIR_ENDS_ACTIVE`, src/amoeba/store/sql.py:135-139) drops every pair whose provider was removed, and `changes` emits no warning. The test `test_a_pair_whose_member_was_removed_is_not_listed` pins that behavior. The consumer block tells the agent to check "what this repo depends on", so a dependency that was removed disappears without a trace. A `ChangesWarning` for a removed provider would make the state visible, and the cost is small.

### [NOTE] `changes` fetches every pair in the program, then filters in Python

`pairs_of` returns all pairs for the program, and the consumer filter runs in Python. `visible_releases` then runs once per pair. Programs are small, so this is not a practical problem. A consumer-filtered query would remove the over-fetch and keep the code shorter.

### [NOTE] A swallowed failure in the live consumer setup

`git(repo, "commit", "-q", "-m", "cf init", check=False)` ignores a failed commit with no comment. The same pattern exists at `tests/live/pause/harness.py:98`, and `consumer.py` largely duplicates that harness setup. A failure here would surface later and less clearly. Either check the return code with a stated reason, or move the shared setup into the harness.

### [NOTE] Test helper builds SQL with an f-string and suppresses the wrong rule

`f"SELECT * FROM {table} ORDER BY 1"` breaks the rule "never f-string SQL". The table name is a literal chosen by the tests, so there is no injection risk, and identifiers cannot be bound as parameters anyway. The fix is an allow-list of table names. The `# noqa: S608` does nothing, because `pyproject.toml` selects only `E, F, W, I, UP, BLE, ASYNC, B`, so it should be removed.

### [NOTE] Known duplicate report for a release commit

The provider doc says "a release flow that adds its own commit before tagging makes a second report for that commit", so a `from_source` consumer sees two entries. The behavior is documented, not hidden, and it is a dead end the design accepts. It is worth a line in the walkthrough, because the consumer agent has no way to tell that the two entries are one change.

### [NOTE] `changes` now means two things in the CLI contract

`amoeba changes` is a new command, but `SetUpResult.changes` and `change_records` already use the word, and lines 102-104 and 213 refer to the set-up field. The two senses do not collide in code, but a reader of the contract can confuse them.

### [PASS] Release writes match the D2 table and the SQL parameter order

I checked the plan table against `_plan`, `CORRECT_RELEASE` against its eight parameters, and `VERSION_RELEASE` and `INSERT_RELEASE` against their columns. SQLite evaluates every SET expression against the old row, so the `COALESCE(?, version)` in `versioned_at` reads the prior version as the comment says. `seq` is `AUTOINCREMENT`, so a withdraw-then-report gets a higher `seq` as the test expects. `Store.write()` commits on a normal return, so the early `return` for a rejection is safe. The `encode_timestamp` text ordering holds, because all values are UTC with `+00:00`, and `'+' < '.'` keeps whole seconds before fractional ones.

### Run Digest

- Response length: 11786 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 37
- Tokens — prompt / cached / cache write / completion / reasoning: 3549455 / 3212859 / 336562 / 66659 / not computed
- Duration: 306.2 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
