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
reviewedSha: 43bc228b48f1f049e126d7936d3a492272bbe50f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 58.2
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Auth, startup, and end-to-end success criteria trace to tasks"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:27-345"
  - id: F002
    severity: concern
    category: correctness
    summary: "`insufficient_scope` on an open stream cannot be produced with two scope values"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:164"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Circular or out-of-order dependency between `tokens.py` and `auth.py`"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:36"
  - id: F004
    severity: concern
    category: prompt-hygiene
    summary: "Hallucination trap in the durable-write helper lookup"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:39"
  - id: F005
    severity: concern
    category: completeness
    summary: "The access-log requirement has no implementing mechanism and the test cannot observe it"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:94"
  - id: F006
    severity: concern
    category: scoping
    summary: "Task 7.3 is oversized and leaves TLS certificate generation unresolved"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:229-238"
  - id: F007
    severity: concern
    category: consistency
    summary: "Fallback paths are not carried through the dependent tests and docs"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:17-22"
  - id: F008
    severity: note
    category: nfr
    summary: "No load test or CI gate for the latency target"
    location: "project-documents/user/slices/109-slice.network-api.md:27"
  - id: F009
    severity: note
    category: consistency
    summary: "Layering departs from the slice's component rule"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:127"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Auth, startup, and end-to-end success criteria trace to tasks

Each LLD criterion in this file's range has a task and a named test:
- **401 and 403 paths, including requests from `127.0.0.1`:** Task 6.5.
- **`principal_mismatch`:** Task 6.7.
- **Runtime token-file failures:** Tasks 6.4 and 6.5, with one ERROR and one INFO.
- **Revoke-last-token gives 401:** Task 6.5.
- **Tokens absent from logs:** Task 6.5.
- **Stream re-authentication:** Task 6.8.
- **Startup refusal matrix and exit 12:** Tasks 6.9 and 7.3.
- **TLS, graceful shutdown, `max_connections`, stall re-run:** Task 7.3.
- **Independence, SSE transcript equals `amoeba feed`, and the authenticated variant:** Task 8.1.
- **The `serve` project-name test:** Task 6.2.
- **Docs, walkthrough, and final criterion-to-test mapping:** Tasks 8.2–8.5.

I found no scope creep. Commit checkpoints are spread through the file and tests sit next to their implementation.

### [CONCERN] `insufficient_scope` on an open stream cannot be produced with two scope values

Task 6.8 tests "lower the principal's scope below `read` (rewrite the file) → `insufficient_scope`". The only scopes are `read` and `submit`, and `submit` includes `read`. No valid file rewrite puts a principal below `read`. An unknown scope makes the file malformed, which gives `auth_unavailable`, not `insufficient_scope`. A junior AI cannot write this test as specified. The same gap is in the LLD (D6 and Success Criteria). Decide how this is exercised and fix the task before work starts. For example, test `authorize()` at the heartbeat hook with a stub authenticator, or drop the case and record the unreachable code as a known departure. Also note that this case disappears under the "scopes not ratified" fallback.

### [CONCERN] Circular or out-of-order dependency between `tokens.py` and `auth.py`

Task 6.1 says `TokenScope` is "defined once in `serve/auth.py`'s vocabulary module and imported here". `TokenAuth` in Task 6.3 must import `tokens.py` to read the file, so `tokens.py` and `auth.py` would import each other. `auth.py` may already hold `NoAuth` from earlier files, but "vocabulary module" names nothing concrete. Name the exact module that holds `TokenScope`, `AuthMode`, and `ApiErrorCode`, and keep it free of imports from `tokens.py`.

### [CONCERN] Hallucination trap in the durable-write helper lookup

Task 6.1 says: "if none was recorded, find it with `grep -rn "write_durably" src/`". Neither the slice nor this task establishes that a helper with that name exists. If the grep returns nothing, an implementer will likely invent `write_durably`, which is the trap the project guidelines describe. Replace the hard-coded name with a stop condition, for example: "If Task 1.1 recorded no helper, search `src/` for an existing atomic or fsync write. If none exists, create one shared helper and say so in the commit."

### [CONCERN] The access-log requirement has no implementing mechanism and the test cannot observe it

Task 6.4 says "the access log records method, path, status, and principal, never headers". Task 6.5 asserts the token is absent from "the access log" under `TestClient`. uvicorn's access log does not include a principal, and `TestClient` does not run uvicorn's logger, so the test would pass vacuously. Task 7.1 does not mention `access_log` or its configuration. Specify who emits the log line (an app middleware, with uvicorn's access log disabled or replaced) and where. Then have the 6.5 test capture that logger, and add a subprocess assertion in Task 7.3 that stderr never contains the token.

### [CONCERN] Task 7.3 is oversized and leaves TLS certificate generation unresolved

Task 7.3 has effort 4 and bundles:
- refusal subprocess cases
- settings-flag behavior
- TLS
- SIGTERM shutdown with a thread-count check
- `max_connections` overflow
- the stall re-run

"Generate a throwaway self-signed certificate at test time" has no stated mechanism. It needs either the `openssl` binary, which may be absent, or a new dev dependency such as `cryptography`. The latter is a footprint change that would need PM approval. State which one to use. Consider splitting into (a) serve/refusal/flags, (b) TLS, and (c) shutdown, `max_connections`, and stall. Task 7.1 also hides non-trivial work: ordering a stop-event set ahead of uvicorn's graceful wait means overriding uvicorn's `Server` signal handling. Add a pointer for that.

### [CONCERN] Fallback paths are not carried through the dependent tests and docs

The ratification fallbacks are listed against the implementation tasks only. Downstream tasks still assume the ratified behavior:
- **Task 7.3 and the walkthrough in 8.4:** assert exit `12`.
- **Tasks 6.5, 6.8, and 8.1:** assert `insufficient_scope` and the `submit` token variant.
- **Tasks 6.1–6.2:** are only partly adjusted for the missing scope column.
- **Task 7.3:** has no TLS-refusal fallback.

Add "if fallback X applied, change this assertion" lines to the affected tasks, or add a rule that the fallback commit must update every dependent test.

### [NOTE] No load test or CI gate for the latency target

The slice states one NFR-like bound under Value: a committed change is on the wire within `follow_interval_seconds` plus delivery time. The design calls for a generous-margin timing test, which belongs in file 2, not this one. No `tests/load/` task or CI-gating task exists in this file, and the slice itself says none of its numeric limits is a contract promise except that latency bound. If the PM wants this treated as an NFR under the review rules, add a load test and a CI wiring task. Otherwise record that the timing test is the intended coverage.

### [NOTE] Layering departs from the slice's component rule

The slice says "Nothing imports `amoeba.serve` except `cli/serve.py`". Task 6.6 also allows `cli/token.py` to import `amoeba.serve.tokens`. That is sensible, since the slice places `tokens.py` in `amoeba.serve`. Task 8.5 should list it as a departure from the LLD, and the LLD's layering sentence should be corrected. Separately, the `chmod 000` case in Task 6.5 fails when tests run as root, so add a skip condition.

### Run Digest

- Response length: 7244 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 58.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
