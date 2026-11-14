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
reviewedSha: f6d81384641ebc8f1f8998f556d3bfb8444cd6b0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
effort: xhigh
turns: 29
promptTokens: 1418562
cachedTokens: 1227220
cacheWriteTokens: 191322
completionTokens: 62939
durationSeconds: 269.9
costUsd: 0.397502
costBasis: provider
runId: run-20261114-p5-c32cc131
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria and decisions D1–D14 each trace to a task"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:50"
  - id: F002
    severity: pass
    category: accuracy
    summary: "Named paths and symbols resolve in the repo"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:55"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Test-with pattern holds and no NFR needs a load test"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:73"
  - id: F004
    severity: fail
    category: sequencing
    summary: "Task 9.2's full-suite gate fails until 12.1 rewrites cli-contract.md"
    location: "tests/test_contract_docs.py:100-127"
  - id: F005
    severity: fail
    category: coverage
    summary: "Task 10.1 drops the live hook path that D14 requires"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:256"
  - id: F006
    severity: concern
    category: design-gap
    summary: "The registered subjects have no defined JSON document"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:194"
  - id: F007
    severity: concern
    category: design-gap
    summary: "Paused-not-handled rows don't name their command"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:215"
  - id: F008
    severity: concern
    category: design-gap
    summary: "Task 3.7 silently skips imports that leave the repo; the design does not decide this"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:123"
  - id: F009
    severity: concern
    category: sizing
    summary: "Files already past about 300 lines take more code with no split planned"
    location: "src/amoeba/answering/passages.py"
  - id: F010
    severity: concern
    category: sizing
    summary: "Task 9.1 bundles about seven changes into one step"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:231"
  - id: F011
    severity: concern
    category: accuracy
    summary: "Task 11.1 gives a member-count command that cannot run on the install it names"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:267"
  - id: F012
    severity: concern
    category: sequencing
    summary: "The restore path leaves the target checked out in a worktree"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:272"
  - id: F013
    severity: note
    category: docs
    summary: "Commit 9.2 is labelled `refactor:` but changes behavior"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:244"
  - id: F014
    severity: note
    category: coverage
    summary: "Blocked task 11 leaves two success criteria unmet until the PM designates the store"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:266"
  - id: F015
    severity: note
    category: sequencing
    summary: "Section 11 has no commit marker, which is correct"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:263"
  - id: F016
    severity: note
    category: accuracy
    summary: "Fixtures directory already exists; 3.4 should name its exact target"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:107"
  - id: F017
    severity: note
    category: docs
    summary: "Frontmatter `dateUpdated` is after today's date"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:16"
---

# Review: tasks — slice 229

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria and decisions D1–D14 each trace to a task

Text and `-j` on every command: 7.3, 8.x, 9.2, 9.3. `add` with no flag: 5.4, 9.3. Default rules read, skipped, declined and deduplicated: 3.1 to 3.4 and 3.8. Named entries still fail: 3.2. Member settings from the CLI: 9.1 flags with the 5.1 mapping. Hook through `handle-pause` and old names gone: 11.2 and the 12.2 scan. Migration 005 is 1.1 and 1.2, config keys are 2.1 and 2.2, cutover is 11, and D14 tests each have a home. I also checked the walkthrough's paths (missed hook, `sources_missing`, `sources_too_large`, `rm` with open questions); each has a task-level route to an exit.

### [PASS] Named paths and symbols resolve in the repo

I checked the task's anchors. `kebab` is in the 220 architecture and `add --depends-on` is in the 227 design, so 0.1's grep checks pass. `cut_passages` (`answering/passages.py:149`), `RulesPath` (`answering/settings.py:59`), `answering_for` (`operations/member_answering.py:35`), `project_names`, `state_layout`, `prune_after_days`, `passages_max_chars`, the harness `set_up` call at `tests/live/pause/harness.py:106`, and the helpers in 0.1 all exist. `store/schema/` holds 001 to 004. The new modules the task asks you to create are the only missing paths.

### [PASS] Test-with pattern holds and no NFR needs a load test

Every implementation step is followed by its tests in the same commit (1.1/1.2 through 10.1). The design restates no NFR, so no load test is required.

### [FAIL] Task 9.2's full-suite gate fails until 12.1 rewrites cli-contract.md

The test requires `amoeba {value}` for every `OperationName` value. After 9.1, the enum gains `add`, `rm` and `list`, but `docs/cli-contract.md` contains none of `amoeba add`, `amoeba rm` or `amoeba list`. It still has `amoeba set_up` and `amoeba handle_pause`. Task 9.2 (line 242) says "checks pass (the full suite)", and its commit (line 244) lands before 12.1 (line 281) rewrites the doc. The commit cannot be green as written. Move the command-list update to `docs/cli-contract.md` and the matching test edit into 9.2; leave the prose rewrite in 12.1.

### [FAIL] Task 10.1 drops the live hook path that D14 requires

The design (slice D14, line 197) says the live tier "runs a pipeline that pauses, through `amoeba handle-pause` set as the hook." Task 10.1 says "The tests call `handle-pause` directly as they do today (none sets the hook)." The first run of the hook command then becomes the production cutover in 11.2. Have the pause live test set `pipeline.on_pause_command` to the absolute `amoeba handle-pause` in its own throwaway Squadron config, and assert the pause invokes it.

### [CONCERN] The registered subjects have no defined JSON document

The design (line 113) says the registered subjects "have their own documents," but neither the design nor the task says what they contain. 7.5 builds the views, and 9.3 tests `list -j` only for the status and settled cases (line 248). A junior would invent the shape for `list programs|members|dependencies -j`. Define each view's JSON in 7.5 and test it in 9.3.

### [CONCERN] Paused-not-handled rows don't name their command

8.3 says "with the command that handles them," and its tests pin exact text. The code already defines the set: `HANDLED_BY_HANDLE_PAUSE` (`src/amoeba/operations/status_runs.py:40-46`) is `unhandled`, `claim_stale` and `answered_unresumed`, all handled by `handle_pause`. The command is therefore `amoeba handle-pause RUN`. State it in 8.3, and name the calls-log source (`status_models.py:86`).

### [CONCERN] Task 3.7 silently skips imports that leave the repo; the design does not decide this

D10 (design line 161) says an import "must stay inside the repository" and gives no outcome. Task 3.7 decides "not read, no error." Under a named entry, that hides a misconfigured rule file with no signal. The project rule against silent fallback applies. Decide in the design, most likely a `sources_unreadable` decline like the depth limit, and test that outcome in 3.8.

### [CONCERN] Files already past about 300 lines take more code with no split planned

Current sizes: `passages.py` 402, `store/sql.py` 406, `wiring.py` 303, `operations/set_up.py` 305, `answering/source_reads.py` 281. Task 3.3 adds the dedup helper to `passages.py`. Tasks 3.1 and 3.7 add optional entries, `git ls-tree` and import following to `source_reads.py`. Task 1.1 threads `rules_from` through `store/sql.py`. Task 9.1 adds the add, rm and list cases to `wiring.py`. Only the CLI split (9.1) names a split. Put the dedup helper and the import-following loop in their own modules so the largest files do not grow.

### [CONCERN] Task 9.1 bundles about seven changes into one step

9.1 covers the enum change, `wiring.invoke` and `OperationResult`, MCP rows and schemas, the detached command line, the three-way split of `cli/main.py`, and about twenty `add`/`rm`/`list` flags with exclusivity rules. The "cannot be green between steps" reason covers only the enum-to-parser coupling. The `cli/main.py` split is a pure move and can be its own green step. Split into: names, wiring, MCP and detached (tests updated in the same step); the pure split; then the flag parsers with 9.3.

### [CONCERN] Task 11.1 gives a member-count command that cannot run on the install it names

It says to count members with `amoeba list members` before the change, then says the pre-slice install has no `list` and to use `amoeba status`. The first instruction cannot run. Use `amoeba status` for the pre-change count.

### [CONCERN] The restore path leaves the target checked out in a worktree

The restore step runs `git worktree add ~/amoeba-backup-229/target-tree {target}` and nothing removes it. While that worktree holds the target, the Phase 7 `git checkout {target}` is refused, and the Worktrees rule says to STOP and ask the PM. Add `git worktree remove ~/amoeba-backup-229/target-tree` after the reinstall in that step.

### [NOTE] Commit 9.2 is labelled `refactor:` but changes behavior

It makes text the default output and removes `set_up`. The commit rules reserve `refactor` for changes with no behavior change. Use `feat:`.

### [NOTE] Blocked task 11 leaves two success criteria unmet until the PM designates the store

If the PM does not designate the live store, the hook criterion and "store at version 5" stay unmet. The gate is correct: `sql.md` requires PM designation for an ALTER against a live database, and migration 005 is one. Recording it so the slice is not marked closed without it.

### [NOTE] Section 11 has no commit marker, which is correct

Section 11 changes only the live config and the installed tool, not the repo. Its record goes into the 12.2 commit.

### [NOTE] Fixtures directory already exists; 3.4 should name its exact target

`tests/answering/fixtures/` already holds `expected_passages.md` and a `sources/` tree with its own `CLAUDE.md`. Task 3.4 says to copy this repo's `CLAUDE.md` and `AGENTS.md` "into `tests/answering/fixtures/`." Name the exact subdirectory so the copies don't land beside or over the existing tree.

### [NOTE] Frontmatter `dateUpdated` is after today's date

`dateUpdated: 20261114`; today is 2026-11-13. Correct it to the actual edit date.

### Run Digest

- Response length: 11029 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 29
- Tokens — prompt / cached / cache write / completion / reasoning: 1418562 / 1227220 / 191322 / 62939 / not computed
- Duration: 269.9 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
