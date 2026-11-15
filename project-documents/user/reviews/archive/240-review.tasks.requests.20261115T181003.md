---
docType: review
layer: project
reviewType: tasks
slice: requests
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/240-tasks.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: de127237bc720d21db78f59c29b0e583a38e88b7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
effort: xhigh
turns: 25
promptTokens: 984679
cachedTokens: 789989
cacheWriteTokens: 194676
completionTokens: 73188
durationSeconds: 333.5
costUsd: 0.404699
costBasis: provider
runId: run-20261115-tasks-plan-16a0f352
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: deferral
    summary: "Timing bound defers a term to slice 242"
    location: "project-documents/user/tasks/240-tasks.requests.md:254-257"
  - id: F002
    severity: fail
    category: gate
    summary: "Section 11 cannot meet its own gate"
    location: "project-documents/user/tasks/240-tasks.requests.md:243-246"
  - id: F003
    severity: fail
    category: test-spec
    summary: "Load test asserts functional correctness only"
    location: "project-documents/user/tasks/240-tasks.requests.md:197-199"
  - id: F004
    severity: concern
    category: ci-gating
    summary: "Load-test CI gating is implicit"
    location: ".github/workflows/ci.yml:40"
  - id: F005
    severity: concern
    category: coverage
    summary: "D11 notice on `list` and `status` descriptions has no task"
    location: "src/amoeba/mcp/tools.py:113-126"
  - id: F006
    severity: concern
    category: ownership
    summary: "Operator walkthrough's Start step has no owner"
    location: "project-documents/user/slices/240-slice.requests.md:351"
  - id: F007
    severity: concern
    category: ownership
    summary: "Backup cleanup has no owner"
    location: "project-documents/user/tasks/240-tasks.requests.md:44"
  - id: F008
    severity: concern
    category: sequencing
    summary: "Live migration runs before code review and merge"
    location: "project-documents/user/tasks/240-tasks.requests.md:301-307"
  - id: F009
    severity: concern
    category: commit-cadence
    summary: "Commit markers sit after nearly every section"
    location: "project-documents/user/tasks/240-tasks.requests.md"
  - id: F010
    severity: concern
    category: test-with
    summary: "Test-with pattern broken in section 11"
    location: "project-documents/user/tasks/240-tasks.requests.md:247-253"
  - id: F011
    severity: concern
    category: duplication
    summary: "Config values are written in two places"
    location: "project-documents/user/tasks/240-tasks.requests.md:105"
  - id: F012
    severity: concern
    category: clarity
    summary: "The read-back in 15.1 names no walkthrough or command"
    location: "project-documents/user/tasks/240-tasks.requests.md:305"
  - id: F013
    severity: note
    category: granularity
    summary: "Granularity: merge the pure moves"
    location: "project-documents/user/tasks/240-tasks.requests.md:108-116"
  - id: F014
    severity: note
    category: formatting
    summary: "Markdown: blank line missing before a commit marker"
    location: "project-documents/user/tasks/240-tasks.requests.md:269"
  - id: F015
    severity: note
    category: deferral-check
    summary: "Note retention split agrees with slice 243"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:201"
  - id: F016
    severity: pass
    category: coverage
    summary: "`list` records expiry through the same sweep"
    location: "src/amoeba/operations/list_view.py:166"
  - id: F017
    severity: pass
    category: coverage
    summary: "`QUOTED_DATA_NOTICE` importer list is complete"
    location: "src/amoeba/operations/changes_models.py"
  - id: F018
    severity: pass
    category: coverage
    summary: "Success criteria map to named tests"
    location: "project-documents/user/slices/240-slice.requests.md:278-295"
  - id: F019
    severity: pass
    category: sequencing
    summary: "Sequencing and prerequisite paths"
    location: "project-documents/user/tasks/240-tasks.requests.md:51-52"
---

# Review: tasks — slice 240

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Timing bound defers a term to slice 242

11.5 sets `EXTRA_WAIT_SECONDS` to 0.0 for all four operations "now" and leaves the 30 s `START_BOUND_SECONDS` term to 242, which will edit this slice's constant and test. The slice design's Technical Requirement (project-documents/user/slices/240-slice.requests.md:291) asks for that term in this slice's worst-case test. The Amoeba "No deferral" rule rejects a breakdown that defers in-scope behavior to a later slice. Fix: define the start-wait value in `wiring_messages.py` now, use it in the worst-case assertion and in the over-bound test. A conservative bound is acceptable; 242 then wires the wait it adds without editing this test.

### [FAIL] Section 11 cannot meet its own gate

11.1 adds `SEND`, `INBOX`, `REPLY` and `CANCEL` to `OperationName`. `tests/test_contract_docs.py:305-312` requires every `OperationName` value to appear backticked in `docs/mcp-server.md`. 11.2 does not add those names to that doc; only 13.1 does. So `test_contract_docs.py` still fails after 11.2 and 11.3, and the "checks pass (whole suite)" gate in 11.4 and the commit marker at 259 cannot be met. This also breaks the breakdown's own rule (Context Summary: each task that adds a contract entry adds it then). Fix: add the four tool names to `docs/mcp-server.md` in 11.2, names only, with the prose left to 13.1.

### [FAIL] Load test asserts functional correctness only

`.claude/rules/python.md` requires load tests for concurrency paths to "assert on latency, throughput, or resource bounds — not just functional correctness." 9.3's assertions are all functional: no `busy`, every send stored, one winner, unique `seq`, consistent `as_of_seq`. The task is rule-required, so it is not scope creep, but as written it is not a load test under the rule. Fix: add a measured per-call latency ceiling, a throughput floor for the run, and a bounded wall-time or resource check, each as a named constant.

### [CONCERN] Load-test CI gating is implicit

No task states how CI gates the load test. CI runs a bare `uv run pytest` (line 40). `pyproject.toml:59-64` sets `testpaths = ["tests"]` and ignores only `tests/live`, so `tests/load` is collected in CI today. The gate exists, but nothing in the breakdown says so, and the rule says gating must not be left implicit. Fix: state in 9.3 that the bare CI run gates it, with the FAIL-3 bounds as the gate. Put the thresholds in one constant so they can be tuned for CI hardware.

### [CONCERN] D11 notice on `list` and `status` descriptions has no task

The slice design (line 208) requires the `list` and `status` tool descriptions to carry the notice. Only 11.2 touches tool descriptions, and it covers only the four new tools. The `ToolSpec` rows for `LIST` (line 113) and `STATUS` (line 126) are not assigned to any task. Fix: add those two description updates to 10.3 or 11.2, with a parity assertion in 11.2's tests.

### [CONCERN] Operator walkthrough's Start step has no owner

The design's Start step pastes the Requesting and Handling blocks into each member repo's rules file ("an agent in each repo does it as a commit"). 13.2 writes the blocks only into `docs/program-rules.md`. No task installs them, so no member carries the Handling block, and nothing tells agents to check `inbox`. The walkthrough's "Nothing else" also omits that the live migration breaks already-open sessions until they restart; 15.1 notes this but the walkthrough does not. Fix: name the mechanism the existing Consumer and Provider blocks use, add an install step for the fixture repos in 14.1, and add a restart line to the Start step.

### [CONCERN] Backup cleanup has no owner

The context summary says the two backups "are removed by the Phase 7 integration step, not by a task here." The git rules define Phase 7 as the merge only, and nothing in the breakdown deletes the backups. Fix: add a sub-item under 15.2 that removes the two backup files after the review passes, with the look-before-delete step, or add the deletion to the merge procedure as a numbered step.

### [CONCERN] Live migration runs before code review and merge

15.1 installs the slice build over the live tool and migrates the live store to version 6 while still in Phase 6. The git rules put code review and merge in Phase 7. If review changes migration 006, the CHECKs, or the config keys, the live store must be restored and migrated again, and the newer-schema guard refuses a downgrade. Fix: move 15 to after the Phase 7 merge, or make a passed review a stated precondition of 15.1.

### [CONCERN] Commit markers sit after nearly every section

There are 20 markers across 15 top-level tasks (lines 68, 87, 99, 118, 137, 148, 162, 176, 187, 201, 212, 222, 229, 236, 259, 269, 280, 288, 297, 313). Every section from 1 to 15 ends with one, which is "after every task", not at working points. Suggested cut to about 10: keep the markers after 1, 2.6, 3, 4 with 5, 8 (send, reply and cancel together), 9, 10.6, 11, 12 with 13, 14 and 15. Drop those after 2.4, 10.2, 10.4 and 10.5.

### [CONCERN] Test-with pattern broken in section 11

11.3 implements the CLI commands, parser, renderers and docs, but their tests come in 11.4. 11.1 leaves three suites red with no tests written, and 11.5's constants are defined in 11.1. Fix: move each CLI command's test file into 11.3, and keep 11.4 for parser names and the parity test.

### [CONCERN] Config values are written in two places

The slice design (line 213) says the suggested values 72 and 3 "appear once, in the contract's example, and a test loads that example." 3.1 also puts them in the `tests/user_configs.py` builders. A changed doc value does not reach the builders. Fix: build the test config from the contract example block that 3.1 already loads, so the numbers live in one place.

### [CONCERN] The read-back in 15.1 names no walkthrough or command

"Over the live MCP walkthrough's stdio client" names no file or command. The design's Verification Walkthrough has no MCP step, and `tests/live/mcp` exists but is not named. An implementing agent cannot run this as written. Fix: name the command and confirm it drives the installed `amoeba-mcp`, then give the expected tool names.

### [NOTE] Granularity: merge the pure moves

3.2, 3.3 and 3.4 are three pure moves, each with a one-line success check. Merge them into one "shared helper moves" task with three sub-items. Merge 4.1–4.3, whose success lines are all "pyright clean", the same way.

### [NOTE] Markdown: blank line missing before a commit marker

The 12.2 marker follows the checkbox with no blank line. CommonMark folds it into the list item, so the plain marker can render inside the item. Add a blank line before it.

### [NOTE] Note retention split agrees with slice 243

243 D6 takes the note prune and the aged-note due check (also line 265), which matches 13.3's amendment of this slice's D6 (line 174). This is not a gap because 240 writes no notes. It stays acceptable only while 240 writes none, and 2.6's directly inserted note row covers the 240 side.

### [PASS] `list` records expiry through the same sweep

`list_view` calls `status(`, so the sweep that 10.3 places in `status.py` also runs for `list`. 12.2's expiry-through-`list` test is supported.

### [PASS] `QUOTED_DATA_NOTICE` importer list is complete

3.2's list matches a repo-wide search exactly: `changes_models.py`, `mcp/tools.py`, `cli/render/releases.py`, `tests/mcp_server/test_tools.py`, `tests/test_program_rules_doc.py`, `tests/cli/render/test_releases.py`, and `docs/cli-contract.md`. The constant name does not appear in `docs/program-rules.md`, so that edit is wording only.

### [PASS] Success criteria map to named tests

Each functional and technical criterion maps to a named test in the breakdown, with one exception: the timing clause (see the first FAIL). The integration criteria map to 11.2 and 10.4.

### [PASS] Sequencing and prerequisite paths

Dependencies run store, then config, models, member resolution, operations, doors, end-to-end, docs and live, with no cycles. Every helper and prerequisite path the breakdown names exists: `store/schema/` holds 001–005, plus `project_of.py`, `wiring.py`, `wiring_releases.py`, `test_migration_005.py`, `tests/user_configs.py`, and the rest. Each test task follows its implementation, apart from the section-11 case noted above.

### Run Digest

- Response length: 11657 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 984679 / 789989 / 194676 / 73188 / not computed
- Duration: 333.5 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19
