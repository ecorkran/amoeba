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
reviewedSha: bfdc52b46eb603ad59837542cc3201017c382925
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 53.3
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria in the auth, serve, and end-to-end groups are traced to tasks"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:30-460"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 7.1 cites the wrong task for the access-log middleware"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:217"
  - id: F003
    severity: concern
    category: ci-gating
    summary: "CI gating for the new load tests is a \"confirm\" step, not an explicit wiring task"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:387"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 8.1c is oversized and partly duplicates earlier tests"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:376-391"
  - id: F005
    severity: concern
    category: test-with
    summary: "Tests for Tasks 6.3 and 6.4 are deferred to Task 6.5"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:68-117"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 6.8 stream-auth tests assume a real-server harness that is not `amoeba serve`"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:182"
  - id: F007
    severity: note
    category: scope
    summary: "Documented LLD departures and gaps are properly routed to the PM"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:145"
  - id: F008
    severity: note
    category: sequencing
    summary: "Commit cadence and dependency ordering are sound"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:32-460"
  - id: F009
    severity: note
    category: documentation
    summary: "Exit-code documentation for `SERVE_REFUSED` is not named in Task 8.3"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:421"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria in the auth, serve, and end-to-end groups are traced to tasks

- **Auth and tokens:** the criteria map to 6.1–6.9 and 7.3a. Examples are 401 for no, wrong or revoked tokens (including from `127.0.0.1`), the `principal_mismatch` and `insufficient_scope` 403s, the `auth_unavailable` fail-closed table with one ERROR and one INFO, and open-stream re-authentication.
- **Startup and server:** the refusal matrix is 6.9 and 7.3. TLS is 7.4. Shutdown, the connection cap and the stall test against the real command are 7.5. The slow-header observation is 7.6.
- **End to end and docs:** the end-to-end flow is 8.1, independence is 8.1a, and the authenticated variant is 8.1b. Docs are 8.2 and 8.3. The walkthrough is 8.4 and final validation is 8.5.
- **Serve-as-project:** the "serve is not a project" criterion is completed in 6.2.
- **Token leakage:** the "tokens never in logs" requirement is covered in 6.5a and 7.3.

### [CONCERN] Task 7.1 cites the wrong task for the access-log middleware

Task 7.1 says `access_log=False` because "the Task 6.4 middleware is the access log". Task 6.4 is runtime token-file failure handling. The middleware is Task 6.5a. A junior AI following the reference could look in the wrong task or conclude the middleware doesn't exist. Change the reference to Task 6.5a.

### [CONCERN] CI gating for the new load tests is a "confirm" step, not an explicit wiring task

- **Current wording:** Task 8.1c adds `tests/load/test_serve_streams.py`. Its last step says to "confirm … `.github/workflows/ci.yml` needs no change".
- **What exists:** `.github/workflows/ci.yml:53-54` has a separate "Load tests" step running `uv run pytest tests/load`. So the gate probably does exist.
- **Gap:** the task leaves the check implicit. It doesn't say to confirm the step has no `continue-on-error`. It doesn't say what to do if the workflow differs. Nothing verifies that the new file is actually collected by the CI invocation.
- **Fix:** make this an explicit step: read `ci.yml`, check that the step runs `tests/load` and fails the run, and run the CI command locally to show the new file is collected. If any of that fails, add the wiring.

### [CONCERN] Task 8.1c is oversized and partly duplicates earlier tests

Task 8.1c bundles four scenarios: a fan-out of `max_feed_streams` concurrent clients with transcript equality, stalled clients filling the cap, a latency bound under load, and the CI/collection check. All of it runs against a real resident process and a real server. Its stall scenario repeats Tasks 5.9 and 7.5. A junior AI is unlikely to finish it in one pass at effort 4, and it requires three consecutive green runs. Split it into two tasks, for example fan-out plus transcript equality, then stall plus latency. Or drop the stall rerun and reference 7.5. The slice design states no load NFR beyond the Value-section latency bound, so the scope of this task should be explicit.

### [CONCERN] Tests for Tasks 6.3 and 6.4 are deferred to Task 6.5

Tasks 6.3 (`TokenAuth`) and 6.4 (runtime file-failure handling) are pure implementation with "Commit with Task 6.5" as their only success criterion. Three tasks of security-critical code are written before any test runs, and the file-failure behavior isn't exercised until 6.5. 6.1/6.2 and 7.1–7.3 follow the test-with pattern. Add a minimal test step to 6.3 (401 and scope outcomes) and keep the fuller file-failure tests with 6.4, so each task ends in a runnable check.

### [CONCERN] Task 6.8 stream-auth tests assume a real-server harness that is not `amoeba serve`

Task 6.8 tests "real server, `http.client`" before `amoeba serve` exists (7.1–7.3). The projectState says only the 5.9 harness (`server_main.py`) exists. The task doesn't say which launcher to use or that it must accept a `TokenAuth` and `heartbeat_seconds`. State that explicitly, or confirm in 5.9 that the harness takes an authenticator. Otherwise the junior AI may stall or invent a launcher.

### [NOTE] Documented LLD departures and gaps are properly routed to the PM

- **Open-stream `insufficient_scope`:** the LLD's open-stream `insufficient_scope` case cannot occur with two scopes where `submit` includes `read` (Task 6.8).
- **Lone TLS flag:** the LLD says nothing about a lone TLS flag on loopback (Task 6.9).
- **`cli/token.py` layering:** `cli/token.py` imports `serve.tokens` (Task 6.6).

All three are recorded for Task 8.5. This is correct. The slice's success criterion about a scope "lowered to below `read`" has no producing case, so no test exists for it, and the task says so.

### [NOTE] Commit cadence and dependency ordering are sound

- **Ordering:** no circular dependencies. Section 6 depends on file 2's Task 5.10. Section 7 depends on 6.9. Section 8 depends on 7.6.
- **Commits:** checkpoints are spread across sections, not batched at the end.
- **Fallback matrix:** the PM-ruling fallback matrix in the Context Summary is consistent with the tasks that reference each fallback.
- **Tasks 6.5a and 6.7:** each appears slightly small, but is justified as a separate commit.

### [NOTE] Exit-code documentation for `SERVE_REFUSED` is not named in Task 8.3

Task 8.3 adds `SERVE_REFUSED` to `CHANGELOG.md`. It doesn't say whether an existing exit-code table in `process-contract.md` or another contract needs a row for code 12. If one exists, add it to the task. If none exists, no action is needed.

### Run Digest

- Response length: 6504 chars
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
- Duration: 53.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
