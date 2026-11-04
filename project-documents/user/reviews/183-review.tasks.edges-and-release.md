---
docType: review
layer: project
reviewType: tasks
slice: edges-and-release
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/183-tasks.edges-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 29938fb5350a42b728e5231a407eae9076b7e5ca
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 744142
cachedTokens: 570140
cacheWriteTokens: 173990
completionTokens: 71471
durationSeconds: 482.7
costUsd: 0.210506
costBasis: provider
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: state-machine
    summary: "Coordinator-resolved block: D9 closes open edges to released, but Task 1.5 forbids open→released"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:210"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`confirm_release` is referenced but no task creates it"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:114"
  - id: F003
    severity: concern
    category: coverage
    summary: "The head wait for a providing slice with no `slice_heads` row is undefined"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:181"
  - id: F004
    severity: concern
    category: commit-cadence
    summary: "Feat source changes sit under `test:` commit messages"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:243"
  - id: F005
    severity: concern
    category: verification
    summary: "Walkthrough step 2's `-k` selector matches no named test"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:147"
  - id: F006
    severity: concern
    category: layering
    summary: "Task 5.4 puts checkout resolution and git reads inside `runner/lifecycle`"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:172"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 0.1 will block today"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:66"
  - id: F008
    severity: note
    category: coverage
    summary: "The baseline \"as after 181 and 182\" does not check 182"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:66"
  - id: F009
    severity: note
    category: test-design
    summary: "`slice_heads` locality is tested twice"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:128"
  - id: F010
    severity: note
    category: test-design
    summary: "The purity check is described as one list that does not exist"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:206"
  - id: F011
    severity: note
    category: verification
    summary: "The validation exception list omits the test edits in 8.1"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:274"
  - id: F012
    severity: note
    category: verification
    summary: "No numeric NFR is restated, and 9.1's coverage claim is unverified"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:273"
  - id: F013
    severity: note
    category: scope
    summary: "Task 3.2 adds a behavior the design does not state"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:127"
  - id: F014
    severity: pass
    category: coverage
    summary: "Success criteria and scope are covered"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:404"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing and placeholders"
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:222"
---

# Review: tasks — slice 183

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Coordinator-resolved block: D9 closes open edges to released, but Task 1.5 forbids open→released

Task 7.2 says each open or satisfied edge whose block is coordinator-resolved closes as `released`. Task 1.5 (line 94) allows only open→satisfied, open or satisfied→superseded, and satisfied→released, and raises on open→released. Design D9 (slice design lines 253–254) uses the same "open or satisfied" wording, while D1 (line 173) allows only satisfied→released. A release is submitted only when every edge of the node is satisfied, so an open edge on a coordinator-resolved block is a producer error, not a normal path. Fix: state in 7.2 that the coordinator case applies to satisfied edges, and that an open edge on such a block raises. Or make open→released legal in both 1.5 and D1. Either way, 7.2's test should name the state.

### [CONCERN] `confirm_release` is referenced but no task creates it

Task 2.2 says the write is `confirm_release(edge_id, at)` in `store/program_edges.py`. Tasks 1.4 and 1.5 list every other method on that module and omit this one. The slice design's component table (line 106) lists it. Fix: add `confirm_release` to 1.5, with a test that it writes only `release_confirmed_at`, and keep 2.2 as the caller.

### [CONCERN] The head wait for a providing slice with no `slice_heads` row is undefined

Task 6.1 defines `branch_head_missing` as "done with no recorded commit and `missing`". Task 6.4 covers only a row with commit null and missing false. A slice already `done` when its edge is created has no row at all. Design D5 (slice design line 213) says that edge waits `branch_head_missing`, and Task 7.9 (line 240) tests exactly that case. Under 6.1's wording the no-row case matches neither rule, so the implementer has to guess. Fix: define no row as `branch_head_missing` in 6.1, and say the `missing` flag is not required for it.

### [CONCERN] Feat source changes sit under `test:` commit messages

Task 7.6 (the `finish.py` payload change) and Task 8.1 (the `inspection/program.py` listing) have no marker after them. They fall into the marker at line 243 (`test: prove release, ...`) and the marker at line 255 (`test: extend the locality proof to edges`). Both commits then carry source changes under a `test:` message. Fix: add a marker after line 231 and after line 250, or change the messages to match the content. Also add a blank line before the marker at line 255, so it does not render as part of the bullet list above it.

### [CONCERN] Walkthrough step 2's `-k` selector matches no named test

Design walkthrough step 2 (slice design line 446) runs `-k "waiting or external"` over `tests/runner/lifecycle` and `tests/runner/intent`. Task 4.1 names files (`test_ready_slices.py`, `test_governing.py`) and describes cases only in prose. Unless the implementer happens to use those words, the selector collects nothing and step 2 shows no output. Task 2.2 handles the same problem for step 1 by requiring "edge" in the test name. Fix: require "waiting" or "external" in the test name for each case in 4.1.

### [CONCERN] Task 5.4 puts checkout resolution and git reads inside `runner/lifecycle`

Task 5.4 has `complete_observed_slices` in `runner/lifecycle/completion.py` call `resolve_checkout`, read the branch head, and call `store.complete_slice`. The slice design places this read in the plan stage (D6, line 220) and in `runner/program/heads.py` (component table, line 111). It also says lifecycle "receives a set of node ids" (line 119). Nothing enforces that lifecycle does no I/O. `tests/runner/purity.py` is a helper called per test file, and `tests/test_import_boundaries.py` has no lifecycle purity rule. Fix: have the plan-stage caller resolve the head and pass it into `complete_observed_slices`. Optionally, add an `io_use` check on the lifecycle modules in 4.1.

### [NOTE] Task 0.1 will block today

`src/amoeba/program/`, `src/amoeba/inspection/program.py` and `src/amoeba/runner/program/stage.py` do not exist, so 181 is not on the target. Task 0.1 will write BLOCKED as written. This matches the file's own `not_started` status, so it is not a plan defect. Phase 6 cannot start until 181 merges.

### [NOTE] The baseline "as after 181 and 182" does not check 182

FR13 (slice design line 418) requires identical ticks "as after 181 and 182". Task 0.2 pins literals on the code as it stands, and 0.1 does not check whether 182 has merged. The slice design (line 88) says 182 is independent and may merge either way. If 182 is not on the target when 0.2 runs, the literals describe pre-182 behavior. Fix: record 182's state in 0.1. If 182 lands later, re-run the baseline on the merged code.

### [NOTE] `slice_heads` locality is tested twice

Task 3.2 asserts that `slice_heads` never appears in the program store schema. Task 8.2 (line 252) adds the same check to the locality proof. Keep the 8.2 check, which is the one that gates the contract suite, and drop the 3.2 assertion.

### [NOTE] The purity check is described as one list that does not exist

Task 7.1 says to add the module to "the test that lists pure modules" in `tests/runner/purity.py`. That file only defines `io_use`. Each module's purity assertion lives in its own test file (for example `tests/runner/test_decide.py` and `tests/runner/test_supervise.py`). Fix: say "add `assert io_use(release) == []` to `tests/runner/program/test_release.py`".

### [NOTE] The validation exception list omits the test edits in 8.1

Task 9.1 allows existing tests to change only for the updates named in Tasks 1.3, 3.1, 3.2, 4.1 and 7.2. Task 8.1 (line 250) also updates "tests that enumerate blocked-on kinds" from 181. Add 8.1 to the list so that 9.1's rule matches what the tasks do.

### [NOTE] No numeric NFR is restated, and 9.1's coverage claim is unverified

The slice design restates no numeric NFR, so no new load test is required. Its "Cost per tick" paragraph (slice design line 509) describes call counts, which Tasks 6.3 and 7.9 already test. `.github/workflows/ci.yml:54` runs `tests/load` as its own step, so the existing load tier is gated. Task 9.1 says the three load tests it names "cover the changed paths", but none of them exercises an edge, and the task file does not check that claim. Fix: reword 9.1 to call them regression checks, or add a small load test for ticks with open edges if the PM wants per-tick cost covered.

### [NOTE] Task 3.2 adds a behavior the design does not state

"A node already `done` still gets its row only if it has none" is not in the slice design. It follows from 125's re-entry idempotency, so it is probably right. The design should say so, or the rule should be dropped.

### [PASS] Success criteria and scope are covered

Every functional and technical requirement (slice design lines 406–424) has a task with a test. Readiness and the no-write resume are covered by 4.1 and 7.5. The head in the `done` transaction on both paths is covered by 3.2, 5.3 and 5.4. From-source and from-release satisfaction are covered by 6.2 and 6.3, and the head retry by 6.4. Release and its three crash points are covered by 7.4 and 7.7–7.9, and supersession by 7.2 and 7.8. `member_referenced` is covered by 1.6, `program-blocked` by 8.1, write-only-on-change by 1.5 and 7.3, call counts and budget refusals by 6.3, and the locality and vocabulary pins by 1.3 and 8.2. No task traces to nothing. The contract docs (8.3–8.5), the CHANGELOG (9.3) and the walkthrough (9.2) are present. The code references I checked match the repo.

### [PASS] Sequencing and placeholders

Dependencies run forward with no cycles: store, then inbox, then head, then readiness, then reads, then observation, then the stage, then listings and docs. Each implementation sub-item has its test in the same task. The empty-set placeholders in 4.1, 5.3 and 5.4 are all replaced in 7.5, which names them.

### Run Digest

- Response length: 11041 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 744142 / 570140 / 173990 / 71471 / not computed
- Duration: 482.7 s
- Cost: $0.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
