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
sourceDocument: project-documents/user/tasks/109-tasks.network-api-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: ea7825b57979f2aad8bd2b6679a9d958035e1260
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 369489
cachedTokens: 274180
cacheWriteTokens: 95299
completionTokens: 7045
durationSeconds: 63.1
costUsd: 0.479751
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Auth middleware is committed untested, against the file 1 cadence rule"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:169-190, 235-251"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Traversal tests for POST submissions do not prove nothing was written"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:316"
  - id: F003
    severity: concern
    category: correctness
    summary: "Pure-ASGI guard does not say what to do with non-HTTP scopes"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:176-181"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Fixture signature in Task 5.1 is not valid pytest"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:158-159"
  - id: F005
    severity: note
    category: test-coverage
    summary: "The token-secrecy test cannot cover uvicorn's access log"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:244"
  - id: F006
    severity: note
    category: proportionality
    summary: "Task steps introduce small choices that the slice does not state"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:176-181, 105-125"
  - id: F007
    severity: note
    category: commits
    summary: "Commit pairing is consistent with the stated cadence apart from Section 5"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:78, 123, 163, 295"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 4–6"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md"
  - id: F009
    severity: pass
    category: ci
    summary: "Load-test CI gating is already in place"
    location: ".github/workflows/ci.yml:54"
  - id: F010
    severity: pass
    category: scope
    summary: "Sizing and proportionality"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Auth middleware is committed untested, against the file 1 cadence rule

- Task 5.2 creates `RequestGuardMiddleware` and is "Committed with Task 5.3".
- Task 5.3 is "Committed with Task 5.4", so the Section 5 commit holds 5.1–5.4.
- Nothing in 5.1–5.4 exercises the Origin, Host, token or content-type logic. Task 5.4 tests reads only, and the guard tests are in Task 5.5, which comes after that commit.
- File 1 (`109-tasks.network-api-1.md:39`) says "a commit never holds untested behavior". The `feat(serve): add reads endpoint and request guards` commit therefore breaks that rule.
- This also breaks the test-with pattern: the guard tests are two tasks after the code.
- Fix: move Task 5.5 to run before the Task 5.4 commit, as 5.3a, and fold the 5.4 commit after it. Alternatively, split the commits so 5.2 commits with 5.5. Task 5.5 only needs the `client` fixture, so it can sit directly after 5.3.

### [CONCERN] Traversal tests for POST submissions do not prove nothing was written

- The slice criterion is "no file outside the supervisor directory is opened". The reads test (Task 5.4) enforces this by asserting that `Store.open_read_only` is never called.
- For submissions, Task 6.2 says only "Traversal ids on both endpoints → 400".
- The write path is the riskier one. `submit()` creates inbox files, so a bad id that slips past validation would create files outside the store directory.
- Add a step that asserts the scratch store directory and its parent are unchanged (no new files) after each traversal POST, or that `submit` was not called.

### [CONCERN] Pure-ASGI guard does not say what to do with non-HTTP scopes

- Task 5.2 requires a pure ASGI middleware. uvicorn also sends `lifespan` scopes through the middleware stack, and any `websocket` scope would arrive the same way.
- The steps read headers and method on every call and never say to pass non-`http` scopes through untouched.
- A junior implementer following the steps literally will crash on startup under uvicorn. The `TestClient` hides this in Section 5, and it would only surface in the real-server tests in Section 7 or 8.
- Add one step: "for `scope["type"] != "http"`, call the inner app unchanged". Add a test that sends a lifespan scope through the middleware.

### [CONCERN] Fixture signature in Task 5.1 is not valid pytest

- `client(token=None)` is described as a fixture, but a pytest fixture cannot take caller arguments.
- It needs to be a factory fixture that returns a callable, or a parametrized fixture. A junior will have to guess.
- The fixtures are also committed unused, and the lazy `build_app` import exists only to allow that. The task is therefore not independently verifiable.
- Either state the factory form explicitly or fold the harness into Task 5.3 or 5.4, where it is first used.

### [NOTE] The token-secrecy test cannot cover uvicorn's access log

- Design D2 justifies secrecy partly by "uvicorn's access log records the method, path, and status, not headers".
- Task 5.5 captures logs under `TestClient`, which does not run uvicorn, so that claim is not exercised here.
- Task 5.5 is still adequate for application logging. Check that the real-server tests in file 3 (smoke or stream) capture uvicorn's log once. If they do not, add that there.

### [NOTE] Task steps introduce small choices that the slice does not state

- The guard order of Origin, Host, token, then content type is not specified by the design. The task fixes it and tests it ("Order" bullet in Task 5.5). This is harmless but is invented behavior.
- `StoreCorruptError` appears in `CODE_BY_EXCEPTION` but is not among the 101 errors the design's Prerequisites list. Confirm in code that the exception exists, since file 1 may already have verified it.
- `build_app(settings, token, store_dir)` differs from the design's `build_app(settings, token)`. It is consistent with "resolve the store directory once", but record it as a design delta.

### [NOTE] Commit pairing is consistent with the stated cadence apart from Section 5

- The other pairings (4.3 with 4.4, 4.5 with 4.6, 6.1 with 6.2) follow "committed with the later test task", and each commit holds code plus its tests.
- Commits are spread through the sections rather than batched at the end.
- Section 5 is the only exception, covered in the first finding.

### [PASS] Success-criteria coverage for Sections 4–6

- **Bind table and TLS:** D3's table, `token_too_short` and `tls_unusable` map to 4.3 and 4.4. The CLI exit-13 criterion is deferred to Section 8.
- **Parity and refusals:** parity over every listing with each option, `as_of_seq`, and the 400/404/422/503 refusals map to 5.3 and 5.4.
- **Traversal and snapshot:** the traversal reads are in 5.4. The snapshot test is covered by the file 1 store amendment.
- **Guards and secrecy:** `Origin`, `Host` and 415, and the token-secrecy requirement, map to 5.5 and 6.2.
- **Submissions:** 202, idempotent retry, `invalid_submission` with the same `reason` as the CLI, 413 with and without `Content-Length` and the `+1` read bound, 503 retry applying once, and outcome 404→200 are all in 6.2.
- **Layering and single definition:** the layering and single-definition tests are in 4.6 and 5.6.
- **Not in scope here:** stream, slot-limit, cursor and kill-9 criteria belong to file 3.

### [PASS] Load-test CI gating is already in place

- Task 7.x in file 3 adds `tests/load/test_serve_load.py`.
- The existing CI workflow has a separate `uv run pytest tests/load` step, so the new file is gated without a wiring task.
- No CI task is needed in this breakdown.

### [PASS] Sizing and proportionality

- Tasks 5.3 and 6.1 are each Effort 3 with many sub-steps, but each is a coherent single module pair and does not need splitting.
- No task traces to no criterion. Test tasks match the criteria, and no extra test tasks appear.
- Splitting the breakdown into three files is justified by the slice's nine-step size.

### Run Digest

- Response length: 7237 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 369489 / 274180 / 95299 / 7045 / not computed
- Duration: 63.1 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
