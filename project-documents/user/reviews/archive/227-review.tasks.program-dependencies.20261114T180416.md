---
docType: review
layer: project
reviewType: tasks
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/227-tasks.program-dependencies.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 635241253f32054b95b3ec3e9437f429bccf9b32
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 713644
cachedTokens: 539503
cacheWriteTokens: 174129
completionTokens: 50926
durationSeconds: 223.4
costUsd: 0.313183
costBasis: provider
runId: run-20261114-p5-0e7feed2
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Text renderer prints `reported` for a versioned release, contradicting the design"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:162"
  - id: F002
    severity: concern
    category: coverage
    summary: "Success criterion 7 has no path if the baseline suite is red"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:62"
  - id: F003
    severity: concern
    category: test-design
    summary: "The concurrency test in 2.4 is ambiguous and may not be testable as written"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:122"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Section 4 cannot be committed midway, because the 226 test edits come last"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:147"
  - id: F005
    severity: concern
    category: scope
    summary: "The new MCP test duplicates 226's parity tests and does not prove criterion 5"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:170"
  - id: F006
    severity: concern
    category: consistency
    summary: "The `add --depends-on` pointer is placed in the wrong file"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:186"
  - id: F007
    severity: concern
    category: consistency
    summary: "The design says \"the one edit to a 226 test,\" but the breakdown makes at least five"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:192"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 6.4 adds manual runs that the design does not ask for, and one of them has no defined fixture"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:225"
  - id: F009
    severity: note
    category: design-rules
    summary: "Release rows are described as \"bounded by history,\" which is growth rather than a bound"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:253"
  - id: F010
    severity: note
    category: scope
    summary: "README edit has a false justification"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:176"
  - id: F011
    severity: note
    category: sequencing
    summary: "The flow test imports the parser from another test module without naming a shared location"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:205"
  - id: F012
    severity: note
    category: proportionality
    summary: "Task 0.1 carries four note-only items"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:58"
  - id: F013
    severity: note
    category: process
    summary: "Uncommitted planning edits are in the working tree"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md"
  - id: F014
    severity: note
    category: coverage
    summary: "No NFR is restated, so no load-test task or CI gate is required"
    location: "project-documents/user/slices/227-slice.program-dependencies.md"
  - id: F015
    severity: pass
    category: coverage
    summary: "All eight success criteria map to tasks"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:224"
  - id: F016
    severity: pass
    category: coverage
    summary: "Cited paths and symbols exist"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:58"
  - id: F017
    severity: pass
    category: sequencing
    summary: "`build_world` collides on a second call, and task 6.2 handles it"
    location: "tests/live/pause/harness.py:84"
  - id: F018
    severity: pass
    category: sequencing
    summary: "Dependency order, the test-with pattern and commit markers all hold"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:92"
  - id: F019
    severity: pass
    category: design-rules
    summary: "No deferral and no waits on real use"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:50"
---

# Review: tasks — slice 227

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Text renderer prints `reported` for a versioned release, contradicting the design

Task 4.3 prints `versioned` as the first line `reported` plus a `version:` line. The design's D5 (slice design line 153) lists five first-line words without `versioned`. But the Operator Walkthrough (slice design line 245) says a release tag gives `versioned`, and D2 defines `versioned` as the outcome. Context Summary line 44 calls this a decision "where the design is silent"; the design is not silent. A provider agent reading text output sees `reported` for a release. Either print `versioned` as the first line and amend D5, or amend the walkthrough and state the choice in D5.

### [CONCERN] Success criterion 7 has no path if the baseline suite is red

Task 0.1 says pre-existing failures are "written down, not fixed." Success criterion 7 (slice design line 230) requires the full default suite and the live test to pass, and the Verification Walkthrough requires all checks to pass. If the baseline is red, the breakdown has no path to criterion 7 and no `BLOCKED:` instruction. Add a rule: a failure in code this slice touches is fixed within the slice; an unrelated failure gets a `BLOCKED:` line under 0.1 with the test name and error text, and the slice stops.

### [CONCERN] The concurrency test in 2.4 is ambiguous and may not be testable as written

The store does have a busy timeout (`src/amoeba/store/store.py:76`, `BUSY_TIMEOUT_SECONDS`). But the task says a second `report_release` "waits … rather than inserting twice." A single-threaded test holding `BEGIN IMMEDIATE` on one connection cannot release it while the second call waits, so the second call raises `StoreBusyError` after the timeout. The task does not say whether the test uses a thread that releases the lock, or asserts `StoreBusyError` with a short timeout. Specify one. D7 does not list this test, so the task should say that it adds it.

### [CONCERN] Section 4 cannot be committed midway, because the 226 test edits come last

Section 4 is one commit spanning 4.1 to 4.5 and about a dozen files. The task says 226 and 229 tests fail "until every part of this section exists," and the 226 test edits sit in 4.4 (line 169). Move the `test_parser_names` edit into 4.2 so the CLI works without the MCP work, then add a `**Commit**:` marker after 4.3. Keep the MCP-side edits and 4.5 as the second commit.

### [CONCERN] The new MCP test duplicates 226's parity tests and does not prove criterion 5

Task 4.4 adds `test_release_tools.py`, which uses a recording fake in place of the operation. That tests door plumbing, not the real operations. D5 and D7 (slice design lines 152, 192) say 226's parity tests cover the rows, and the task's `directory` refusal check probably overlaps 226's door tests. Drop the new file and add the two names to 226's parity cases. Then state that criterion 5, which asks for the same results over CLI and MCP with real inputs, is covered by those parity tests plus the CLI tests. I did not read 226's parity tests, so that coverage is unverified.

### [CONCERN] The `add --depends-on` pointer is placed in the wrong file

Task 5.1 says to add the pointer to the `add --depends-on` contract "in `docs/cli-contract.md`." D8 (slice design line 201) puts that pointer in `docs/program-rules.md`. The same bullet also carries D2's and D4's notes, which D8 also places in `program-rules.md`. Change the bullet to name `docs/program-rules.md`, or state why the split is intended.

### [CONCERN] The design says "the one edit to a 226 test," but the breakdown makes at least five

D7 says the stdio literal count is "the one edit to a 226 test." Task 4.4 (line 169) edits `DIRECTORY_TOOLS` and `READ_TOOLS` in `tests/mcp_server/test_tools.py` (lines 28 and 35), the stdio count, and `test_parser_names`. Task 4.5 (line 177) edits `test_contract_docs`. `tests/mcp_server/test_instructions.py:13` also requires every tool to be named in `INSTRUCTIONS`. Task 6.3 (line 220) then checks only the edits named in 4.4 and 4.5. The breakdown is right and the design is wrong. Correct D7 so the design matches the code.

### [CONCERN] Task 6.4 adds manual runs that the design does not ask for, and one of them has no defined fixture

The design gives the Operator Walkthrough to the designing and reviewing agents (Amoeba rule "Operator walkthrough"). The implementer's job is the Verification Walkthrough. Most of the eight cases already have named tests (2.4, 3.2, 4.2, 6.1, 6.2). Step 225 asks for manual runs "with a fixture `cf` on `PATH`," which neither the design nor the task defines. Cut 6.4 to the coverage mapping in 6.4's first bullet, and drop the manual runs.

### [NOTE] Release rows are described as "bounded by history," which is growth rather than a bound

The Amoeba rule requires that anything the system writes has a named cleanup, or that the design says why it is bounded. The design says rows "grow with the member's merges and releases" (line 120) and that a removed member's rows stay forever (line 253). Per-row `withdraw` is an explicit cancel, but nothing removes rows of removed members. State a real bound, or name a cleanup. The breakdown inherits this, so no task change is needed for now.

### [NOTE] README edit has a false justification

Task 4.5 and Context Summary line 44 edit `README.md` because "existing tests require every tool named." That holds for `INSTRUCTIONS`, which `tests/mcp_server/test_instructions.py:13` checks. It does not hold for the README: `tests/test_old_command_names_gone.py` checks README only for retired names. D8 does not list README. The edit is harmless. Keep it and say why, or drop it.

### [NOTE] The flow test imports the parser from another test module without naming a shared location

Task 6.1 reads the consumer block "(the 5.2 parser)," but 5.2 defines that parser in `tests/test_program_rules_doc.py`. Name a shared helper location, such as a `tests/support` module, so 6.1 does not import from a test file.

### [NOTE] Task 0.1 carries four note-only items

Items 58 and 59 list about 30 identifiers for the implementer to "note," and nothing checks them later. The identifiers are accurate, and I confirmed the ones I checked exist. Keep the checks that gate work and drop the note lists, since the later tasks already name what they use.

### [NOTE] Uncommitted planning edits are in the working tree

At the start of the session, the task file showed as modified and `project-documents/user/reviews/227-review.tasks.program-dependencies.md` showed as deleted. Commits at each marker should name their paths explicitly rather than run `git add -A`, so these planning edits do not land in a slice commit.

### [NOTE] No NFR is restated, so no load-test task or CI gate is required

The slice design restates no latency, throughput or resource requirement. The live tier stays out of a bare run, as the project rules require, so no CI gate is needed for it.

### [PASS] All eight success criteria map to tasks

Criteria 1 to 3 map to 1.2, 1.3, 2.4, 3.2 and 6.1. Criterion 4 (two since values) maps to 3.2, and it is tested at operation level rather than with two real worktrees, which is adequate. Criteria 5 and 6 map to 4.2, 3.2, 2.4 and 6.2. Criterion 7 maps to 6.3, 4.5 and 5.3. Criterion 8 maps to 6.1 and 6.2.

### [PASS] Cited paths and symbols exist

I checked the modules, helpers and test files the task names, including `DecisionsRequest._utc_text`, `resolve_member` with `NotInProgram` and `NotAProject`, `pairs_of`, `visible_releases` (new), `_option_flags`, `FakeCf` and `status_deps` in `tests/operations/status_support.py`, `build_world` and `run_amoeba`, `READ_ADVICE` and `WRITE_ADVICE`, and the `EXPECTED_SCHEMA_VERSION` value of 5. `docs/program-rules.md` and `tests/program/` are absent, as expected for new files.

### [PASS] `build_world` collides on a second call, and task 6.2 handles it

`repo.mkdir()` (line 84) and `data_dir.mkdir()` (line 90) have no `exist_ok`, so a second call on the same parent fails. Task 6.2 says to extend the harness, and that is the right fix.

### [PASS] Dependency order, the test-with pattern and commit markers all hold

Each implementation step is followed by its tests, and the modules are built in dependency order. The seven commit markers fall at tested points, not after every task.

### [PASS] No deferral and no waits on real use

The task file states that no task waits on a person or on real use. Searching the design and task file for deferral language found none. Section 2.2's "fuller contract text comes in 4.5" is sequencing within the slice, not deferral.

### Run Digest

- Response length: 12070 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 713644 / 539503 / 174129 / 50926 / not computed
- Duration: 223.4 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19
