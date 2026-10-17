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
reviewedSha: 364974b3c106633ee43ac06490d82dd99fe17a4d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 315961
cachedTokens: 223963
cacheWriteTokens: 91990
completionTokens: 9237
durationSeconds: 78.3
costUsd: 0.483409
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Five tasks share one commit, and the guard's tests come two tasks after the code"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:161-251"
  - id: F002
    severity: concern
    category: scope
    summary: "Task 5.1 is too small to stand alone"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:151-165"
  - id: F003
    severity: concern
    category: requirements-clarity
    summary: "Bind-policy rule precedence is ambiguous, and some inputs are unspecified"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:73"
  - id: F004
    severity: concern
    category: requirements-clarity
    summary: "`InvalidSubmissionError` handling has no clear owner"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:117"
  - id: F005
    severity: concern
    category: requirements-clarity
    summary: "Submission body shape leaves required fields undefined"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:287"
  - id: F006
    severity: concern
    category: test-feasibility
    summary: "Traversal tests on path-parameter endpoints probably can't reach the handler as written"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:316"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "Single-definition rule is checked once by hand, not by a committed test"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:138"
  - id: F008
    severity: note
    category: test-coverage
    summary: "Reads error paths: `store_busy` and `store_unreadable` have no end-to-end test"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:223-225"
  - id: F009
    severity: note
    category: proportionality
    summary: "Step detail is heavy but broadly traceable"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:176-181"
  - id: F010
    severity: pass
    category: coverage
    summary: "Coverage of Sections 4–6 against the slice's success criteria"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:22-325"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Five tasks share one commit, and the guard's tests come two tasks after the code

Tasks 5.1, 5.2, 5.3 and 5.4 all say "Committed with Task 5.5", so Sections 5.1–5.5 land as a single commit. That conflicts with the project rule of at least one commit per task and with the slice's "commit after each". It also breaks the test-with pattern for the guard. The guard is written in 5.2 and its tests are in 5.5, after the reads code and tests. A defect in the guard would first surface in a commit that also holds the reads. Reorder so each implementation task is followed by its tests and committed:
- Reads: write the app and reads, test them, commit.
- Guard: write the guard, test it, commit.

Alternatively, have 5.2 add a minimal `test_auth.py` that tests the middleware directly over a stub ASGI app, which doesn't need `build_app`.

### [CONCERN] Task 5.1 is too small to stand alone

Task 5.1 adds fixtures that nothing uses until 5.4. It uses a lazy import so it can be committed before `app.py` exists, and it has no tests or commit of its own. Fold it into 5.4 (or into the reordered reads and guard tasks above). The lazy-import workaround then goes away.

### [CONCERN] Bind-policy rule precedence is ambiguous, and some inputs are unspecified

Task 4.3 says to apply D3's table "in its row order (a short token is refused on every bind)". These two instructions conflict:
- In row order, the loopback row ("serves") comes first and `token_too_short` is last. A short token on loopback would pass, or, off loopback, `tls_required` would win over `token_too_short`.
- The parenthetical implies the short-token check runs first.

Task 4.4 then parametrizes "each row's result", which cannot pin the outcome for combined cases such as a short token with no TLS files off loopback. Three inputs are also unspecified:
- An empty `AMOEBA_SERVE_TOKEN` (treated as unset or as short?).
- Exactly one TLS file given on a loopback bind. `load_cert_chain(certfile, None)` has its own semantics.
- Which rule applies to a short token when other rules also fail.

State an explicit check order and these cases, or ask the PM. Don't leave them for the junior to guess.

### [CONCERN] `InvalidSubmissionError` handling has no clear owner

Task 4.5 lists `InvalidSubmissionError` → `invalid_submission` with its `reason` after the `CODE_BY_EXCEPTION` entries, so it may or may not be in that table. Task 5.3 registers handlers "for each `CODE_BY_EXCEPTION` type". Task 6.1 says exceptions "map through `CODE_BY_EXCEPTION`", but the error body must carry `reason`, which a plain table lookup doesn't produce. Say whether it is in the table and which task registers the handler that adds `reason`. Otherwise the 422 `invalid_submission` test in 6.2 depends on a guess. Task 4.6's mapping test should include it.

### [CONCERN] Submission body shape leaves required fields undefined

Step 3 of Task 6.1 makes only `submission_id` explicitly required. The LLD body is `{kind, submission_id, submitted_by, payload}`. The task doesn't say whether a missing `kind`, `submitted_by` or `payload` is `invalid_body` or is defaulted. A default would be a silent fallback, which project rules forbid. `submit()`'s signature may settle `submitted_by`, but the task doesn't say so. Name the required keys, or ask the PM, and add a test for a missing required key (Task 6.2 currently tests only the missing id).

### [CONCERN] Traversal tests on path-parameter endpoints probably can't reach the handler as written

Task 6.2 expects 400 for traversal ids on both submission endpoints, and the LLD criterion says the same for every endpoint. In the path, these ids are likely to be handled before `validated_project_id` runs:
- `..` and `.` segments are normally normalized away by the HTTP client.
- `%2F` is decoded before Starlette routing, and the default `{project_id}` converter excludes `/`. That gives a 404 route miss, not a 400.

I have not run this. Task 5.4's query-string cases don't have the problem. For the path endpoints, the task should say which encodings actually reach the handler and what status the rest produce. Alternatively, test `validated_project_id` directly for the hostile values and test the endpoints with ids that route. Otherwise the junior will chase failures that come from the test client.

### [CONCERN] Single-definition rule is checked once by hand, not by a committed test

Task 4.6 proves the new import-boundaries rule by adding a temporary `"not_found"` literal and removing it. The rule is a durable guard, so its failure case should be a committed unit test. Run the check against a fixture source string containing an `ApiErrorCode` value, and another containing an integer literal in 400–599. Keep the manual confirmation as an optional extra.

### [NOTE] Reads error paths: `store_busy` and `store_unreadable` have no end-to-end test

The LLD's reads error row includes 503 `store_busy` (with `Retry-After`) and `store_unreadable`. Task 5.4 tests `store_schema_mismatch` only. Task 4.6 covers the table mapping and headers, which is probably enough. A `monkeypatch` that raises each exception inside `read_listing` would exercise the registered handlers cheaply.

### [NOTE] Step detail is heavy but broadly traceable

Tasks 5.2, 5.3 and 4.3 spell out middleware order, header handling and `ssl.SSLContext` construction. Most of this restates the LLD, so I'm not asking for cuts. Task 5.3 combines `reads.py`, `app.py` and all exception handlers at effort 3 and is the one to split if it overruns. A reasonable split is the listing-request parsing and route in one task, and `build_app` with its handlers in another.

### [PASS] Coverage of Sections 4–6 against the slice's success criteria

The criteria that belong in this file all have a task and a test:
- Reads parity with `inspect` and `as_of_seq` (5.3 and 5.4).
- Origin, Host and content-type guards, plus the token never appearing in a log or body (5.2 and 5.5).
- Bind-policy table and TLS failures (4.3 and 4.4).
- Single-definition rule for status numbers and codes (4.6).
- Layering and writer-guard tests (5.6).
- Submission requirements: required id, idempotent retry, `reason` parity with `amoeba submit`, 413 with and without `Content-Length`, and retry after `submission_write_failed` (6.1 and 6.2).

Each task traces to an LLD section, and the dependencies are linear with no cycles. File 3 covers the load test in `tests/load/` and the CI gate for it.

### Run Digest

- Response length: 7821 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 315961 / 223963 / 91990 / 9237 / not computed
- Duration: 78.3 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
