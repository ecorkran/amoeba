---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 953bff7e5383b0a3129a43faf9bd11dd596c5a76
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 79105
cachedTokens: 42880
completionTokens: 9803
reasoningTokens: 7878
durationSeconds: 29.3
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Stated fallback plan contradicts the declared task dependencies"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 5.8 bundles unrelated concerns and exceeds a single junior-AI unit"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F003
    severity: note
    category: ci-integration
    summary: "CI gating is handled by verification, not a wiring task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F004
    severity: note
    category: task-granularity
    summary: "Four near-identical 1-effort export-pin tasks"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md"
  - id: F005
    severity: note
    category: test-coverage
    summary: "Snapshot test does not directly exercise several snapshot fields"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Stated fallback plan contradicts the declared task dependencies

The Context Summary says: "If any is absent [of 105–109], do the sections that do not need it (8, 9.1–9.4, 10.1–10.3) and stop before the rest." File 1 makes the same claim ("Sections 2, 3, 8 and 9.1–9.4 need only 101–104"). But the declared dependencies gate those sections behind the full sequence:

- Task 8.1 `Dependencies: 6.6`, and 8.2 drives `run_sequence` from the clean run (Task 5.9). The clean run exercises steps 5, 9, 10 (Judge/HTTP/tokens via 109, PM detection via 106), so Section 8 in fact **requires** 105–109 — it cannot be the "do this while they're absent" work.
- Task 9.1 `Dependencies: 8.2`, which chains the pruning module (which per the slice genuinely needs only fixtures and public `Node`) behind the sequence it does not depend on conceptually.
- Task 10.1 `Dependencies: 5.9`, so the claimed fallback set `10.1–10.3` is likewise blocked on 105–109.

A junior AI following the declared dependencies will refuse to start the very sections the file tells it to do when 105–109 are missing. Either the fallback list should drop Section 8 and 10.1 (the parts that truly need the sequence) or the dependencies on 8.1/9.1/10.1 should be re-pointed to the real prerequisites (harness Task 4.6, fixtures) so the intended parallelism holds. This is a planning-consistency defect, not a code defect.

### [CONCERN] Task 5.8 bundles unrelated concerns and exceeds a single junior-AI unit

Task 5.8 (effort 4) asks one task to (a) stand up `amoeba serve --auth tokens` as a long-lived server, (b) provision two principals/`amoeba token add`, (c) pick and wire 109's HTTP client for `POST .../submissions`, (d) implement the Judge, Operator, Human, PM, and Inspector actors, and (e) get the whole group to a steps-1–5 smoke pass — each actor on a different surface (subprocess CLI, HTTP-over-network, file-copy). The server/token/HTTP-client infrastructure is the risky, failure-prone half and is coupled to 109's choices recorded only in Task 1.1's notes; the CLI actors (Operator/Human/PM/Inspector) are mechanical and independent. Splitting into "server + tokens + Judge actor" and "CLI actors" would give each half a verifiable success criterion and stop a 109-client mismatch from blocking the trivial actors. Compare Tasks 5.9 and 6.5 (also effort 4), which each cover a single coherent deliverable.

### [NOTE] CI gating is handled by verification, not a wiring task

A load-tier test task exists (Task 7.1, `tests/load/test_restart_matrix.py`). The review expectation is a CI wiring task so gating is not implicit; here Task 7.1 instead instructs "confirm by reading it" that `ci.yml` already runs `tests/load`. Because the gating is explicitly verified rather than assumed, this satisfies the intent, but it is one step short of an auditable wiring assertion (e.g. a check that the `tests/load` step is present and not `continue-on-error`). No action strictly required.

### [NOTE] Four near-identical 1-effort export-pin tasks

Tasks 3.3–3.6 each add one hand-written `test_public_api_*.py` pinning a single package's `__all__`. They are correctly test-with paired and correctly conditional on 105/106, but four separate 1-effort tasks for the same mechanical operation is at the granular end. Merging them into one parametrized pin test (with the two slice-dependent packages skipped-if-absent) would reduce bookkeeping without losing the "deliberate edit in two places" property D2 wants. Acceptable as written.

### [NOTE] Snapshot test does not directly exercise several snapshot fields

Task 4.4 defines the snapshot as including "blocked-state count per node" and "message count per channel", but Task 4.5's test exercises only node status, journal-entry comparison (`completed` vs `adopted`), and block presence. The counts are only indirectly exercised later via the `after-issue` allowed-difference. Adding one assertion for blocked-state/message counts in 4.5 would pin the comparison logic at the unit level rather than relying on the kill-run comparison to catch a regression.

### [PASS] Success-criteria coverage is complete

Every slice-design success criterion maps to a task: clean run + verdict/judge-sample/detection counts (`5.9`); `finding_changes` round-2 names round 1 (`5.9`); per-kill-point completion and snapshot equality (`6.2`–`6.4`, `7.1`); subscriber transcript equals feed-from-0 and rebuilds status (`6.5`); `proof-b` isolation (`5.9`, `8.1`); three directory resolutions and relative-variable refusal (`8.2`, `2.1`); slug-id refusals at `submit`/`open_project`/`Store.open` (`2.3`, `2.4`, `8.2`); the four `done` refusals (`2.5`, `2.6`); the prune classifications and byte-identical runs directory (`9.5`); the guard and its self-test (`4.9`); five export pins (`3.3`–`3.6` plus the existing store pin); import-boundary checks (`9.1`, `11.1`); docs link/anchor resolution (`10.5`); and the 120-designer index (`10.4`). No success criterion lacks a task and no task is untethered from one.

### Run Digest

- Response length: 6418 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 28794
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / completion / reasoning: 79105 / 42880 / 9803 / 7878
- Duration: 29.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
