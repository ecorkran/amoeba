---
docType: review
layer: project
reviewType: tasks
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/243-tasks.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 0941569ab94acb10010925d9640c13ad333cac8a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 1052613
cachedTokens: 887807
cacheWriteTokens: 164790
completionTokens: 56288
durationSeconds: 255.0
costUsd: 0.2893
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: coverage
    summary: "Task 4.4 makes the 242 row test conditional, and 242 is missing from dependencies"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:138"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The commit marker after group 3 lands before the D4 guard"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:120"
  - id: F003
    severity: concern
    category: test-quality
    summary: "The release-note size test cannot fail on the change it is meant to catch"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:148"
  - id: F004
    severity: concern
    category: nfr
    summary: "No load case covers the new per-consumer writes inside report_release's lock"
    location: "tests/load/test_report_release_load.py:56"
  - id: F005
    severity: concern
    category: coverage
    summary: "`list` not showing notes has no test"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:136"
  - id: F006
    severity: concern
    category: coverage
    summary: "Two stated behaviours have no task test"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:151"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Group 6 is overweight and one check is duplicated"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:194"
  - id: F008
    severity: note
    category: proportionality
    summary: "The context summary's effort figure does not match the plan"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:39"
  - id: F009
    severity: note
    category: sequencing
    summary: "Add the Handling-block prerequisite to task 0.1"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:57"
  - id: F010
    severity: note
    category: docs
    summary: "The 9.2 success grep cannot isolate plan entry 4"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:222"
  - id: F011
    severity: pass
    category: coverage
    summary: "Success criteria are covered, except the `list` check"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:251"
  - id: F012
    severity: pass
    category: sequencing
    summary: "Sequencing and the test-with pattern hold"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:66"
  - id: F013
    severity: pass
    category: accuracy
    summary: "Referenced repo paths and symbols exist"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:62"
---

# Review: tasks — slice 243

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 4.4 makes the 242 row test conditional, and 242 is missing from dependencies

Design D4 says "Each row is a test" (design line 157), and its 242 row (line 155) is one of them. Task 4.4 instead says "if 242 is built, one added test … otherwise write '242 not built' in a note". That skips an in-scope test based on another slice's build status, which the Amoeba design rules reject under "No deferral". The condition is also unnecessary. The plan orders `240 → 241 → 242 → 243 → 244` (`project-documents/user/architecture/240-slices.agent-messaging.md:112`), and 242 does not depend on 243 (`project-documents/user/slices/242-slice.hold-and-release.md:52` lists notes as outside its scope). Fix: make the test unconditional, and add 242 to the frontmatter dependencies (lines 6–10) and to projectState (lines 11–15), which name only 240 and 241. The "if 242 is built" wording in the 4.1 audit bullet (line 125) needs the same change.

### [CONCERN] The commit marker after group 3 lands before the D4 guard

The marker at line 120 closes group 3, which lets `send` write note rows. The guard that keeps 240's request reads from seeing them (`reply`, `cancel`, the `parent` lookup, `inbox` requests, `list`/`status`) is group 4 (lines 122–141), committed at line 141. The design's own risk entry (design line 301) names this failure. No door creates notes until group 6, so nothing user-facing is affected yet. But the commit at line 120 is not a point where D4 holds. Fix: run the audit and guard (4.1–4.2) before 3.1, or drop the marker at 120 and commit once after group 4.

### [CONCERN] The release-note size test cannot fail on the change it is meant to catch

Line 148 makes `MAX_RELEASE_NOTE_BODY_LENGTH` include "the template's fixed length from the template's own pieces". A template change then moves the bound with it, so a check against the bound cannot fail on a template change. Design D5 (line 190) requires that "a change to a report constant or to the template that breaks the bound fails a test". Line 152 asks for "assert that raising a report constant by one would exceed it". The constant is computed once at import, so patching a report constant in a test does not change it. The only way to pass is to recompute the same sum in the test. Fix: pin the value stated in `cli-contract.md` (task 9.1, line 216) and assert in a contract test that it equals the computed constant. Template growth then changes the computed value and fails the comparison. Keep the largest-report length assertion on top of that.

### [CONCERN] No load case covers the new per-consumer writes inside report_release's lock

The design restates the write-lock timing bound (design "Write lock", lines 94–95). It says `report_release`'s timing is "227's, unchanged" because it adds no lookup or wait. But D5 adds one `messages` row and one `deliveries` row per consumer inside the same `BEGIN IMMEDIATE`, so the lock-held work grows with consumers. The existing load test seeds members only (`seed_members`, line 56) and never calls `seed_pairs`, so it never writes a note. Task 6.4 (line 187) puts its timing check in `tests/test_message_timing.py`, which is not in the load tier. Task 5.4 (line 165) checks only a stub call count. Fix: add a `tests/load` case that seeds pairs (`seed_pairs`, `tests/operations/release_support.py:78`) at a realistic consumer count and asserts the existing latency bound. Also add a CI wiring item that names `tests/load`. Today it runs only because `.github/workflows/ci.yml:40` is a bare `uv run pytest` and `pyproject.toml` ignores only `tests/live`. That gating is implicit, and the rule requires it to be explicit.

### [CONCERN] `list` not showing notes has no test

The design's Technical Requirements (line 268) say "`list` and `status` do not show notes". Task 4.4 tests only `status` in `test_status_requests.py`. `list` is covered only by the read change in 4.2. Fix: add a `list` case beside the status case, with an open request and a note, where `list` shows the request only.

### [CONCERN] Two stated behaviours have no task test

(a) D5 (design line 183) says "a consumer's mode changing later (`add --depends-on` again) sends nothing retroactively". Task 5.2 covers pairs added after a report and pairs removed, but not a mode change. (b) The design's operator walkthrough (line 327) says a failing note write exits 3. Task 5.4 (line 164) checks that the report rolls back, but nothing checks the exit code. Fix: add the mode-change case to 5.2, and in 5.4 assert that the CLI exits 3 when the note write raises.

### [CONCERN] Group 6 is overweight and one check is duplicated

Group 6 covers CLI flags, CLI rendering, inbox rendering, MCP fields, descriptions and `INSTRUCTIONS`, a timing test, import checks and rules text, and it closes with one commit (line 194). Task 6.4 (line 187) asserts a stub `cf` call count for a program note, and task 5.4 (line 165) asserts the same kind of count for `report_release`. The Success Criteria contain no timing criterion; the timing claim is only in the design's Data Flow. Fix: fold the program-note count into 3.3, where the note path is built. Split the commit at 194 into the doors (6.1–6.3) and the rules and checks (6.4–6.5). Keep the import-boundary checks, since the design requires them (line 270).

### [NOTE] The context summary's effort figure does not match the plan

The context summary says "Effort 4/5". The plan's entry 4 says "Relative Effort: 2" and "Risk Level: Low" (`project-documents/user/architecture/240-slices.agent-messaging.md:92–93`). Reconcile the two. The proportionality finding above depends on which one is right.

### [NOTE] Add the Handling-block prerequisite to task 0.1

Task 6.5 edits "the Handling block" (line 190). 240 creates that block (`240-slice.requests.md`, "Block names" and "Handling block", lines 222 and 261). Task 0.1 checks code prerequisites only, and `docs/program-rules.md` has no Handling block today. Add that check to 0.1, so a missing block is reported as `BLOCKED:` at the start instead of at 6.5.

### [NOTE] The 9.2 success grep cannot isolate plan entry 4

`grep -n "Dependencies"` on the plan matches the Dependencies line of every entry (`240-slices.agent-messaging.md` lines 44, 61, 77, 90, 105), so "shows entry 4 naming 241" cannot be checked as written. Name entry 4 by its title and check the lines after it.

### [PASS] Success criteria are covered, except the `list` check

Each functional, technical and integration criterion maps to a task. Program fan-out, rejections, resend and id reuse are in 3.3. The reply, cancel and parent refusals, inbox, rm, sweep and scenario D are in 4.4. The matrix against `changes` is 5.5, atomicity is 5.4, push is 7.1, the live tier is 8.1, MCP parity is 6.3, retention is 2.6, and the schema-version and boundary checks are in 10.1. The `list` gap is noted above.

### [PASS] Sequencing and the test-with pattern hold

Each implementation group is followed by its tests. The store work (group 2) precedes the send path (group 3) and the release path (group 5). The dependency order inside the slice has no cycle.

### [PASS] Referenced repo paths and symbols exist

Verified in the repo: `visible_releases` (`src/amoeba/store/releases.py:133`); the `ReportOutcome` values (`src/amoeba/operations/report_release_models.py:62-69`); `FULL_HASH_LENGTHS` and `MAX_CHANGED_LENGTH` (same file, lines 32 and 39); `ACTIVE_MEMBER`, `_PAIR_ENDS_ACTIVE` and `SELECT_PAIRS_CONSUMED_BY` (`src/amoeba/store/sql.py:98, 135, 144`); `members_of`, `get_program` and `pairs_consumed_by` (`src/amoeba/store/programs.py:80, 96, 111`); `store.write()` (`src/amoeba/store/store.py:119`); and `BUSY_TIMEOUT_SECONDS` and `MCP_CALL_DEADLINE_SECONDS`. The helper paths the tasks name exist, including the release and seed helpers, `tests/cf_stub.py`, `tests/live/program/`, `tests/test_program_rules_doc.py` and `tests/load/test_no_cf_under_write_lock.py`. Migrations 001–005 exist, and `CHANGELOG.md` has an `[Unreleased]` heading. `store/sql.py` is 484 lines, as the context summary states.

### Run Digest

- Response length: 11818 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1052613 / 887807 / 164790 / 56288 / not computed
- Duration: 255.0 s
- Cost: $0.29 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
