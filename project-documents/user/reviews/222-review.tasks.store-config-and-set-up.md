---
docType: review
layer: project
reviewType: tasks
slice: store-config-and-set-up
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/222-tasks.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: cce504e598427f75299fe9eb94492a85ff007f38
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 113573
cachedTokens: 11198
cacheWriteTokens: 102371
completionTokens: 4221
durationSeconds: 34.8
costUsd: 0.453667
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: task-clarity
    summary: "Task 8.6 does not say how `working_directory` is computed"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:215-218"
  - id: F002
    severity: note
    category: test-coverage
    summary: "Wheel-contents criterion is checked once by hand"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:254-256"
  - id: F003
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing and sizing"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md"
  - id: F005
    severity: pass
    category: proportionality
    summary: "Proportionality"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md"
---

# Review: tasks — slice 222

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 8.6 does not say how `working_directory` is computed

Task 8.6 returns `working_directory` as `{member, program}`, `{not_in_program}` or `{not_a_project}`. It doesn't say where that comes from.
- Task 8.2 already resolves the working directory through `project_of`, before the write.
- Task 7.1's `resolve_member(store, directory, run)` makes its own `cf` call and does its own store lookup.
- A junior could call `resolve_member` inside the `Store.write()` block. That runs a subprocess under the write lock, which the design's Data Flow step 3 forbids.
- A junior could instead re-implement the id-to-member lookup. That duplicates 7.1 and breaks the DRY rule.

Add one line saying to reuse the CF id resolved in 8.2. Either split a lookup helper (CF id to `Member | NotInProgram`) out of `resolve_member` in 7.1, or state that 8.6 calls it with the already-resolved id. Task 8.7 covers the outcome, but nothing pins how it is built.

### [NOTE] Wheel-contents criterion is checked once by hand

The slice criterion "The wheel contains `001_baseline.sql`" is checked only by the one-off `uv build` and listing in 10.2. No test or later step repeats it. This is acceptable for the slice's scope. Adding a test would be extra weight, so I'm not asking for one.

### [PASS] Success criteria coverage

Each criterion maps to at least one task:
- **`applied`/`unchanged`/read-back:** 8.7.
- **D7 checks and `malformed`:** 8.3 and 8.5.
- **Exit 2 and exit 3:** 10.3.
- **Two-worktree resolution and `not_in_program`/`not_a_project`:** 7.2 and 8.7.
- **`answering_for`:** 9.2.
- **Missing config file or key:** 4.3 and 10.3.
- **Concurrency, busy timeout, stamped-higher store:** 8.8, 3.5 and 10.3.
- **D10, pinning, D11 and import-boundary tests:** 2.2, 2.3, 3.6, 5.2 and 10.4.
- **Contract docs:** 11.2.
- **Walkthrough and the four checks:** 11.3.

No task falls outside a criterion. The extra tests (AST home check, vocabulary pinning, contract match) each trace to a stated design requirement.

### [PASS] Sequencing and sizing

Dependencies run in order with no cycles:
- Fixtures (1.x) come before `project_of` (5.x), member resolution (7.x) and `set_up` (8.x).
- Config (4.x) comes before the `unknown_authorize_item` check and `answering_for`.
- Store (3.x) comes before programs (6.x).
- The config contract doc (4.2) comes before the test that extracts its example (4.3).

Implementation tasks are each followed by their tests (2.1–2.3, 3.5–3.6, 4.1–4.3, 5.1–5.2, 6.x, 8.4–8.5, 8.6–8.7). The `**Commit**:` markers sit at working, tested points and are neither per-task nor only at the end. Group 8 has eight subtasks, but they split cleanly along the design's phases. Each one is small enough for a junior to complete.

### [PASS] Proportionality

It is one task file with a task count that fits an effort-3 slice. Steps name behavior and constraints taken from the design, not code structure. The slice restates no NFR, so no load test or CI wiring task is needed.

### Run Digest

- Response length: 3802 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 113573 / 11198 / 102371 / 4221 / not computed
- Duration: 34.8 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Resolution

- [concern] Task 8.6 `working_directory`: applied. 8.6 now says it is built from the 8.2 working-directory lookup (no new `cf` call): `not_a_project` from CF's message, otherwise `get_member` on the CF id in the same transaction gives `{member, program}` or `{not_in_program}`.
- [note] Wheel-contents criterion: applied. Task 10.2 now has `tests/test_wheel_contents.py`, which builds the wheel and asserts `001_baseline.sql` is in it, replacing the one-time manual listing.
- [pass] Success criteria coverage: no change needed.
- [pass] Sequencing and sizing: no change needed.
- [pass] Proportionality: no change needed.
