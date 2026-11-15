---
docType: review
layer: project
reviewType: tasks
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/243-tasks.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 0d644269d6fa0cf0fb80bcd69b227fb172cc7b42
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 1196995
cachedTokens: 999609
cacheWriteTokens: 197368
completionTokens: 101265
durationSeconds: 445.5
costUsd: 0.488031
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Group 1 commit records a model that `send` does not yet implement"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:81"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The `--to` argparse change lands after its only permitted assertion edit"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:75"
  - id: F003
    severity: concern
    category: consistency
    summary: "The test-edit invariant contradicts itself"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:52"
  - id: F004
    severity: concern
    category: ci-gating
    summary: "The load test's CI gate is implicit"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:173"
  - id: F005
    severity: concern
    category: consistency
    summary: "The plan still says 243 needs only 240"
    location: "project-documents/user/architecture/240-slices.agent-messaging.md:114"
  - id: F006
    severity: concern
    category: completability
    summary: "Task 0.1 says both \"BLOCKED if any name is missing\" and \"map built names\""
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:60"
  - id: F007
    severity: concern
    category: verifiability
    summary: "The 9.2 success check passes without checking the Dependencies line"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:234"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 4.4 is too large for one pass"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:134"
  - id: F009
    severity: concern
    category: proportionality
    summary: "The test set goes beyond the criteria, and the file is heavy for effort 2"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:153"
  - id: F010
    severity: note
    category: completability
    summary: "A rejected program note's rejection row has no defined `to_ref`"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:113"
  - id: F011
    severity: note
    category: coverage
    summary: "The exit code for a failed note write is designed but not tested"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:166"
  - id: F012
    severity: note
    category: consistency
    summary: "`depth = 1` is decided in the task file, not the design"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:45"
  - id: F013
    severity: note
    category: sequencing
    summary: "9.2 amends 240's design but not 240's build file"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:230"
  - id: F014
    severity: note
    category: consistency
    summary: "MCP field documentation is deferred against this file's own rule"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:191"
  - id: F015
    severity: note
    category: operator-walkthrough
    summary: "Operator walkthrough: one dead end the design does not record"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:330"
  - id: F016
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:251"
  - id: F017
    severity: pass
    category: verifiability
    summary: "The named prerequisites and identifiers exist"
    location: "src/amoeba/store/releases.py:133"
  - id: F018
    severity: pass
    category: process
    summary: "Test-with pattern, commit markers and the Amoeba design rules hold"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md"
---

# Review: tasks — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Group 1 commit records a model that `send` does not yet implement

Task 1.1 (line 71) makes `SendRequest` accept `kind: note` and `to_program`, but `send` keeps the 240 request path until 3.2 (line 116). A valid note, such as `to_program` with no `to` (D1 allows it), would reach the request code with no `to`. No door exposes `kind` until 6.1 and 6.3, so the exposure is internal, but the commit would stay in history. Task 3.3 (line 121) already refuses to commit group 3 alone for this reason. Move the group-1 marker to the group-4 commit, or commit groups 1 to 4 together.

### [CONCERN] The `--to` argparse change lands after its only permitted assertion edit

Task 1.1 allows one edit to a 240 assertion that refuses a missing `to` "by argparse or by the model", and points at `tests/cli/test_send_cli.py` (240's CLI suite, `240-tasks.requests.md:236`). The argparse change itself is in 6.1 (line 181). If the assertion is argparse-level, an edit in 1.1 fails until 6.1 lands. Leaving it alone means 6.2 must change it, which lines 52 and 246 forbid. Move the argparse change and its assertion edit together, into 1.1 or 6.1, and name which one in the note.

### [CONCERN] The test-edit invariant contradicts itself

Line 52 says the only existing-test changes are those "tasks 1.1 and 3.3 name", and fixture rows come from "task 4.1". But 3.3 names no changed assertion (it says the request tests pass unchanged), line 246 allows only 1.1's assertion, and fixture rows are added in 4.4 (line 135). Line 135 adds note rows to 240 fixtures that may count rows, and line 52's rule ("fix the new code, not the test") gives no route when that happens. Name one permitted edit, point fixture work at 4.4, and seed notes in new test functions with their own store so existing fixtures stay untouched.

### [CONCERN] The load test's CI gate is implicit

Task 5.6 says CI already runs the load test. That is true: `.github/workflows/ci.yml:40` runs bare `uv run pytest`, and `pyproject.toml:64` ignores only `tests/live`. But no task names the gate or confirms the test is in it, and this repo's rule is that CI gating is not left implicit. Either cite the step in 5.6 and state that a bound failure fails that job, or add a CI wiring task that makes the gate explicit.

### [CONCERN] The plan still says 243 needs only 240

Line 114 reads "242 and 243 need only 240". Task 9.2 (line 232) amends only entry 4's Dependencies line. Task 0.1 (line 60) and 4.4 (line 139) now depend on 242, so after 9.2 the plan and the slice disagree. Add this paragraph to 9.2's amendment list.

### [CONCERN] Task 0.1 says both "BLOCKED if any name is missing" and "map built names"

Line 44 says later tasks use role names and mean whatever 240 built, and 0.1 (line 61) records the built names. Line 60 says to write BLOCKED if any listed module or function is missing. A renamed module that still plays its role cannot be told apart from a missing one. The listed names do appear in 240's task file, so they are sourced, but they are unverified until 240 is built. Change line 60 so BLOCKED fires only when no module plays the role. A rename is recorded in the note.

### [CONCERN] The 9.2 success check passes without checking the Dependencies line

The check runs `sed` over the entry's range and counts lines matching `MAX_RELEASE_NOTE_BODY_LENGTH` or `241`. It passes if any line in that section mentions 241, and it never reads the Dependencies line that line 232 requires to read 222, 227, 240, 241 and 242. The sed range also depends on the exact heading text. Replace it with a check that reads the Dependencies line and asserts it contains 241 and 242.

### [CONCERN] Task 4.4 is too large for one pass

4.4 covers fixture rows in four 240 suites, a new inbox suite, additions to four list, status, rm and sweep suites, the requests scenario, and a 242 test: eleven test files in one task. Split it into 4.4 (the 240 suites for reply, cancel, send's parent and inbox's request reads), 4.5 (the new inbox notes suite and the list, status, rm and sweep additions), and 4.6 (the scenario rerun and the 242 question test), each with its own success line.

### [CONCERN] The test set goes beyond the criteria, and the file is heavy for effort 2

- 5.2(b) (line 153) is a monkeypatch test that shows the size check can fail. It tests the test. The criterion needs only that the largest body fits the constant. Cut it.
- 5.2's recipient table (line 152) repeats the matrix in 5.5 (line 170), which is the criterion's oracle. Keep the table as unit cases only.
- 6.4 (line 195) is a one-bullet timing test that checks a design paragraph, not a criterion. Fold it into 6.3's tests. It also does not measure the note prune that 2.5 adds inside `send`, `reply` and `cancel`'s write lock (design line 203). The design's timing argument (design line 94) leaves that work out.

The file has 34 top-level tasks and more than 100 checkboxes for a slice the task rates at effort 2 (line 42). The cuts above are the first place to trim.

### [NOTE] A rejected program note's rejection row has no defined `to_ref`

240's `message_rejections` defines `to_ref` as "as given, send only" (`project-documents/user/slices/240-slice.requests.md:124`). Nothing here says what a note records for `to_program`. Decide it in 3.1 (for example, the program id as given) and assert it in 3.3.

### [NOTE] The exit code for a failed note write is designed but not tested

D6 and the operator walkthrough say a failing note write exits 3 (design lines 206 and 327). Task 5.4 tests the rollback and retry, but no line asserts exit 3. Add one assertion at the CLI or the exit-code mapping.

### [NOTE] `depth = 1` is decided in the task file, not the design

The context says "Decided here, not in the design". The design is what later readers use, so the rule belongs in D1 (design line 118, "A note takes no `parent`"). Move it there and leave a pointer in the task file.

### [NOTE] 9.2 amends 240's design but not 240's build file

240 is built first from `240-tasks.requests.md`, which 9.2 does not touch. 243 would then amend code that 240 built to the old design. That may be acceptable, but the task should say so, or re-task 240 before it is built.

### [NOTE] MCP field documentation is deferred against this file's own rule

Line 51 says a task that adds a field adds its contract-doc entry then. Task 6.3 adds `kind` and `to_program` to the MCP tools with no doc step, and they wait for 9.1 (line 227). `tests/test_contract_docs.py:305-312` checks `mcp-server.md` only for tool names, so no test fails, but the rule is broken. Add the MCP entries to 6.3.

### [NOTE] Operator walkthrough: one dead end the design does not record

The design says "Dead ends found: none" (line 330). Stepping through it as the person who runs it: the Start step (line 321) depends on each repo's agent committing the new Handling paragraph. Nothing checks that it happened, and a repo that skips it has no rule telling its agent that notes are data. The 240 notice (D11) still labels every note, so the exposure is reduced, not removed. Record it as a known gap and name the mechanism that delivers the block to each repo. The other paths (start, normal use, each failure, end state, cleanup) all have an exit.

### [PASS] Every success criterion has a task

I mapped each functional, technical, integration and push criterion, the verification walkthrough, and D1 to D8 to at least one task. The only tasks without a criterion are the process steps (0.1, 0.2), the CHANGELOG entry (9.3, which matches 240's task file, not the design) and the design amendments (9.2, which the design lists).

### [PASS] The named prerequisites and identifiers exist

The 227 identifiers that 5.1 to 5.3 rely on exist in merged code: `visible_releases` takes `since: str`, which matches `encode_timestamp`; `ReportOutcome` has the four outcomes; `_apply` is in `report_release.py`; `SELECT_PAIRS_CONSUMED_BY` and `_PAIR_ENDS_ACTIVE` are in `store/sql.py`, which is 484 lines as stated. The 240, 241 and 242 names in 0.1 appear in their task files but are not built, so they stay unverified until then. The CI and pyproject claims in 5.6 are accurate.

### [PASS] Test-with pattern, commit markers and the Amoeba design rules hold

Every implementation group is followed by its tests (1.1 to 1.2, 2.1 to 2.2, 2.3 to 2.4, 2.5 to 2.6, 3.1 to 3.2 to 3.3, 4.1 to 4.3 to 4.4, 5.1 to 5.2, 5.3 to 5.4, 6.1 to 6.2). Markers are plain lines at group ends, apart from the group-1 issue above. The file has no deferral and no step that waits on real usage. It adds no config or state file, and every state has an exit: notes leave by the prune.

### Run Digest

- Response length: 13279 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 1196995 / 999609 / 197368 / 101265 / not computed
- Duration: 445.5 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
