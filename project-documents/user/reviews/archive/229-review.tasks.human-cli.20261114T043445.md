---
docType: review
layer: project
reviewType: tasks
slice: human-cli
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/229-tasks.human-cli.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: b32df8ec501f7002f9df0afef785ed3cbf8d91c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
effort: xhigh
turns: 28
promptTokens: 1040439
cachedTokens: 848583
cacheWriteTokens: 191840
completionTokens: 64987
durationSeconds: 288.2
costUsd: 0.279689
costBasis: provider
runId: run-20261114-p5-c32cc131
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Task 0.1 gate greps for a string the 227 design does not contain"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:54"
  - id: F002
    severity: fail
    category: correctness
    summary: "`list --all` scope is specified three different ways"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:180"
  - id: F003
    severity: concern
    category: coverage
    summary: "`list --all` drops the \"every other run\" part of D3"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:183"
  - id: F004
    severity: concern
    category: operator-walkthrough
    summary: "The empty-program bound in D3 is false, and no task gives those rows an exit"
    location: "project-documents/user/slices/229-slice.human-cli.md:121"
  - id: F005
    severity: concern
    category: operator-walkthrough
    summary: "The D3 typo-fix path is a dead end"
    location: "src/amoeba/operations/set_up_checks.py:89"
  - id: F006
    severity: concern
    category: sequencing
    summary: "The 11.1 backup goes to `mktemp -d` and a shell variable"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:252"
  - id: F007
    severity: concern
    category: sequencing
    summary: "BLOCKED at 11.1 halts all of 12, which does not depend on it"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:251"
  - id: F008
    severity: concern
    category: sizing
    summary: "Task 9 is oversized and has a red middle with no checkpoint"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:222"
  - id: F009
    severity: concern
    category: sequencing
    summary: "The live hook command may resolve to the pre-slice binary"
    location: "tests/live/pause/harness.py:33"
  - id: F010
    severity: note
    category: specificity
    summary: "`--no-rules`, `--no-allow` and `--no-deny` have no stated request mapping"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:142"
  - id: F011
    severity: note
    category: operator-walkthrough
    summary: "The walkthrough does not say what happens to a question after the fix"
    location: "project-documents/user/slices/229-slice.human-cli.md:204"
  - id: F012
    severity: note
    category: sizing
    summary: "3.5 packs a parser and a multi-rule follow into one subtask"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:112"
  - id: F013
    severity: note
    category: coverage
    summary: "The slice design says the 220 and 227 edits are still to do"
    location: "project-documents/user/slices/229-slice.human-cli.md:176"
  - id: F014
    severity: note
    category: specificity
    summary: "7.5 does not define \"the entries it resolves to now\""
    location: "project-documents/user/tasks/229-tasks.human-cli.md:186"
  - id: F015
    severity: note
    category: metadata
    summary: "Front-matter `dateUpdated` is after today's date"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:16"
  - id: F016
    severity: pass
    category: coverage
    summary: "Success criteria are all covered"
    location: "project-documents/user/tasks/229-tasks.human-cli.md"
  - id: F017
    severity: pass
    category: correctness
    summary: "Referenced helpers and source paths exist"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:56"
  - id: F018
    severity: pass
    category: process
    summary: "Test-with ordering, commit markers and deferral language"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:72"
---

# Review: tasks — slice 229

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 0.1 gate greps for a string the 227 design does not contain

`grep -n "amoeba add" project-documents/user/slices/227-slice.program-dependencies.md` returns nothing. The 227 design uses `add --depends-on` (line 41) and `rm --pair` (line 254), with no `amoeba` prefix. The 220 check is correct: `kebab` is at line 40 and the `add`, `rm` and `list` rows are at lines 99–101. As written, step 0.1 writes `BLOCKED: 220 or 227 not updated` on a correct tree. Change the 227 pattern to `add --depends-on` or `rm --pair`.

### [FAIL] `list --all` scope is specified three different ways

- 7.3 (line 180) says `--all` with any registered subject is `rejected`.
- 7.4 (line 183) and 9.2 (line 229) reject `--all` only with `members` or `dependencies`.
- 7.5 (line 186) says empty programs are hidden "unless `all`", which only makes sense if `programs --all` is valid.

The parent design is also split: D3 (`project-documents/user/slices/229-slice.human-cli.md:111`) allows `--all` with `programs`, and D14 (line 192) says `--all` with a registered subject is exit 2. A junior cannot pass both 7.3 and 7.5. Keep D3, change 7.3 to reject `--all` only for `members` and `dependencies`, and correct D14.

### [CONCERN] `list --all` drops the "every other run" part of D3

D3 (slice line 111) says `--all` with no subject adds every other run under its member, then Settled. 7.3 adds only `settled`, and 7.4 asserts "`all` adds `settled` and nothing else". 8.3 renders "every other run under its member", but no task produces that data. Either add the data and its test to 7.3 and 7.4, or remove the behavior from D3 and 8.3.

### [CONCERN] The empty-program bound in D3 is false, and no task gives those rows an exit

The design says program rows "exist only for names someone typed to `--program`, a few at most." D5 (line 139) creates a program named after the CF project whenever `add` runs without `--program`. Every repo ever registered leaves a row, and `rm` leaves it behind. Deletion is excluded (line 43) and no task removes rows. The Amoeba rules require either a named cleanup or a true bound. Fix: delete a program row when no member or question ever referenced it (the foreign key only blocks rows with history), or state the real growth. Then add the matching step to 6 or 7.

### [CONCERN] The D3 typo-fix path is a dead end

D3 says the fix for a typo'd program is `rm` then `add --program right`. `get_member` returns soft-removed rows (`src/amoeba/store/programs.py:84,90`). `check_request` then rejects any stored member whose `program_id` differs, with no `removed_at` check (lines 88–96). So the removed member is refused with `member_of_other_program`. Moving it would change an engine guard, which conflicts with the slice's "no operation's decision logic changes" scope. Decide the behavior, document it in D3 and the walkthrough, and pin it with a test in 5.4 or 6.2.

### [CONCERN] The 11.1 backup goes to `mktemp -d` and a shell variable

The backup is the only restore path for migration 005 on the live store. `mktemp -d` on macOS creates the directory under `$TMPDIR`, which the OS clears. `$BACKUP` is also a shell variable that a later restore step in a fresh shell will not have. Use a durable directory and have the reply name the literal path. The restore step must use that literal path.

### [CONCERN] BLOCKED at 11.1 halts all of 12, which does not depend on it

11.1 says `BLOCKED` and "stop". The project rule is to block only the dependent part. Most of 12.1 and 12.2 do not depend on the cutover. The exception is the CHANGELOG bullet at line 270, which says "the live store and hook were moved", and the commit title at line 273, "record slice 229 cutover". Those presume 11 completed. State that 11 can block alone and 12 proceeds, and that the cutover bullet and commit title are written only when 11 completes.

### [CONCERN] Task 9 is oversized and has a red middle with no checkpoint

9.1 leaves `tests/cli` failing, and 9.2 says the CLI is rebuilt there. 9.2 splits `cli/main.py` into three modules and defines about fifteen flags. 9.3 replaces `test_set_up_cli.py`, adds three CLI test files, and updates four more test files plus the MCP parity tests. That is one commit over roughly a dozen files with no green checkpoint. Merge 9.1 into 9.2 so the red state is not a task boundary, and split 9.3 into new-command tests and renamed-command tests.

### [CONCERN] The live hook command may resolve to the pre-slice binary

10.1 (line 241) says "the hook is `amoeba handle-pause`". Until 11.2 reinstalls, a bare `amoeba` on PATH is the PM's installed pre-slice tool, which has no `handle-pause`. The harness resolves its own binary as `Path(sys.executable).with_name("amoeba")` (line 33) and invokes it by absolute path (line 146). I did not find where the hook string is set. Require that the hook command be built from that absolute path, not the bare name.

### [NOTE] `--no-rules`, `--no-allow` and `--no-deny` have no stated request mapping

D4 says `--no-rules` stores none, and `--no-allow` and `--no-deny` store an empty list (slice lines 128–129). 5.1, 9.2 and 9.3 never say these build `rules_paths=[]` and `authorize_*=[]`. 9.3 asks for "the request each flag builds" without listing them. State the mapping in 5.1 and test it.

### [NOTE] The walkthrough does not say what happens to a question after the fix

After `sources_missing` or `sources_too_large`, the walkthrough says the PM adds a file or raises the cap. It does not say whether the waiting question re-runs. Per the 220 architecture, a declined question waits for the PM to answer. State the exit explicitly (answer or dismiss) in the walkthrough and in the `list` text.

### [NOTE] 3.5 packs a parser and a multi-rule follow into one subtask

3.5 combines the pure import parser, path resolution with the repo boundary, depth and cycle limits, the missing-target rule, and size accounting. Splitting the parser into its own subtask would give a junior a testable first step.

### [NOTE] The slice design says the 220 and 227 edits are still to do

D12 says "the 220 architecture is amended in this slice", and the Included list (line 37) names "the 227 design update". Both are already on main. Task 0.1 treats them as preconditions, which is correct, but the design text is stale.

### [NOTE] 7.5 does not define "the entries it resolves to now"

A junior could read this as a git check at the pinned commit for each member. The design intends the configured entries, with no git call per member. Say so.

### [NOTE] Front-matter `dateUpdated` is after today's date

`dateUpdated: 20261114` is after the current date, 2026-11-13.

### [PASS] Success criteria are all covered

- Text and `-j` on every command: 8.1–8.5, 9.2, 9.3.
- `list -j` equals status: 7.4, 9.3.
- `amoeba add` with no flag: 5.3, 5.4. 9.3 does not list the zero-flag CLI case explicitly.
- Default rules read, skipped and declined: 3.1, 3.2.
- Each section once: 3.3, 3.4.
- Named entries still fail: 3.2.
- Every member setting from the CLI: 5.1, 9.2.
- Hook through `handle-pause` and old names gone: 9.2, 9.3, 10.1, 11.2, 12.2.

The design restates no NFR, so no load test is required.

### [PASS] Referenced helpers and source paths exist

I checked the test helpers in 0.1 and the source modules named in the tasks. `tests/live/pause/harness.py`, `tests/cf_fixtures.py` (`LIST_PROJECTS`), `tests/user_configs.py`, `tests/store/test_migration_004.py`, `tests/mcp_server/`, the `store/schema` set (001 to 004 only), `ConsumedMode`, `RulesPath`, `OperationName` and the `SetUpProblemCode` members all exist. The new modules the tasks create do not exist yet, as expected.

### [PASS] Test-with ordering, commit markers and deferral language

Each implementation subtask is followed by its test subtask. The 13 `**Commit**:` markers sit at green points, except around task 9 (see above). I found no deferral language in the task file or the design beyond explicit exclusions.

### Run Digest

- Response length: 11620 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 28
- Tokens — prompt / cached / cache write / completion / reasoning: 1040439 / 848583 / 191840 / 64987 / not computed
- Duration: 288.2 s
- Cost: $0.28 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
