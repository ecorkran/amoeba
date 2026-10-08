---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 471687558981a404e164767dfe4136f6e517c8bd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 61.7
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered across both task files"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Test-with pattern and commit cadence are sound"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:26"
  - id: F003
    severity: concern
    category: hallucination-trap
    summary: "Task 1.3 puts a concrete npm package name next to a \"confirm it\" instruction"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:89"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 3.6 is overloaded, and its writer-guard test passes vacuously until Task 6.3"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:267-284"
  - id: F005
    severity: concern
    category: testability
    summary: "Task 5.1 evaluates `cf_data_dir` at import time but plans tests that need the environment variable to vary"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:379-381"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 4.3 is dense and may deserve a higher effort estimate"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:350-366"
  - id: F007
    severity: note
    category: sequencing
    summary: "Dependency declarations are slightly off but harmless"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:165-167"
  - id: F008
    severity: note
    category: design-conformance
    summary: "Deliberate deviation from the design on the version-label capture is flagged properly"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:30"
  - id: F009
    severity: note
    category: nfr
    summary: "No non-functional requirement calls for a load test"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:275"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered across both task files

Every Functional, Technical and Integration requirement in the design maps to a task. Task 8.7 adds an explicit traceability pass.
- **First snapshot, `cf set phase`, `updatedAt`/`customData`-only writes, unlinked change:** Tasks 6.3 and 2.3.
- **Disappearance and return, `missing`, catch-up, restart:** Tasks 6.4, 7.4 and 8.1.
- **`unreachable` and `unrecognized`, re-read only when the signature changes:** Task 6.2.
- **Deactivate and reactivate:** Tasks 4.2 and 6.4.
- **Bounded failure and retry:** Tasks 6.5 and 6.6.
- **Idle tick cost:** Tasks 4.3 and 6.1.
- **Migration upgrade, trigger, and feed invariant:** Tasks 3.2, 3.3 and 3.7.
- **Settings and flags:** Task 5.1.
- **Contract docs:** Tasks 8.2 and 8.3.
- **Import and single-definition boundaries:** Task 8.4.
- **Real fixtures:** Tasks 1.2 and 1.3.

### [PASS] Test-with pattern and commit cadence are sound

Implementation and test tasks are paired and committed together: 3.2 with 3.3, 3.5 with 3.6, and 4.1 with 4.2. Every other task carries its own tests and its own commit. Commits fall at the end of each section rather than at the end of the slice, and there are no circular dependencies.

### [CONCERN] Task 1.3 puts a concrete npm package name next to a "confirm it" instruction

Step 3 hardcodes `npm install -g @context-forge/cli` and, in the same step, tells the junior to confirm the name against `npm ls -g`. Under the project's hallucination-trap rule, the junior may keep the example if the lookup returns nothing.
- **Fix:** have the junior read the installed package name from `npm ls -g --depth=0` and stop and ask the PM if none is found. Remove the literal name, or mark it as unverified.
- **Scope:** the CI workflow change is not in the slice design's Technical Scope. It is justified because the real-`cf` tests must fail rather than skip, but the PM should know it was added. Task 8.6 does not list it.

### [CONCERN] Task 3.6 is overloaded, and its writer-guard test passes vacuously until Task 6.3

Task 3.6 bundles four things:
- two new store operations;
- the combined record-and-set-state method with its atomicity test;
- the public-API export check;
- a new AST writer-guard test.

The AST test checks calls into `process/cf_watch.py`, a file that does not exist until Task 6.1. It therefore passes with nothing to check, and Task 6.3 later tightens it to equality. A test that cannot fail gives false confidence in the meantime.
- **Fix:** move the AST guard test to Task 6.3, where the permitted caller first exists. Alternatively, have it assert that the set of calling modules is empty until then. That leaves Task 3.6 at a manageable size.

### [CONCERN] Task 5.1 evaluates `cf_data_dir` at import time but plans tests that need the environment variable to vary

The default is computed once at module import, following `DEFAULT_SQ_RUNS_DIR`, using the real environment. The test list includes "`--cf-data-dir` beats `CONTEXT_FORGE_DATA_DIR`", and Task 8.1 relies on the env var reaching a subprocess. A junior running the first test in-process cannot change the import-time default without reloading the module or monkeypatching.
- **Fix:** say how it should be tested, either in a subprocess or by asserting only that the flag overrides the default. Otherwise it invites a hack.
- **Related:** this task also adds `--cf-max-attempts`, which the design does not list. It is flagged to the PM in Task 8.6, so it is acceptable.

### [NOTE] Task 4.3 is dense and may deserve a higher effort estimate

The task's own text marks it as a mechanism the LLD does not spell out. It covers commit-timing semantics (pending flag, bump after the `with` block, clear on exception) and a test matrix of eight cases. Effort 3 looks light, but it is a single coherent unit and should not be split. Its first step, confirming the shared `Store` handle, is a good guard.

### [NOTE] Dependency declarations are slightly off but harmless

Task 3.1 declares a dependency on Task 2.3, but store models do not need the upstream diff. The design says the upstream work can start before 106 lands, so the dependency adds nothing.

In file 2, Task 7.3 wires `CFWatchTenant` but declares only Task 7.2. It should also declare Task 6.6. Section order makes this work in practice, but the dependency graph should be explicit.

### [NOTE] Deliberate deviation from the design on the version-label capture is flagged properly

The design says "one `cf --version` per detected change", but its Technical Requirements say "no tick starts a subprocess". Task 6.3 resolves this by capturing the label once per read that records a snapshot, and never on idle or no-op reads. Task 8.6 reports the choice to the PM. This is a reasonable reading; the PM should confirm it.

### [NOTE] No non-functional requirement calls for a load test

The slice states only a structural idle-tick guarantee (one `stat`, no read, no query). It sets no throughput or latency target, so no `tests/load/` task or CI gate is required. Tasks 6.1 and 6.6 cover the guarantee with spy-based unit tests.

### Run Digest

- Response length: 6376 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 61.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
