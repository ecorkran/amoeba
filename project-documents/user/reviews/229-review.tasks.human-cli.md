---
docType: review
layer: project
reviewType: tasks
slice: human-cli
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/229-tasks.human-cli.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: e8b8decfb7057892b25c8c8f3ef4b00ffd6e223b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
effort: xhigh
turns: 26
promptTokens: 1595386
cachedTokens: 1395487
cacheWriteTokens: 199875
completionTokens: 75528
durationSeconds: 325.0
costUsd: 0.445667
costBasis: provider
runId: run-20261114-p5-c32cc131
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Rename misses a user-facing error that names the removed command"
    location: "src/amoeba/operations/answer.py:96-97"
  - id: F002
    severity: concern
    category: verification
    summary: "The old-name scan in 12.2 has an exemption no one can apply"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:294"
  - id: F003
    severity: concern
    category: operator-walkthrough
    summary: "Cutover re-run dead end: the backup refuses an existing directory with no next step"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:277"
  - id: F004
    severity: concern
    category: operator-walkthrough
    summary: "\"Unplaced runs\" has no action, and the design gives none"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:216"
  - id: F005
    severity: concern
    category: sizing
    summary: "Task 3.1 bundles two separable changes under a check that cannot test behavior"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:90-94"
  - id: F006
    severity: concern
    category: sizing
    summary: "Task 9.3 is too large for a pyright-only check"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:244-247"
  - id: F007
    severity: note
    category: sequencing
    summary: "9.2 leaves the CLI unimportable until 9.3; the suite stays red until 9.4"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:243"
  - id: F008
    severity: note
    category: consistency
    summary: "Design D4 contradicts itself on `--no-rules` for a new member"
    location: "project-documents/user/slices/229-slice.human-cli.md:128"
  - id: F009
    severity: note
    category: sizing
    summary: "Size counts in the Context Summary are understated"
    location: "src/amoeba/store/sql.py"
  - id: F010
    severity: note
    category: metadata
    summary: "Frontmatter `dateUpdated` is tomorrow's date"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:16"
  - id: F011
    severity: note
    category: sizing
    summary: "7.5 is large but coherent"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:194-198"
  - id: F012
    severity: pass
    category: coverage
    summary: "All six parent success criteria have a task"
    location: "project-documents/user/tasks/229-tasks.human-cli.md"
  - id: F013
    severity: pass
    category: sequencing
    summary: "Test steps follow their implementation steps; no cycles"
    location: "project-documents/user/tasks/229-tasks.human-cli.md"
  - id: F014
    severity: pass
    category: verification
    summary: "Dependency and fact claims check out against the source tree"
    location: "src/amoeba/operations/status_runs.py:40-46"
  - id: F015
    severity: pass
    category: process
    summary: "The PM-designation gate is rule-required, and no in-scope behavior is deferred"
    location: "project-documents/user/tasks/229-tasks.human-cli.md:276"
---

# Review: tasks — slice 229

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Rename misses a user-facing error that names the removed command

`answer` tells the operator to run ``amoeba handle_pause {run_id}``. After 9.3 that command exits 2. No task edits `answer.py`: 8.5 changes how `answer` results are printed, not the detail text, and 9.2 covers only `names.py`, `wiring.py`, `mcp/tools.py` and `mcp/detached.py`. The 12.2 scan covers `src` and matches this line, so 12.2's success check fails as written. Name `answer.py` in 9.2 or 12.2, and say the message should give `amoeba handle-pause`.

### [CONCERN] The old-name scan in 12.2 has an exemption no one can apply

12.2 excludes "this file and the old-name cases of 9.4". 9.4 puts the old-name cases (`set_up`, `handle_pause`, `mark_read` exiting 2) in `tests/cli/test_parser_names.py`, the same file that asserts the new names. Excluding the file hides the new-name checks. Excluding lines needs a convention the task never defines. Have 9.4 mark each old-name case with a named marker, and have the scan skip only marked lines.

### [CONCERN] Cutover re-run dead end: the backup refuses an existing directory with no next step

11.1 says to refuse if `~/amoeba-backup-229` exists. The restore step in 11.2 depends on that same directory, so after a restore the cutover cannot be retried, and no step says what to do about it. Under the Amoeba rule that every limit says what happens when it is hit, state the exit. The simplest is a per-attempt backup name, with the restore step naming the one it uses.

### [CONCERN] "Unplaced runs" has no action, and the design gives none

8.3 renders Unplaced runs with no command. `status_placement.py:66-75` lists a paused run as unplaced for three reasons: `no_directory`, `directory_missing` and `lookup_failed`. `handle-pause` runs in the run's own checkout, so it cannot clear the first two. The design (D3, `229-slice.human-cli.md:109`) has the same gap. The design needs an exit for each reason. For `lookup_failed` the next `list` can retry once `cf` answers. For the other two, name the command that ends the run, or say how the run closes.

### [CONCERN] Task 3.1 bundles two separable changes under a check that cannot test behavior

3.1 changes the settings type through `answering_for`, `AnswererSettings`, `pause_context.py` and every reader. It moves `_select_rules` into `rule_entries.py`, adds optional-entry skipping with `SelectedFile.optional`, and adds the `git ls-tree` absence check. Its only success check is "pyright clean; existing tests pass", so the new behavior is first checked in 3.2. Split into 3.1a (choice plumbing; named members unchanged, checked by the existing tests) and 3.1b (optional entries and `ls-tree`, with its own check).

### [CONCERN] Task 9.3 is too large for a pyright-only check

9.3 builds the parent parser and `-j`, registers every command by `cli_name`, writes a runner per command, and adds about a dozen `add` flags with their exclusivity and `--file` conflicts. It also adds the `rm` and `list` flags (with the `--all` exit-2 rule), the CF-name lookup for renderers, and the exit-code mapping. Its only check is "pyright clean". Split into 9.3a (parser, `-j`, runners for the existing commands) and 9.3b (`add`, `rm`, `list` flags and request building), each checked by the 9.5 tests it feeds.

### [NOTE] 9.2 leaves the CLI unimportable until 9.3; the suite stays red until 9.4

This is acceptable because no commit marker sits between 9.1 and 9.4, so history stays green. But the checks will fail in `tests/cli`, `tests/test_contract_docs.py` and the live tiers after 9.2 and 9.3, and neither success line says so. One sentence in each would stop a junior from "fixing" expected failures.

### [NOTE] Design D4 contradicts itself on `--no-rules` for a new member

D4 says `--no-rules` "stores none", and also that none of the three flags "gives a new member the default". Tasks 5.1 and 4.2 map `--no-rules` to `rules_paths: []` (named and empty). D7 supports that reading ("an empty list is already a valid named choice"). Fix the design sentence, and list this choice in the task Context Summary with the other decisions made where the design is silent.

### [NOTE] Size counts in the Context Summary are understated

The Context Summary calls `passages.py`, `store/sql.py`, `wiring.py`, `set_up.py` and `source_reads.py` "at or near 300 lines". The actual counts are `store/sql.py` 406, `answering/passages.py` 402, `operations/set_up.py` 305, `wiring.py` 303 and `answering/source_reads.py` 281. Two files are well past the rule already. The "call sites only" approach is still right, but the agent should be told the real numbers.

### [NOTE] Frontmatter `dateUpdated` is tomorrow's date

`dateUpdated: 20261114`, and today is 2026-11-13. If a tool wrote it, check the writer. Otherwise correct it.

### [NOTE] 7.5 is large but coherent

It covers three registered views, three JSON models, the `cf` failure path, the not-in-CF marker and the program filter, under one "pyright clean" check. It stays in one module and 7.6 tests it, so I would not split it. It is the longest step in section 7, and the planner should expect that.

### [PASS] All six parent success criteria have a task

Text and `-j` on every command, and `list -j` equal to the status document (8.x, 9.3, 9.5). `add` with no flag, and the clear error otherwise (5.3, 5.4, 8.2, 9.5). Default rules read with each section once, and `sources_missing` naming what was tried (3.1 to 3.4). Named entries still fail (3.2). Every member setting from the CLI (9.3 flags against the `MemberRequest` fields, plus `rm --concept`). The hook through `handle-pause`, and the old name gone (10.1, 11.2, 11.3, and the 12.2 scan, subject to the findings above).

### [PASS] Test steps follow their implementation steps; no cycles

Each implementation step is followed by its tests: 1.1/1.2, 2.1/2.2, 3.1/3.2, 3.3/3.4, 3.5/3.6, 3.7/3.8, 4.1/4.2, 5.1/5.2, 5.3/5.4, 6.1/6.2, 7.3/7.4, 7.5/7.6, 9.3/9.4-9.5. Steps 7.1, 7.2, 8.x and 9.2 carry their own tests. Ordering holds: 4.1 before 5.1 and 8.2, 7.1 before 7.5, 9.1 before 9.2.

### [PASS] Dependency and fact claims check out against the source tree

Confirmed: `store/schema/` holds 001 to 004 only; `config/home.py` has `state_layout`; `operations/dismiss.py` and `mcp/tools.py` exist; `cli/main.py:161` holds `build_parser`; `tests/live/pause/harness.py:106` calls `set_up`; `HANDLED_BY_HANDLE_PAUSE` is exactly unhandled, claim_stale and answered_unresumed, as 8.3 says; `RunEntry.last_call` exists (`status_models.py:88`); the config and state homes and file names match 11.1. Not verified: the `cf list projects --json` shape, `sq config set --help`, and the git target and branch state.

### [PASS] The PM-designation gate is rule-required, and no in-scope behavior is deferred

The designation 11.1 asks for is what `sql.md` requires for an ALTER on the live store, so it is not a finding. Nothing in scope is deferred to an issue or a later slice.

### Run Digest

- Response length: 9014 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 1595386 / 1395487 / 199875 / 75528 / not computed
- Duration: 325.0 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Resolution

- [concern] Rename misses a user-facing error that names the removed command: fixed. 9.2 now renames the `no_such_question` detail in `operations/answer.py` to `amoeba handle-pause`, updates the `mcp/tools.py` description and the `mcp/detached.py` docstring, and updates the `answer` test that asserts the detail.
- [concern] The old-name scan in 12.2 has an exemption no one can apply: fixed. 9.4 ends each old-name case line with the comment `# old-name-case` and nothing else in the file; 12.2's scan skips only lines carrying it (and its own file, which holds the patterns).
- [concern] Cutover re-run dead end: fixed. 11.1 backs up to a new per-attempt directory `~/amoeba-backup-229-<UTC stamp>` (BACKUP), so an old one never blocks a retry; the restore step uses the literal path recorded in 11.1.
- [concern] "Unplaced runs" has no action, and the design gives none: fixed. 8.3 and design D3 now say each reason's exit: `lookup_failed` clears on the next `list` once `cf` answers; `no_directory` and `directory_missing` are Squadron runs with no Amoeba record and leave the list when Squadron stops listing them as paused. No command is offered, since `handle-pause` needs the run's own checkout and `sq runs` has no cancel command.
- [concern] Task 3.1 bundles two separable changes under a check that cannot test behavior: fixed. Split into 3.1 (choice plumbing, with new `answering_for` cases in `test_member_answering.py`) and 3.1b (optional entries and `ls-tree`, tested in 3.2).
- [concern] Task 9.3 is too large for a pyright-only check: fixed. Split into 9.3 (parent parser, `-j`, runners for the existing commands) and 9.3b (`add`, `rm`, `list` and their flags); each success line adds `--help` runs.
- [note] 9.2 leaves the CLI unimportable until 9.3; the suite stays red until 9.4: fixed. The success lines of 9.2, 9.3 and 9.3b name the tests expected to fail (`tests/cli`, `tests/test_contract_docs.py`, the live tiers) and say not to fix them there.
- [note] Design D4 contradicts itself on `--no-rules` for a new member: fixed. D4 now says `--no-rules` stores an empty named list and only giving none of the three flags gives a new member the default; the choice is listed in the task Context Summary decisions.
- [note] Size counts in the Context Summary are understated: fixed. The summary now gives the real counts (`store/sql.py` 406, `passages.py` 402, `set_up.py` 305, `wiring.py` 303, `source_reads.py` 281).
- [note] Frontmatter `dateUpdated` is tomorrow's date: fixed (20261113). The review pipeline writes 20261114 on each run, so it may need correcting again after the next one.
- [note] 7.5 is large but coherent: no change. The review itself recommends against splitting; it stays one module with 7.6 testing it.
- [pass] All six parent success criteria have a task: no change needed.
- [pass] Test steps follow their implementation steps; no cycles: no change needed.
- [pass] Dependency and fact claims check out against the source tree: no change needed.
- [pass] The PM-designation gate is rule-required, and no in-scope behavior is deferred: no change needed.
