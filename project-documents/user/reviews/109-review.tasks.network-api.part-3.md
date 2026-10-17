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
reviewedSha: 364974b3c106633ee43ac06490d82dd99fe17a4d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 183269
cachedTokens: 93187
cacheWriteTokens: 90076
completionTokens: 4594
durationSeconds: 38.4
costUsd: 0.416241
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Tasks 7.3 and 7.4 reference each other"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:69-99"
  - id: F002
    severity: concern
    category: task-structure
    summary: "Four tasks are committed together, and three of them have no test"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:41-125"
  - id: F003
    severity: concern
    category: testing
    summary: "Task 7.6's pinning test for disconnect timing is prone to flakiness"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:139-141"
  - id: F004
    severity: note
    category: ci-wiring
    summary: "The CI gate for the load tier depends on a step in `ci.yml` that this task only checks"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:233"
  - id: F005
    severity: note
    category: clarity
    summary: "The load test does not say how the 600-change burst is produced"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:226"
  - id: F006
    severity: note
    category: scope
    summary: "The smoke test adds mutual-survival checks that the slice partly assigns elsewhere"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:206-207"
  - id: F007
    severity: note
    category: dependencies
    summary: "Task 8.1 depends on an unresolved PM decision"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:161"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for stream, CLI, load and docs"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:103-277"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Tasks 7.3 and 7.4 reference each other

Task 7.3 depends on 7.2 and its last step says the route "returns the Task 7.2 response wired to the Task 7.4 thread". Task 7.4 depends on 7.3. So 7.3 cannot be completed or type-checked ("`pyright` clean") until 7.4 exists. A junior AI would have to invent a stub or work out of order. Fix by reordering so the follow thread (7.4) comes before the route (7.3), or by moving the wiring step into 7.4. 7.4 would then own "register the route with the thread started", and 7.3 would stop at cursor, slots and preflight.

### [CONCERN] Four tasks are committed together, and three of them have no test

Tasks 7.2, 7.3 and 7.4 each say "Committed with Task 7.5". The frame builder is described as a pure function, but its test is deferred to 7.5, behind two other tasks. That breaks the test-with pattern. The usual remedy is to put the frame-builder test directly after 7.2, and to run cursor parsing and the 400/503 paths through `TestClient` right after 7.3. Alternatively, merge 7.2–7.4 into one implementation task of about effort 5 and say so. The same section already has Tasks 7.1 and 7.6 committing on their own, so the single bundled commit is the outlier. As written, a failure in 7.5 could come from any of three untested units.

### [CONCERN] Task 7.6's pinning test for disconnect timing is prone to flakiness

"Pin behavior 2" asserts that a slot is still held after a clean client close and before the next heartbeat. This is a negative timing assertion, and it will fail if the library later notices disconnects faster. The slice does say "a test pins each" of the two library behaviors. But the success criterion only requires that the slot is freed within one heartbeat plus one follow interval, and the "free within that bound" test already covers it. The task should say what the assertion tolerates, for example "not freed before X seconds, with a margin". Otherwise it should drop the upper-bound claim. The "three consecutive runs" check helps, but the assertion should be made tolerant.

### [NOTE] The CI gate for the load tier depends on a step in `ci.yml` that this task only checks

The slice's load tier needs a CI gate. Task 9.2 handles it by confirming that the existing `Load tests` step runs `uv run pytest tests/load` and so picks up the new file. That satisfies the requirement without adding a task. Two things to be aware of:
- It is stated as a success criterion with no step.
- It assumes CI installs `starlette`, `uvicorn` and `httpx`, which Task 4.1 in file 2 should cover.

If the step is missing or scoped differently, the task should say to stop and ask the PM rather than add a workflow change silently.

### [NOTE] The load test does not say how the 600-change burst is produced

"Commit a burst of 600 changes" doesn't name the writer path. The test must not touch the production database and must stay inside the writer guard, so a junior AI needs a pointer to the store fixture used by the 106 load tests. Note also that the latency bullet needs per-change commit timestamps recorded at the writer, which the task doesn't state.

### [NOTE] The smoke test adds mutual-survival checks that the slice partly assigns elsewhere

The slice's Integration Requirement says the restart matrix belongs to slice 110 and that walkthrough step 5 checks survival by hand. Task 9.1 adds "stop the resident process with the follower open" and "`kill -9` the server" to the smoke test. These do trace to the Functional Requirement "`kill -9` of the server leaves the resident process running … stopping the resident process leaves the server serving", so they are not scope creep. They do make the smoke test heavier than the Integration Requirement describes. This is acceptable if no earlier task already covers that criterion. If one does, trim these two steps.

### [NOTE] Task 8.1 depends on an unresolved PM decision

The first step of Task 8.1 stops until the PM answers file 1's open item on where `ServeRefusedError` is mapped. This is handled correctly: it is flagged, it has a recommendation, and it is gated. The risk is that the answer arrives only after Sections 1–7 are done. Ask the PM before implementation starts, not at Task 8.1. The task also mentions "per the PM's answer" without a fallback if the answer differs from the recommendation.

### [PASS] Success-criteria coverage for stream, CLI, load and docs

These criteria map to tasks:
- Delivery, resume and cursor precedence: 7.5.
- Keepalive: 7.5.
- Slot limit, abrupt-close and stalled-reader release, and the two library behaviors: 7.6.
- Exit-13 matrix, HTTPS, token not in output, bind failure, SIGTERM grace, and lazy uvicorn import: 8.2.
- End-to-end smoke: 9.1.
- Load tier with the 600-change burst, p95 ≤ 1 s and no starvation: 9.2.
- Network contract, four deltas and `CHANGELOG.md`: 9.3.
- Walkthrough and final validation: 9.4.

Commits are spread across Sections 7–9, apart from the 7.2–7.5 bundle noted above. The cross-references to Tasks 4.1, 4.4, 5.6 and 6.2 exist in file 2.

### Run Digest

- Response length: 6070 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 183269 / 93187 / 90076 / 4594 / not computed
- Duration: 38.4 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
