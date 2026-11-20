---
docType: review
layer: project
reviewType: tasks
slice: standing-answers
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/230-tasks.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 3ff3ea74310e9c45619e32b6a61f7aee54b0ee51
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 503697
cachedTokens: 349714
cacheWriteTokens: 153973
completionTokens: 42271
durationSeconds: 180.4
costUsd: 0.264167
costBasis: provider
runId: run-20261120-p5-ebc0a23b
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/230-slice.standing-answers.md:210"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Test tasks follow their implementation tasks"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:78"
  - id: F003
    severity: pass
    category: verification
    summary: "Built names and paths hold"
    location: "src/amoeba/store/migrations.py:25"
  - id: F004
    severity: concern
    category: correctness
    summary: "3.2 points at a helper that cannot produce the standing rejection"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:110"
  - id: F005
    severity: concern
    category: granularity
    summary: "4.1 is six sub-steps across both doors and both docs"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:126-133"
  - id: F006
    severity: note
    category: sequencing
    summary: "Development Approach order differs from the tasks"
    location: "project-documents/user/slices/230-slice.standing-answers.md:255"
  - id: F007
    severity: note
    category: detail
    summary: "Two types are named without their home"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:91"
  - id: F008
    severity: note
    category: granularity
    summary: "Task 5.4's required keyword has six call sites the task does not list"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:170"
  - id: F009
    severity: note
    category: scope
    summary: "Task 9.1's second live test goes beyond the integration criteria"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:223"
  - id: F010
    severity: note
    category: process
    summary: "0.1 assumes the planning commit already exists"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:58"
---

# Review: tasks — slice 230

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task

Reach, withdraw, member removal, the authorize list and the cap map to 5.7, 7.2, 6.2 and 5.5. The migration maps to 1.2, the two live checks to 9.1, and the walkthrough to 9.2. The Technical Requirements (AST test, prompt-kind tie, checks) map to 2.2, 5.2 and 9.2.

### [PASS] Test tasks follow their implementation tasks

Each implementation task has a following test task: 1.1/1.2, 2.1/2.2, 3.2/3.3, 3.4/3.5, 4.1/4.2, 4.3/4.4, 5.1/5.2, 5.4/5.5, 5.6/5.7, 6.1/6.2, 7.1/7.2. Task 5.3 has no test of its own, but 5.5 covers its passage fields. Dependencies run store, then operations, then the doors, then passages, then decisions, then rm, then docs and the live test.

### [PASS] Built names and paths hold

`EXPECTED_SCHEMA_VERSION` is 9 with files 001 to 009. `members.project_id` and `programs.program_id` are PRIMARY KEYs, so D1's foreign keys are valid. `PassageRef` has no `kind` (src/amoeba/answering/values.py:71), so 6.1's derivation from the source prefix is needed. `project_of` runs `cf` with no working directory when given a reference. `assemble`, `gather`, `_read_store`, `apply_removal`, `list_view`, `wiring.invoke` and the named test files all exist.

### [CONCERN] 3.2 points at a helper that cannot produce the standing rejection

3.2 says `--member` resolves "as `add --project` does", and Context Summary line 42 names `project_or_rejection` as what `add --project` uses. That function (src/amoeba/operations/project_lookup.py:22-44) returns a `SetUpResult` with `NOT_A_PROJECT` for an unknown project. Standing needs a `StandingResult` with `rejected / no_such_member`. An implementer who reuses it gets the wrong return type and code.

Fix: say 3.2 calls `project_of` directly, raises `ContextForgeError` on `CfCallFailed` (the part `project_or_rejection` shares), and maps `CFProjectNotFound` to `rejected / no_such_member` itself. Remove `project_or_rejection` from the reuse instruction.

### [CONCERN] 4.1 is six sub-steps across both doors and both docs

4.1 covers names, dispatch, the parser and renderer, MCP tools, the server instructions, two contract docs and four test-file edits, about ten files in total. The single commit is forced by the exhaustive match in `wiring.py`, but that does not make it one task.

Split it. 4.1 takes names, the wiring arm, the CLI parser, the renderer and `cli-contract.md`. The new 4.2 takes the MCP tools, the `INSTRUCTIONS` line, `mcp-server.md` and the parser-name test edits. MCP calls `wiring.invoke` and has no exhaustive match, so the split is safe. Keep one commit at the end of section 4.

### [NOTE] Development Approach order differs from the tasks

The design says passages, then `rm`, then MCP, then docs. The tasks put MCP in section 4, before passages. The reorder is harmless, since MCP only calls `wiring.invoke`, and section 3's header gives the atomicity reason. Either note it in the design during 0.2 or leave it; the design should not contradict the tasks silently.

### [NOTE] Two types are named without their home

`StandingWithdrawal` (2.1) has no module, so 3.4 cannot know where to import it. Name `store/standing.py`. 3.1 uses `NonBlankText` without saying it lives in `src/amoeba/operations/set_up_models.py:31`. Name the import so the implementer does not write a second text type.

### [NOTE] Task 5.4's required keyword has six call sites the task does not list

Current callers are `src/amoeba/operations/pause_context.py:262`, `tests/answering/test_passages.py:323` and `:442`, `tests/answering/test_program_passages.py:52` and `:109`, and `tests/answering/test_rule_dedup.py:44`. The task says "every existing caller" but gives no search. Add `grep -rn "assemble(" src tests`, as task 182 did. Keeping the keyword required is the right call under the no-silent-fallback rule.

### [NOTE] Task 9.1's second live test goes beyond the integration criteria

The design's Integration Requirements name two live checks: answered with a citation, and withdrawn means waiting. The second test (a ruling given with another member's `--member` leaves the question waiting) checks reach end to end. Unit tests in 5.7 already prove the reach rule. It costs one pre-authorized run and no criterion needs it. Keep it only if live reach coverage is wanted.

### [NOTE] 0.1 assumes the planning commit already exists

0.1 expects `git status --short --untracked-files=no` to print nothing, and says the design and this file are committed on the target. The start-of-session status shows the task file modified and the review file untracked. The planning review loop has to finish and commit first, per CLAUDE.md. This is a process precondition, not a task defect, but Phase 6 cannot pass 0.1 until that commit exists.

### Run Digest

- Response length: 7044 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 503697 / 349714 / 153973 / 42271 / not computed
- Duration: 180.4 s
- Cost: $0.26 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
