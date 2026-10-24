---
docType: review
layer: project
reviewType: tasks
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: e41246d24b05a99ada84bc91189ff0ed68ad4780
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 227891
cachedTokens: 112115
cacheWriteTokens: 115770
completionTokens: 9900
durationSeconds: 76.8
costUsd: 0.574112
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Task 11.2 points at a slice-plan path that does not exist"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:404"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "Unknown-status blocking is tied to creation, and the re-block case is untested"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:298"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 8.3 is overweight and should be split"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:290-303"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 9.2 wires failure-to-fault behavior without tests, and the closure rule lands one task later"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:349"
  - id: F005
    severity: concern
    category: coverage-gap
    summary: "Verification walkthrough step 4 (rename and renumber with the real `cf`) is dropped"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:418"
  - id: F006
    severity: concern
    category: scope
    summary: "Task 4.1 is labeled `refactor:` but changes behavior, and it moves the CF command constants out of `plan_read.py`"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:128-139"
  - id: F007
    severity: note
    category: clarity
    summary: "Task 5.3's \"eligible slice\" bullet is garbled"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:175"
  - id: F008
    severity: note
    category: clarity
    summary: "`reconcile`'s `faults` parameter is undefined"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:264"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criterion coverage is complete"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md"
---

# Review: tasks — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 11.2 points at a slice-plan path that does not exist

Task 11.2 edits `project-documents/user/slices/120-slices.runner-routing-engine.md`. That file is not there. The slice plan is `project-documents/user/architecture/120-slices.runner-routing-engine.md`, which is also the LLD's `parent:` value. The only `120-*` file under `slices/` is `120-slice.run-identity-and-supported-run-surfaces.md`. A junior would stall, or create a new file, and the criterion "`git diff --stat` touches only these three files" would then fail. Correct the path.

### [CONCERN] Unknown-status blocking is tied to creation, and the re-block case is untested

The LLD (D6) requires that a `degraded` or out-of-vocabulary status block the slice with `plan_status_unknown`. It also requires that a block the PM resolves while the status is still unknown is re-applied on the next read. Task 8.3 puts this rule inside the create rule ("the slice gets four `runnable` steps and is blocked"). Two cases then have no home:
- A slice that already exists and later turns `degraded`. The create rule never revisits linked nodes.
- A resolved block that must be re-applied. Task 8.3's test only checks that the slice is "still blocked after a second identical read", never that it is blocked again after being resolved.

State which rule re-evaluates existing linked slices, and add a test for resolve-then-re-block and for a known-to-unknown transition. These behaviors are covered by the LLD's "degraded slice … is blocked" criterion.

### [CONCERN] Task 8.3 is overweight and should be split

Task 8.3 bundles six things:
- the `reconcile` entry point;
- node and step creation;
- the `slugs.py` stem rule;
- D6 statuses, including deferred and deprecated slices;
- unknown-status blocking;
- the AST guard test with its self-test.

It has about nine test groups and a single commit. Split it into three tasks, each with its own commit:
- create and statuses;
- slug stem and unknown status;
- the `create_node` guard (D10), which is independent of reconcile logic and can follow immediately.

### [CONCERN] Task 9.2 wires failure-to-fault behavior without tests, and the closure rule lands one task later

Task 9.2 adds `PlanReadFailed` → `record_failed` + `plan_read_failed` fault, and "slice-level failure counts as failed". Its tests cover none of these paths. They are tested only in 9.3, which also adds the closure-recurrence rule. Between the two commits, a failed read raises a fault that 122's close rule shuts on the next non-reading tick. The task file's own rule is "a commit never holds untested behavior". Move the failure-to-fault wiring into 9.3, or give 9.2 matching tests.

Task 9.2 is also large: tick wiring, tenant and factory plumbing, six or more scenario tests and the budget-coverage extension. Consider separating the budget-coverage extension into its own task.

### [CONCERN] Verification walkthrough step 4 (rename and renumber with the real `cf`) is dropped

Task 11.3 runs only LLD walkthrough step 3. Step 4 copies the repository, edits a slice name, then renumbers `(131)` to `(132)`, and checks node identity and the single `lifecycle_orphan` against real `cf` output. That is the only check of the identity-across-plan-edits risk against real CF behavior. Automated tests use the stub. Add step 4 to Task 11.3, or write a note in the task explaining why it is omitted.

### [CONCERN] Task 4.1 is labeled `refactor:` but changes behavior, and it moves the CF command constants out of `plan_read.py`

The task makes the initiatives probe stricter (full model, `-a`). That is a behavior change, yet its commit is `refactor: probe initiatives with the plan model`. The project's commit types reserve `refactor` for behavior-preserving work. Use `feat:`, or split the pure extraction of `run_cf` and `commands.py` from the stricter probe.

The task also puts the command constants in `lifecycle/commands.py`. The LLD (D11) says they are defined once in `plan_read.py`. That is a sensible departure, since it avoids a `probes.py` → `plan_read.py` import. Record it as a task-level addition next to "Module split". `run_cf` and `cf_call.py` are not in the LLD at all. They are justified by DRY, but they are the only item in the plan that is not traceable to a success criterion.

### [NOTE] Task 5.3's "eligible slice" bullet is garbled

"Eligible slice: linked, has step children, CF status not `deferred` or `deprecated` is expressed by 'has step children'" reads as two conflicting rules. The intent matches D4 and D6: eligibility is exactly "linked and has step children". Reword it so a junior does not add a status check to `predecessors`.

### [NOTE] `reconcile`'s `faults` parameter is undefined

The section header gives `reconcile(store, project_id, cf_project_id, read, faults) -> bool`. It never says what `faults` is. It could be a sink for the `checked_scope` faults, a callback, or something else. Task 9.2 never says how those faults reach the tick's fault boundary. Name the type once in Task 8.1 or 8.3.

### [PASS] Success-criterion coverage is complete

Every functional and technical criterion maps to a task. Apart from the gaps above, the mapping is:
- linking, new slice, rename, renumber and move, completed slice leaving the plan, no-plan state: 8.2–8.5, 9.2;
- no orphaning on a bad read: 8.1, 8.2, 9.3;
- cut-off reads and `TickBudget` coverage: 6.3, 9.2;
- early reads: 6.4, 9.2;
- human steps: 10.1;
- ready steps and the predecessor table: 5.3, 5.4;
- crash during reconcile: 8.5, 9.3;
- migration, parser fixtures, `create_node` guard: 2.1, 3.1–3.2, 8.3;
- contract documents and CHANGELOG: 11.1, 11.2.

I found no scope creep beyond the `run_cf` extraction noted above. No NFR with a target is restated, so no load test or CI-gating task is required.

### [PASS] Sequencing, test-with pattern and commit cadence

The dependency chain is acyclic. The circular-import direction between `tree.py` and `predecessors.py` is specified in Task 5.3. Every implementation task includes its own tests, and there is one commit per task from Section 2 onward, so no commits are batched at the end. The referenced existing files, including `tests/cf_stub.py`, `tests/runner/tick_support.py`, `tests/test_writer_guard.py` and `probes.py`'s `OUTPUT_HEAD_CHARS`, exist. `projectState` also matches the code: `probes.py` no longer has a slices probe.

### Run Digest

- Response length: 7797 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 227891 / 112115 / 115770 / 9900 / not computed
- Duration: 76.8 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
