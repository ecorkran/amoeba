---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-3.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: e3175941e3b9b62b982951f504ae9c54428c3817
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 49.7
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Fallback matrix omits tasks that carry scope-dependent content"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:19-24"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 8.1 bundles four scenarios and is too large for one pass"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:295-309"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 6.4 mixes the access-log middleware with token-file failure handling"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:87-100"
  - id: F004
    severity: concern
    category: scope-creep
    summary: "Task 6.9 adds a startup rule that is not in the slice design"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:183"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Auth-refusal tests use TestClient where the slice's Technical Requirements say subprocess"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:111"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Success criterion \"listing reads still succeed at the stream cap\" is not asserted in this file"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:233"
  - id: F007
    severity: note
    category: architecture
    summary: "Layering departure is handled narrowly and reported"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:130"
  - id: F008
    severity: note
    category: nfr-coverage
    summary: "No load test or CI gating task, justified in file 1"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:21"
  - id: F009
    severity: note
    category: sequencing
    summary: "Sequencing and test-with pattern are sound"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:30-378"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Fallback matrix omits tasks that carry scope-dependent content

The Context Summary says that if a ruling is "no", the fallback applies in every listed task, tests and docs included. The "D6 scopes" row lists 6.1, 6.3, 6.5, 6.6, 6.8, 8.2 and 8.5. It misses three tasks:
- **Task 6.2** pins the scope column in the file format: unknown-scope refusal, the table-driven refusals, and the "exactly as `amoeba token add` writes it" fixture.
- **Task 6.7** has a test, "a `read` token posting → `403 insufficient_scope`". The matrix lists 6.7 only under principal binding.
- **Task 8.1** has an "Authenticated variant" with a `submit` token.

The scope-denial wording in 6.5 is called out and the others are not. A junior following the matrix literally would leave scope tests in 6.2, 6.7 and 8.1 that fail under the fallback. The TLS row has a similar gap: 7.3 mentions the TLS fallback in prose, but it isn't in the table. Make the matrix complete.

### [CONCERN] Task 8.1 bundles four scenarios and is too large for one pass

Task 8.1 is rated effort 5 and combines four separate end-to-end scenarios:
- the resident-process kill and restart flow;
- the two-way independence test (kill server, then kill resident);
- SSE transcript equality with `amoeba feed`;
- an authenticated rerun.

Each needs subprocess orchestration, and the success criterion requires three consecutive clean runs. Split it into two tasks, 8.1a for the end-to-end flow plus the transcript comparison and 8.1b for independence and the authenticated variant, each committed on its own. A flaky orchestration bug is then easier to isolate.

### [CONCERN] Task 6.4 mixes the access-log middleware with token-file failure handling

Task 6.4 covers runtime fail-closed behavior and log deduplication, then adds an ASGI access-log middleware in `serve/app.py` as a fourth step. The middleware is a different concern: it is the sole access log and is needed by Task 7.1 and the token-leak tests. It also logs the principal, so it must run after authentication. Task 6.4 says nothing about that ordering. Move the middleware to its own small task, or to the start of 6.3 where the auth wiring happens. State the middleware-versus-authenticator order explicitly.

### [CONCERN] Task 6.9 adds a startup rule that is not in the slice design

Task 6.9 says `tls_cert` and `tls_key` are "both required together; one without the other is refused for any host". D6 and the Success Criteria require TLS for non-loopback binds. They say nothing about a half-specified pair on loopback. The rule is sensible, but it is an unratified addition with its own test row and exit-code behavior. Either note it as a deliberate addition for the PM in Task 8.5, or drop it and rely on uvicorn's own failure. As written it does not trace to a success criterion.

### [CONCERN] Auth-refusal tests use TestClient where the slice's Technical Requirements say subprocess

The Technical Requirements say "Stream, auth-refusal, and kill tests run `amoeba serve` as a real subprocess and use stdlib `http.client`". Task 6.5 runs the 401/403/503 request-time refusals only through `TestClient`. Task 7.3 covers startup refusals as a subprocess, but no subprocess test exercises `--auth tokens` request-time rejection, except the authenticated variant in Task 8.1. That variant targets the submit path, not the 401 and 503 cases. Add one subprocess assertion, for example in 7.3: 401 without a token, 200 with one, and no token in stderr. Otherwise record `TestClient` as a deliberate deviation from the requirement.

### [CONCERN] Success criterion "listing reads still succeed at the stream cap" is not asserted in this file

The Success Criteria say that at `max_feed_streams` open streams, the next one is refused with `503 too_many_streams` and listing reads still succeed. Task 7.3 checks the `503` through a small `--max-feed-streams` flag but doesn't check that a listing read still works at the cap. I searched the sibling task files and found no assertion for it. Add the read check to 7.3, or confirm it exists in file 2.

### [NOTE] Layering departure is handled narrowly and reported

The slice says only `cli/serve.py` imports `amoeba.serve`. Task 6.6 has `cli/token.py` import `serve.tokens`. It keeps `serve/__init__.py` empty, narrows the layering test to exactly two importers, and reports the departure to the PM in 8.5. That is acceptable and honestly flagged. The alternative is to put the token store somewhere neutral, such as a small module outside `serve`, which would avoid the departure. The PM should choose.

### [NOTE] No load test or CI gating task, justified in file 1

The slice's only contract promise is the latency bound under Value, and it names no throughput target. Task 5.10 in file 2 covers it with a timing test in the default suite. File 1 says explicitly that no `tests/load/` test and no CI gate is added. The repo has `tests/load/` and `.github/workflows/ci.yml`, so this is a conscious choice and not an oversight. It does leave the latency test without a dedicated gate. The stall, memory and thread-count tests are timing-sensitive, so running them in default CI is worth confirming. Task 7.5's "three consecutive runs" criterion partly covers this.

### [NOTE] Sequencing and test-with pattern are sound

Dependencies chain linearly from 5.10 through 8.5 with no cycles. The test-with pattern holds: 6.1 is tested in 6.2, 6.3 and 6.4 in 6.5, 6.6 and 6.7 carry tests in-task, and 7.1 and 7.2 are tested in 7.3. Commits are spread across all three sections. Every task traces to a success criterion, an LLD requirement, or the ratification fallbacks. The LLD's open-stream `insufficient_scope` inconsistency is identified in 6.8 and carried to the 8.5 report.

### Run Digest

- Response length: 6984 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 49.7 s
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
