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
reviewedSha: 65e3ebda05503b34b5edb61cd316209ca282d7c5
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
effort: xhigh
turns: 23
promptTokens: 716725
cachedTokens: 543921
cacheWriteTokens: 172792
completionTokens: 67019
durationSeconds: 288.0
costUsd: 0.354999
costBasis: provider
runId: run-20261114-p5-0e7feed2
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion traces to at least one task"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:222"
  - id: F002
    severity: pass
    category: verification
    summary: "Prerequisite and existing-code claims match the repo"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:58"
  - id: F003
    severity: pass
    category: consistency
    summary: "Parent-document pending edits are already applied"
    location: "project-documents/user/architecture/220-arch.program-tool.md:107"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing is acyclic and tests follow their implementation"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:64"
  - id: F005
    severity: concern
    category: process
    summary: "Task 0.1 commits both planning documents in one commit"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:57"
  - id: F006
    severity: concern
    category: testing
    summary: "The worktree case proves SC4 only against a replayed `cf`"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:218"
  - id: F007
    severity: concern
    category: dry
    summary: "The member-resolution rejection mapping is specified twice"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:116"
  - id: F008
    severity: concern
    category: scope
    summary: "The wiring split is not in the design, and no criterion needs it"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:144"
  - id: F009
    severity: concern
    category: granularity
    summary: "The live test changes a shared harness and leaves the design choice open"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:222"
  - id: F010
    severity: concern
    category: testing
    summary: "The no-commits case in the walkthrough is never asserted"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:216"
  - id: F011
    severity: note
    category: verification
    summary: "The diff check doesn't name the file that holds the schema version"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:228"
  - id: F012
    severity: note
    category: typing
    summary: "Two closed vocabularies are not named as StrEnums"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:47"
  - id: F013
    severity: note
    category: duplication
    summary: "The flow test may duplicate an existing program rig"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:212"
  - id: F014
    severity: note
    category: scope
    summary: "Pasting the rule blocks into member repos is outside this breakdown"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:44"
---

# Review: tasks — slice 227

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion traces to at least one task

SC1 → 1.3, 3.2, 6.1. SC2 → 1.2, 2.4, 3.2. SC3 → 2.4, 3.2, 6.1. SC4 → 6.1 (see the worktree concern). SC5 → 2.4, 3.2, 4.2, 4.3. SC6 → 3.2, 4.2. SC7 → 6.2, 6.3, 4.4, 5.3. SC8 → 6.1, 6.2. No criterion is without a task.

### [PASS] Prerequisite and existing-code claims match the repo

The reflog shows merges for 224, 225, 226, 228 and 229. `wiring.py` is 324 lines, as 3.3 says. `OperationName` has ten members. `RejectCode` has three, and `test_the_rejection_codes_are_the_three_the_design_names` exists at `tests/operations/test_decisions_request.py:102`. `EXPECTED_SCHEMA_VERSION` is 5 at `src/amoeba/store/migrations.py:25`. The test names, helpers and doc headings the tasks cite also exist: `test_parser_names.py:48` ("eleven"), `test_stdio_smoke.py:71` (dynamic count), `DIRECTORY_TOOLS`/`READ_TOOLS`, `FakeCf`, `git()`, `build_world`, `run_amoeba`, and the `releases` heading in `store-contract.md`.

### [PASS] Parent-document pending edits are already applied

Decision 3 (versioning replaces text, correction, withdrawal) is at line 107. Decision 4 (explicit starting point) is at line 111. The "no gate" Anticipated Slices text is at line 202. Entry 9 in `220-slices` (lines 162–171) has the flow-test and correction criteria. No task is needed for these.

### [PASS] Sequencing is acyclic and tests follow their implementation

Sections run 1 → 6 with no back-references. Each use comes after its definition: 2.1 before 3.1, 2.2 before 2.4, 5.2 creates `rule_blocks` before 6.1 imports it, 3.3 before 3.4 edits `wiring.py`. Each implementation item is followed by its tests. The red window in section 4 is declared, and its single commit sits at 4.4, where the suite is green.

### [CONCERN] Task 0.1 commits both planning documents in one commit

The planning rule is one commit per document, made when its review loop finishes. 0.1 commits the design and the task file together as `docs: add the slice 227 design and task breakdown`. Both files are mid-review: HEAD is `review: FAIL` round 1 and both show uncommitted revisions. Remove the commit step from 0.1. Planning commits belong to the planning phase, one per document.

### [CONCERN] The worktree case proves SC4 only against a replayed `cf`

6.1's worktree case has the replayed `cf` return one project id for both directories. 6.2, the live test, has no worktree case. So SC4 would pass even if real `cf` can't resolve a `git worktree add` directory to its member. Whether it can is unverified, and `AGENTS.md`'s worktree rules show `cf` tracks worktrees per checkout. Add a live step: create a worktree of the consumer, run `changes` from it, and record the outcome. Otherwise, state in the breakdown that this assumption is unverified.

### [CONCERN] The member-resolution rejection mapping is specified twice

2.4 and 3.2 each resolve the directory with `resolve_member` and map `NotInProgram` and `NotAProject` to `not_a_member` details. 3.2 says "details as in 2.4", which makes it a second copy. The codebase already holds this kind of duplication: `NOT_A_PROJECT_DETAIL` appears in `add.py:42` and `rm.py:38`. CLAUDE.md forbids the pattern. Have 2.4 create one helper that returns the problem or the member, and have 3.2 call it.

### [CONCERN] The wiring split is not in the design, and no criterion needs it

3.3 moves four names out of `wiring.py` into a new `wiring_deadline.py`. The design's Architecture lists `wiring.py` only for two invoke cases and does not list the new module. `wiring.py` was already over the 300-line guideline before this slice, and the guideline is "where practical". No success criterion depends on the move. Either drop 3.3, or add the module to the design's Architecture with the reason.

### [CONCERN] The live test changes a shared harness and leaves the design choice open

6.2 asks for a `join` argument on `build_world` in `tests/live/pause/harness.py` (defined at line 68; it creates `cf-data` at line 89), plus a shared `cf-data`, a shared `AMOEBA_HOME` and a member name. It also says "note the choice under this task", which hands the design decision to the implementer. The design needs two throwaway members, real `cf` and `git`, and a throwaway `AMOEBA_HOME`. Build that in `tests/live/program/conftest.py` and leave the pause harness unchanged. That keeps the change out of the pause live tests.

### [CONCERN] The no-commits case in the walkthrough is never asserted

The design's Operator Walkthrough says a repo with no commits yields an empty `since` from both git commands, `changes` rejects it as `malformed`, and the agent records the error. 6.1's no-previous-design case covers only "no design under the slices path, root commit exists". 3.1 tests that an empty `since` is rejected, but nothing runs the rule block's commands in a repo with no commits. Add that case to 6.1. Assert on stdout only: `git log` exits non-zero in an empty repo.

### [NOTE] The diff check doesn't name the file that holds the schema version

`EXPECTED_SCHEMA_VERSION` lives in `src/amoeba/store/migrations.py:25`. A diff of `src/amoeba/store` will also show `releases.py`, `models.py` and `sql.py`, so "shows no schema file" is ambiguous. Name the file and require `git diff {target} -- src/amoeba/store/migrations.py` to be empty.

### [NOTE] Two closed vocabularies are not named as StrEnums

The Context Summary lists the closed StrEnums but omits `ChangesWarning.code` (`not_in_context_forge`) and `ReleaseProblem.code`, which the design says is a `RejectCode`. 3.2 and 4.1 both hard-code the warning string. Name the warning code as a StrEnum, and type `ReleaseProblem.code` as `RejectCode`.

### [NOTE] The flow test may duplicate an existing program rig

`tests/operations/program_rig.py` already builds program repos with dated commits (`commit_file` with `CONCEPT_COMMIT_DATE` and `LATER_COMMIT_DATE`, around line 120). 6.1 asks for new provider and consumer repos built from `git_repo.py`. Check the rig first and reuse or extend it.

### [NOTE] Pasting the rule blocks into member repos is outside this breakdown

The breakdown puts pasting the blocks into member repos out of scope, and the design's Operator Walkthrough assigns it to an agent session in each repo after merge. No success criterion requires it, and it is an operator step rather than development work, so I'm not raising it as a deferral. No change is needed here. Until those pastes happen, no repo produces or reads these reports.

### Run Digest

- Response length: 9260 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 716725 / 543921 / 172792 / 67019 / not computed
- Duration: 288.0 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

- [pass] Every success criterion traces to at least one task: no change needed.
- [pass] Prerequisite and existing-code claims match the repo: no change needed.
- [pass] Parent-document pending edits are already applied: no change needed.
- [pass] Sequencing is acyclic and tests follow their implementation: no change needed.
- [concern] Task 0.1 commits both planning documents in one commit: fixed. 0.1 now makes one commit per document (design, then task breakdown).
- [concern] The worktree case proves SC4 only against a replayed `cf`: fixed. Task 6.2 adds a second consumer worktree resolved through real `cf` to the same member, with different `since` values giving different results.
- [concern] The member-resolution rejection mapping is specified twice: fixed. 2.4 defines `resolve_release_member` once in `operations/release_member.py`; 3.2 calls it, and the detail tests live only in 2.4.
- [concern] The wiring split is not in the design, and no criterion needs it: fixed by removing task 3.3 and its commit. `wiring.py` was already 324 lines before this slice; the slice adds only about 15 lines there, and the design never planned a split. Section 3 is renumbered.
- [concern] The live test changes a shared harness and leaves the design choice open: fixed. 6.2 leaves `tests/live/pause/harness.py` unchanged. It builds the provider with `build_world` and the consumer in a helper under `tests/live/program/` that shares the provider's `cf-data` directory and `AMOEBA_HOME`.
- [concern] The no-commits case in the walkthrough is never asserted: fixed. 6.1 asserts that both git commands print nothing in a repo with no commits, and that `changes` with the empty `since` is `rejected` / `malformed`.
- [note] The diff check doesn't name the file that holds the schema version: fixed. 6.3 names `EXPECTED_SCHEMA_VERSION` in `store/migrations.py`.
- [note] Two closed vocabularies are not named as StrEnums: fixed. 3.1 adds `ChangesWarningCode(StrEnum)`, a problem's `code` is typed `RejectCode`, and the context summary lists both.
- [note] The flow test may duplicate an existing program rig: fixed. 6.1 states that `status_support.FakeCf` is used and that `program_rig.py` serves one concept repo with one project and does not fit.
- [note] Pasting the rule blocks into member repos is outside this breakdown: rejected, no change. The context summary already marks it out of scope. Those are commits in other repos by their own agent sessions after merge, and this slice delivers the blocks and the tests that prove them.
