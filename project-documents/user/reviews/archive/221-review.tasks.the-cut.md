---
docType: review
layer: project
reviewType: tasks
slice: the-cut
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/221-tasks.the-cut.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: cec2b1f370a2bfd09d39416e8a5e1fb603bbf1ba
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107172
cachedTokens: 11198
cacheWriteTokens: 95970
completionTokens: 3906
durationSeconds: 32.2
costUsd: 0.424909
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Live tests are updated after the \"checks pass\" gate that covers them"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:196-216"
  - id: F002
    severity: note
    category: task-sizing
    summary: "Section 2 is one 20-task block with a single commit marker"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:95-201"
  - id: F003
    severity: note
    category: task-sizing
    summary: "Several small tasks could merge"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:123-139"
  - id: F004
    severity: note
    category: clarity
    summary: "Wheel-contents test destination is vague"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:193"
  - id: F005
    severity: pass
    category: coverage
    summary: "Success criteria coverage and scope"
    location: "project-documents/user/tasks/221-tasks.the-cut.md"
---

# Review: tasks — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Live tests are updated after the "checks pass" gate that covers them

Task 2.20 requires `ruff`, `pyright` and `pytest` to pass, and task 2.17 requires that no test mentions nodes, journal entries or a tick. The `tests/live/answering` imports are only updated or deleted later, in 3.2 and 3.3. `addopts` ignores `tests/live` for pytest only. Ruff and pyright normally still scan those files, and they still import deleted or moved modules (`stage_harness.py` and `test_answering_run.py` are expected to). Unless pyright is configured to exclude `tests/live`, which I could not confirm, 2.20 cannot pass as written. The Section 2 commit would then hold a broken tree. The slice's Success Criteria also treat the four checks as passing on the whole repo.
Fix: move 3.2 and 3.3 (update the `stays` files, delete the `waits on 223` files) into Section 2 before 2.20. Keep 3.4, running the live tier, in Section 3. Alternatively, state in 2.20 that `tests/live` is excluded from pyright and ruff until Section 3.

### [NOTE] Section 2 is one 20-task block with a single commit marker

Tasks 2.1 to 2.19 leave the tree uncompilable on purpose, because the checks run only at 2.20. This follows the design's Migration Plan step 2, so it is not a defect. The cost is that the whole diff lands in one commit and any failure in 2.20 is hard to locate. A fully green earlier point is hard to find, so I am not asking for new markers. If the implementer can cheaply run pyright on `src/amoeba/answering` and `src/amoeba/upstream` after 2.12, a one-line note to do so would help catch severing mistakes early.

### [NOTE] Several small tasks could merge

Tasks 2.5, 2.6 and 2.7 are three similar `git mv` and test-move tasks into `upstream/`. They could be one "move the upstream readers" task. Tasks 2.11 and 2.12 are both verification greps. This is optional, because each task is clear and independently checkable.

### [NOTE] Wheel-contents test destination is vague

Task 2.19 says to "move `test_wheel_contents.py` beside the library" without naming a path. The design says only "moves with the library". Every other moved test names `tests/answering/` or `tests/upstream/`, so name `tests/answering/` here as well.

### [PASS] Success criteria coverage and scope

Each design success criterion maps to a task:
- **Deletions of `delete` and `squadron` paths:** 1.1–1.5 and 2.13–2.16.
- **Moves to the D3 locations:** 2.2–2.7.
- **Checks pass:** 1.6, 2.20 and 4.2.
- **Library tests pass without store or tick:** 2.20.
- **`src/amoeba` contains only the expected packages:** 2.16.
- **Live tier:** 3.2–3.4.
- **Boundaries test (D6):** 2.17.
- **`uv build` wheel:** 3.1, with packaging in 2.19.
- **Audit row changes (D1):** 2.1 and 4.2.
- **README (D9):** 4.1.
- **`amoeba#32`:** correctly left to Phase 7.

No task falls outside the design. The baseline in 0.3 is a small, justified addition. Tests move with their code, `**Commit**:` markers sit at the end of each phase, and no merge or push task is written. A single task file suits the slice.

### Run Digest

- Response length: 3631 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107172 / 11198 / 95970 / 3906 / not computed
- Duration: 32.2 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
