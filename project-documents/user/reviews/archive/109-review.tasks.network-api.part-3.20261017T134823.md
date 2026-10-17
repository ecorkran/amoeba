---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-3.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: ea7825b57979f2aad8bd2b6679a9d958035e1260
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 185092
cachedTokens: 92657
cacheWriteTokens: 92429
completionTokens: 4465
durationSeconds: 37.3
costUsd: 0.42431
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Smoke test seeds a node while the resident process is running"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:187"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "CI gating of the new load test is left implicit"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:199-216"
  - id: F003
    severity: concern
    category: coverage-gap
    summary: "Smoke test omits the \"streams stay open while the resident process is down\" criterion"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:188"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 7.3 mixes several concerns and adds an unlisted error path"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:65-82"
  - id: F005
    severity: note
    category: design-consistency
    summary: "`ServeRefusedError` is handled in `cli/serve.py` instead of `cli/main.py`"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:144"
  - id: F006
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md"
  - id: F007
    severity: pass
    category: traceability
    summary: "Success-criteria coverage for sections 7–9"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:20-256"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Smoke test seeds a node while the resident process is running

Task 9.1 starts `amoeba start`, POSTs `create_project`, waits for `applied`, and then "seed[s] one node as the walkthrough does". The slice walkthrough (`109-slice.network-api.md:378`) says the seeding script requires the process to be stopped, so it runs before `start`. In the order Task 9.1 gives, the seeding either fails or races the resident writer. The sole-writer model is the design's central invariant. The step has to say how the node gets seeded. One option is to stop the resident process, seed, and restart it, which costs an extra restart. Another is to create the project locally before starting, which gives up the "create a project over HTTP" criterion (`109-slice.network-api.md:369`). The PM should choose one.

### [CONCERN] CI gating of the new load test is left implicit

The slice restates NFRs (32 followers, p95 ≤ 1 s, no starvation), and Task 9.2 adds `tests/load/test_serve_load.py`. No task checks or wires CI. `.github/workflows/ci.yml:54` already runs `uv run pytest tests/load`, which collects the new file by path, so no new wiring is needed. Task 9.2 should still say that, and add a success criterion that the CI step picks the file up and that 32 concurrent streams plus 600 changes fits the runner's timeout. Without it, the gate is only an accident of directory layout.

### [CONCERN] Smoke test omits the "streams stay open while the resident process is down" criterion

The slice's last Functional Requirement (`109-slice.network-api.md:353`) says that stopping the resident process leaves the server "serving reads, accepting submissions, and holding streams open". Task 9.1 checks only that a restarted server still serves a read after the resident process stops. Nothing in sections 7–9 shows an open stream surviving the resident stop. Task 9.1 should hold the feed open across the resident stop, or the walkthrough should be named as the sole check (step 4 does exercise it by hand). If the intent is for the walkthrough to cover it, say so explicitly.

### [CONCERN] Task 7.3 mixes several concerns and adds an unlisted error path

Task 7.3 covers cursor parsing, slot limiting, a worker-thread preflight, the follow thread with three exception mappings, and route registration. It also has no test of its own, because tests arrive in 7.4 and 7.5. That is acceptable for an effort-3 task, but a junior AI will find it dense. The task also adds `unexpected_parameter` for the feed route. The slice's API table for the feed (`109-slice.network-api.md:301`) does not list that code, and 7.4 has no test for it. Either add it to the contract table and 7.4, or drop it. Separately, 7.2 and 7.3 produce no tests and no commit until 7.4, which weakens the test-with and commit-checkpoint pattern. This is tolerable given that the design needs a real server for these tests.

### [NOTE] `ServeRefusedError` is handled in `cli/serve.py` instead of `cli/main.py`

The slice (`109-slice.network-api.md:260`) says `ServeRefusedError` is "mapped to the exit code in `cli/main.py`, the same way lifecycle errors are". Task 8.1 instead catches it in `run_serve` and returns the code. Task 8.1 also gives `run(settings, token, store_dir)`, where the slice shows `run(settings, token)`. Both changes are reasonable, but the slice should be updated or the divergence flagged, since 9.4 already allows LLD corrections.

### [NOTE] Proportionality is acceptable

The three-file split and the 14 tasks in sections 7–9 are heavy but match the slice, which includes a migration, a new network surface, TLS and a load tier. Task 7.5's two "pin behavior" tests are justified because the design depends on those library behaviors. 8.2's `sys.modules` check partly duplicates 5.6's AST layering test, but one is runtime and one is static, so I'd keep both.

### [PASS] Success-criteria coverage for sections 7–9

Each of these maps to a task:
- Delivery, resume and cursor precedence: 7.4.
- Slot limit with reads still working, and the two slot-release paths: 7.5.
- Shutdown grace: 7.5 and 8.2.
- The exit-code matrix, HTTPS and the 401: 8.2.
- Smoke and `kill -9`: 9.1.
- All three load assertions: 9.2.
- Contract docs, deltas and `CHANGELOG`: 9.3.
- Walkthrough and final validation: 9.4.

No task lacks a success criterion behind it. Dependencies form a linear chain with no cycles, and commit checkpoints sit at 7.1, 7.4, 7.5, 8.2, 9.1, 9.2, 9.3 and 9.4 rather than at the end.

### Run Digest

- Response length: 5505 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 185092 / 92657 / 92429 / 4465 / not computed
- Duration: 37.3 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
